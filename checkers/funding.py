"""Checker for funding claims against live Crustdata company data.

Who calls it: core/runner.py (or pipeline checker stage).
What it calls: sources/crust.py (or context company data), core/models.py, core/log.py.
Extracts funding rounds, round types, round amounts, and total investment and returns CheckResult.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from core.log import log_step
from core.models import CheckContext, CheckResult, Claim, Evidence, SourceType

CRUSTDATA_ENDPOINT = "https://api.crustdata.com/company/enrich"


def _get_company_data(ctx: CheckContext) -> tuple[dict[str, Any] | None, str | None]:
    """Retrieve company data from context or via sources/crust.py."""
    if ctx.company:
        return ctx.company, None

    domain = ctx.company_domain
    if not domain:
        return None, None

    try:
        from sources.crust import get_company

        company = get_company(domain, run_id=ctx.run_id)
        return company, None
    except ImportError:
        return None, None
    except Exception as exc:
        err_msg = str(exc).lower()
        held_reason = "timeout" if "timeout" in err_msg else "error"
        return None, held_reason


def check(claim: Claim, ctx: CheckContext) -> CheckResult:
    """Check a funding claim against Crustdata company data.

    Extracts round amounts, round types, round dates, and total funding.
    Populates observed with keys expected by verdict/engine: "amount",
    "total_raised", "round_type", "date", and "rounds".
    Never chooses the verdict label.
    """
    company_data, held_reason = _get_company_data(ctx)
    if held_reason is not None:
        log_step(
            ctx.run_id,
            "check_funding",
            "held",
            claim_id=claim.id,
            held_reason=held_reason,
        )
        return CheckResult(
            evidence=[],
            observed={},
            comparable=False,
            held_reason=held_reason,
        )

    if not company_data:
        log_step(
            ctx.run_id,
            "check_funding",
            "cannot_verify",
            claim_id=claim.id,
            reason="no_company_data",
        )
        return CheckResult(
            evidence=[],
            observed={},
            comparable=False,
            held_reason=None,
        )

    data = company_data
    if "matches" in data and isinstance(data["matches"], list) and data["matches"]:
        data = data["matches"][0].get("company_data", data["matches"][0])

    funding_obj = data.get("funding") or {}

    total_raised: float | None = None
    if isinstance(funding_obj, dict) and "total_investment_usd" in funding_obj:
        val = funding_obj["total_investment_usd"]
        if val is not None:
            try:
                total_raised = float(val)
            except (ValueError, TypeError):
                total_raised = None
    elif "total_funding" in data:
        try:
            total_raised = float(data["total_funding"])
        except (ValueError, TypeError):
            total_raised = None

    last_round_amount: float | None = None
    if isinstance(funding_obj, dict) and "last_round_amount_usd" in funding_obj:
        val = funding_obj["last_round_amount_usd"]
        if val is not None:
            try:
                last_round_amount = float(val)
            except (ValueError, TypeError):
                last_round_amount = None

    last_round_type: str | None = None
    if isinstance(funding_obj, dict) and "last_round_type" in funding_obj:
        last_round_type = funding_obj["last_round_type"]

    last_round_date: str | None = None
    if isinstance(funding_obj, dict) and "last_fundraise_date" in funding_obj:
        last_round_date = funding_obj["last_fundraise_date"]
        if last_round_date and "T" in str(last_round_date):
            last_round_date = str(last_round_date).split("T")[0]

    raw_rounds = funding_obj.get("funding_rounds") if isinstance(funding_obj, dict) else None
    rounds: list[dict[str, Any]] = []
    if isinstance(raw_rounds, list):
        for r in raw_rounds:
            if isinstance(r, dict):
                r_type = r.get("round_type") or r.get("type") or ""
                r_amount = r.get("amount_usd") or r.get("amount")
                r_date = r.get("date") or r.get("round_date")
                if r_date and "T" in str(r_date):
                    r_date = str(r_date).split("T")[0]
                try:
                    r_amt_val = float(r_amount) if r_amount is not None else None
                except (ValueError, TypeError):
                    r_amt_val = None
                rounds.append({
                    "round_type": str(r_type),
                    "amount": r_amt_val,
                    "date": str(r_date) if r_date else None,
                })

    # Determine which round or metric is target of the claim
    claim_text = f"{claim.metric or ''} {claim.quote}".lower()
    target_amount: float | None = None
    target_round_type: str | None = None
    target_date: str | None = None

    is_total_claim = any(kw in claim_text for kw in ["total raised", "total funding", "raised in total"])

    if is_total_claim and total_raised is not None:
        target_amount = total_raised
        target_round_type = "TOTAL"
        target_date = last_round_date
    else:
        # Check if a specific round type is mentioned (e.g. "seed", "series a", "series b", "pre-seed")
        matched_round: dict[str, Any] | None = None
        for r in rounds:
            r_t = str(r["round_type"]).lower()
            if r_t and r_t in claim_text:
                matched_round = r
                break

        if matched_round is not None:
            target_amount = matched_round.get("amount")
            target_round_type = matched_round.get("round_type")
            target_date = matched_round.get("date")
        else:
            # Fallback to last round if available, or total raised
            target_amount = last_round_amount if last_round_amount is not None else total_raised
            target_round_type = last_round_type
            target_date = last_round_date

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {}

    if target_amount is not None:
        observed["amount"] = target_amount
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="funding.last_round_amount_usd" if target_amount == last_round_amount else "funding.total_investment_usd",
                value=target_amount,
                record_date=target_date,
            )
        )

    if total_raised is not None:
        observed["total_raised"] = total_raised
        if target_amount != total_raised:
            evidence.append(
                Evidence(
                    id=uuid.uuid4().hex,
                    claim_id=claim.id,
                    source_type=SourceType.CRUSTDATA_COMPANY,
                    locator=CRUSTDATA_ENDPOINT,
                    field_or_quote="funding.total_investment_usd",
                    value=total_raised,
                    record_date=last_round_date,
                )
            )

    if target_round_type is not None:
        observed["round_type"] = target_round_type

    if target_date is not None:
        observed["date"] = target_date

    if rounds:
        observed["rounds"] = rounds

    comparable = bool(observed and target_amount is not None)

    log_step(
        ctx.run_id,
        "check_funding",
        "ok" if comparable else "cannot_verify",
        claim_id=claim.id,
        observed=observed,
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=comparable,
        held_reason=None,
    )


# Alias
check_funding = check
