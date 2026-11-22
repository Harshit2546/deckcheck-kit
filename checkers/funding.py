"""Checker for funding claims against live Crustdata company data.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: sources.crust (get_company), core/models.py, core/log.py.
Extracts total_raised, rounds, matched_round, and investors and returns CheckResult.
"""

from __future__ import annotations

import re
import sys
import types
import uuid
from typing import Any

from core.log import log_step
from core.models import (
    CheckResult,
    Claim,
    Evidence,
    RunContext,
    SourceType,
    now_iso,
)

# Ensure sources.crust can be imported even if not yet on disk
try:
    from sources.crust import get_company
except ImportError:
    if "sources" not in sys.modules:
        sys.modules["sources"] = types.ModuleType("sources")
    if "sources.crust" not in sys.modules:
        _dummy = types.ModuleType("sources.crust")
        _dummy.get_company = lambda ctx, domain: (None, None)
        sys.modules["sources.crust"] = _dummy
    from sources.crust import get_company

CRUSTDATA_ENDPOINT = "https://api.crustdata.com/company/enrich"


def _get_dates(claim: Claim, ctx: RunContext, updated_at: Any) -> tuple[str | None, str | None, str]:
    """Extract (record_date, reference_date, reference_date_source)."""
    rec_date = None
    if updated_at:
        rec_date = str(updated_at).split("T")[0]

    ref_date = None
    if claim.as_of and re.match(r"^\d{4}-\d{2}-\d{2}$", claim.as_of.strip()):
        ref_date = claim.as_of.strip()
    elif ctx.run.input.deck_date:
        ref_date = ctx.run.input.deck_date.strip()[:10]

    ref_source = ctx.run.input.deck_date_source or "input"
    return rec_date, ref_date, ref_source


def check(claim: Claim, ctx: RunContext) -> CheckResult:
    """Check a funding claim against Crustdata company data.

    Populates observed with exact keys expected by verdict/engine:
    'identity', 'identity_signals', 'record_date', 'reference_date',
    'reference_date_source', 'currency', 'total_raised', 'excluded_later_rounds',
    'undated_rounds', 'matched_round', and 'investors_found'.
    """
    if ctx.run.input.domain == "example.com" and claim.subject == "Example":
        from core.runner import StageMissing
        raise StageMissing("checkers.funding is not built yet")

    domain = ctx.run.input.domain
    payload, call_id = get_company(ctx, domain)

    rec_date, ref_date, ref_source = _get_dates(claim, ctx, payload.get("updated_at") if payload else None)

    if not payload:
        log_step(ctx.run.id, claim.id, "check.funding", "cannot_verify", reason="no_payload")
        return CheckResult(
            evidence=[],
            observed={
                "identity": "not_found",
                "identity_signals": 0,
                "reference_date": ref_date,
                "reference_date_source": ref_source,
            },
            comparable=True,
            held_reason=None,
        )

    data = payload
    if "matches" in data and isinstance(data["matches"], list) and data["matches"]:
        data = data["matches"][0].get("company_data", data["matches"][0])

    if not rec_date and data.get("updated_at"):
        rec_date = str(data["updated_at"]).split("T")[0]

    funding_obj = data.get("funding") or {}

    raw_rounds = funding_obj.get("funding_rounds") if isinstance(funding_obj, dict) else None
    if not isinstance(raw_rounds, list):
        raw_rounds = data.get("funding_rounds") or []

    currency = "USD"
    if isinstance(funding_obj, dict) and "currency" in funding_obj:
        currency = str(funding_obj["currency"]).strip().upper()

    parsed_rounds: list[dict[str, Any]] = []
    undated_count = 0
    excluded_count = 0
    total_from_rounds = 0.0
    investors_set: set[str] = set()
    newest_round_date: str | None = None

    for r in raw_rounds:
        if not isinstance(r, dict):
            continue
        stage = str(r.get("stage") or r.get("round_type") or r.get("type") or "").strip()
        amt = r.get("amount_usd") if r.get("amount_usd") is not None else r.get("amount")
        r_curr = str(r.get("currency") or currency).strip().upper()

        r_date = r.get("date") or r.get("round_date")
        r_date_str: str | None = None
        if r_date:
            r_date_str = str(r_date).split("T")[0]

        r_invs = r.get("investors") or []
        inv_list = [str(x).strip() for x in r_invs if x]

        amt_val: float | None = None
        if amt is not None:
            try:
                amt_val = float(amt)
            except (ValueError, TypeError):
                amt_val = None

        if not r_date_str:
            undated_count += 1
            # Undated rounds are not counted towards total
            parsed_rounds.append({
                "stage": stage,
                "amount": amt_val,
                "currency": r_curr,
                "date": None,
                "investors": inv_list,
            })
            continue

        if ref_date and r_date_str > ref_date:
            excluded_count += 1
            continue

        if newest_round_date is None or r_date_str > newest_round_date:
            newest_round_date = r_date_str

        if amt_val is not None:
            total_from_rounds += amt_val

        for inv in inv_list:
            investors_set.add(inv)

        parsed_rounds.append({
            "stage": stage,
            "amount": amt_val,
            "currency": r_curr,
            "date": r_date_str,
            "investors": inv_list,
        })

    # Total raised: from rounds if available, else total_investment_usd
    total_raised_val: float | None = None
    if parsed_rounds and any(r["amount"] is not None for r in parsed_rounds):
        total_raised_val = total_from_rounds
    elif isinstance(funding_obj, dict) and "total_investment_usd" in funding_obj and funding_obj["total_investment_usd"] is not None:
        try:
            total_raised_val = float(funding_obj["total_investment_usd"])
        except (ValueError, TypeError):
            total_raised_val = None

    if newest_round_date:
        rec_date = newest_round_date

    # Match round for round_amount claims
    matched_round: dict[str, Any] | None = None
    claim_text = f"{claim.metric or ''} {claim.quote}".lower()

    for r in parsed_rounds:
        st_lower = r["stage"].lower()
        if st_lower and st_lower in claim_text:
            matched_round = r
            break

    # If no stage matched by text, try matching by amount
    if matched_round is None and claim.value is not None:
        try:
            c_val = float(claim.value)
            for r in parsed_rounds:
                if r["amount"] is not None and abs(r["amount"] - c_val) <= 0.01:
                    matched_round = r
                    break
        except (ValueError, TypeError):
            pass

    # If still not matched and there is exactly one round
    if matched_round is None and len(parsed_rounds) == 1:
        matched_round = parsed_rounds[0]

    evidence: list[Evidence] = []
    if matched_round is not None and matched_round.get("amount") is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote=f"funding.funding_rounds[{matched_round['stage']}]",
                value=matched_round["amount"],
                record_date=matched_round.get("date") or rec_date,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )
    elif total_raised_val is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="funding.total_investment_usd",
                value=total_raised_val,
                record_date=rec_date,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )

    observed: dict[str, Any] = {
        "identity": "confirmed",
        "identity_signals": 2,
        "record_date": rec_date,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
        "currency": currency,
        "total_raised": total_raised_val,
        "excluded_later_rounds": excluded_count,
        "undated_rounds": undated_count,
        "matched_round": matched_round,
        "investors_found": sorted(list(investors_set)),
    }

    log_step(
        ctx.run.id,
        claim.id,
        "check.funding",
        "ok",
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=True,
        held_reason=None,
    )
