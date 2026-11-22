"""Checker for funding claims against live Crustdata company data.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: checkers._common (get_company, company_identity), core/models.py, core/log.py.
Extracts total_raised, rounds, matched_round, and investors and returns CheckResult.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from checkers import _common
from core.log import log_step
from core.models import (
    CheckResult,
    Claim,
    Evidence,
    RunContext,
    SourceType,
    now_iso,
)

CRUSTDATA_ENDPOINT = "https://api.crustdata.com/company/enrich"

MONTH_NAMES = {
    "01": "jan", "02": "feb", "03": "mar", "04": "apr",
    "05": "may", "06": "jun", "07": "jul", "08": "aug",
    "09": "sep", "10": "oct", "11": "nov", "12": "dec",
}


def _get_reference_date(claim: Claim, ctx: RunContext) -> tuple[str | None, str]:
    """Extract (reference_date, reference_date_source). Never reads updated_at."""
    ref_date = None
    if claim.as_of and re.match(r"^\d{4}-\d{2}-\d{2}$", claim.as_of.strip()):
        ref_date = claim.as_of.strip()
    elif ctx.run.input.deck_date:
        ref_date = ctx.run.input.deck_date.strip()[:10]

    ref_source = ctx.run.input.deck_date_source or "input"
    return ref_date, ref_source


def check(claim: Claim, ctx: RunContext) -> CheckResult:
    """Check a funding claim against Crustdata company data.

    Populates observed with exact keys expected by verdict/engine:
    'identity', 'identity_signals', 'record_date', 'reference_date',
    'reference_date_source', 'currency', 'total_raised', 'excluded_later_rounds',
    'undated_rounds', 'matched_round', and 'investors_found'.
    """
    domain = ctx.run.input.domain
    payload, call_id = _common.get_company(ctx, domain)

    ref_date, ref_source = _get_reference_date(claim, ctx)

    if not payload:
        log_step(ctx.run.id, claim.id, "check.funding", "cannot_verify", reason="no_payload")
        return CheckResult(
            evidence=[],
            observed={
                "identity": "not_found",
                "identity_signals": 0,
                "record_date": None,
                "reference_date": ref_date,
                "reference_date_source": ref_source,
                "currency": "USD",
                "total_raised": None,
                "excluded_later_rounds": 0,
                "undated_rounds": 0,
                "matched_round": None,
                "investors_found": [],
            },
            comparable=True,
            held_reason=None,
        )

    data = payload
    if "matches" in data and isinstance(data["matches"], list) and data["matches"]:
        data = data["matches"][0].get("company_data", data["matches"][0])

    funding_obj = data.get("funding") or {}

    raw_milestones = None
    source_key = "milestones"
    if isinstance(funding_obj, dict) and funding_obj.get("milestones") is not None:
        raw_milestones = funding_obj["milestones"]
        source_key = "milestones"
    elif data.get("milestones") is not None:
        raw_milestones = data["milestones"]
        source_key = "milestones"
    elif isinstance(funding_obj, dict) and funding_obj.get("funding_rounds") is not None:
        raw_milestones = funding_obj["funding_rounds"]
        source_key = "funding_rounds"
    elif data.get("funding_rounds") is not None:
        raw_milestones = data["funding_rounds"]
        source_key = "funding_rounds"

    currency = "USD"
    if isinstance(funding_obj, dict) and funding_obj.get("currency"):
        currency = str(funding_obj["currency"]).strip().upper()

    rec_date: str | None = None
    total_raised_val: float | None = None
    excluded_count = 0
    undated_count = 0
    matched_round: dict[str, Any] | None = None
    investors_set: set[str] = set()
    evidence: list[Evidence] = []

    if isinstance(raw_milestones, list):
        parsed_milestones: list[dict[str, Any]] = []
        funded_milestones: list[dict[str, Any]] = []
        total_raised_sum = 0.0
        has_funded = False

        for m in raw_milestones:
            if not isinstance(m, dict):
                continue

            stage = str(m.get("round_type") or m.get("stage") or m.get("type") or "").strip()
            raw_amt = m.get("amount_usd") if m.get("amount_usd") is not None else m.get("amount")
            m_curr = str(m.get("currency") or currency).strip().upper()

            m_date_raw = m.get("date") or m.get("funding_date") or m.get("round_date")
            m_date_str: str | None = None
            if m_date_raw:
                m_date_str = str(m_date_raw).split("T")[0].strip()

            raw_inv = m.get("investors")
            inv_list: list[str] = []
            if isinstance(raw_inv, str):
                inv_list = [x.strip() for x in raw_inv.split(",") if x.strip()]
            elif isinstance(raw_inv, list):
                inv_list = [str(x).strip() for x in raw_inv if str(x).strip()]
            elif isinstance(m.get("investors_detailed"), list):
                inv_list = [
                    str(d["name"]).strip()
                    for d in m["investors_detailed"]
                    if isinstance(d, dict) and d.get("name")
                ]

            amt_val: float | None = None
            if raw_amt is not None:
                try:
                    amt_val = float(raw_amt)
                except (ValueError, TypeError):
                    amt_val = None

            # Fix requirement: "undated_rounds = milestones missing a date OR amount_usd (not in the total)"
            if not m_date_str or amt_val is None:
                undated_count += 1
                item = {
                    "stage": stage,
                    "amount": amt_val,
                    "currency": m_curr,
                    "date": m_date_str,
                    "investors": inv_list,
                }
                parsed_milestones.append(item)
                if not (ref_date and m_date_str and m_date_str > ref_date):
                    for inv in inv_list:
                        investors_set.add(inv)
                continue

            # Fix requirement: "excluded_later_rounds = milestones dated after it" (after reference date)
            if ref_date and m_date_str > ref_date:
                excluded_count += 1
                continue

            # Milestone with date <= reference date and amount_usd
            total_raised_sum += amt_val
            has_funded = True
            if rec_date is None or m_date_str > rec_date:
                rec_date = m_date_str

            for inv in inv_list:
                investors_set.add(inv)

            item = {
                "stage": stage,
                "amount": amt_val,
                "currency": m_curr,
                "date": m_date_str,
                "investors": inv_list,
            }
            parsed_milestones.append(item)
            funded_milestones.append(item)

        if has_funded:
            total_raised_val = total_raised_sum

        is_total_raised_claim = (claim.metric or "").strip().lower() == "total_raised"

        if not is_total_raised_claim and parsed_milestones:
            claim_text = f"{claim.metric or ''} {claim.quote}".lower()
            candidates: list[tuple[int, str, dict[str, Any]]] = []

            for m in parsed_milestones:
                if ref_date and m["date"] and m["date"] > ref_date:
                    continue

                score = 0
                st_raw = m["stage"].lower()
                st_norm = st_raw.replace("_", " ").strip()
                st_slug = st_raw.replace(" ", "_").strip()

                # Stage match
                if st_norm and (st_norm in claim_text or st_slug in claim_text):
                    score += 10

                # Date match
                if m["date"]:
                    if claim.as_of and (claim.as_of in m["date"] or m["date"] in claim.as_of):
                        score += 10
                    elif m["date"] in claim_text:
                        score += 10
                    else:
                        if m["date"][:4] in claim_text:
                            score += 5
                        month_abbr = MONTH_NAMES.get(m["date"][5:7])
                        if month_abbr and month_abbr in claim_text:
                            score += 3

                # Amount match
                if claim.value is not None and m["amount"] is not None:
                    try:
                        if abs(m["amount"] - float(claim.value)) <= 0.01:
                            score += 8
                    except (ValueError, TypeError):
                        pass

                date_key = m["date"] or ""
                candidates.append((score, date_key, m))

            candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

            if candidates and candidates[0][0] >= 10:
                matched_round = candidates[0][2]
            elif len(candidates) == 1 and (claim.metric or "").strip().lower() == "round_amount":
                matched_round = candidates[0][2]

        if matched_round is not None and matched_round.get("date"):
            rec_date = matched_round["date"]

        if matched_round is not None and matched_round.get("amount") is not None:
            m_date = matched_round.get("date") or rec_date
            field_or_quote = (
                f"funding.{source_key}[{m_date}].amount_usd"
                if m_date
                else f"funding.{source_key}.amount_usd"
            )
            evidence.append(
                Evidence(
                    id=uuid.uuid4().hex,
                    claim_id=claim.id,
                    source_type=SourceType.CRUSTDATA_COMPANY,
                    locator=CRUSTDATA_ENDPOINT,
                    field_or_quote=field_or_quote,
                    value=matched_round["amount"],
                    record_date=m_date,
                    retrieved_at=now_iso(),
                    call_id=call_id,
                )
            )
        elif total_raised_val is not None:
            for m in sorted(funded_milestones, key=lambda x: str(x.get("date") or ""), reverse=True):
                m_date = m.get("date") or rec_date
                field_or_quote = (
                    f"funding.{source_key}[{m_date}].amount_usd"
                    if m_date
                    else f"funding.{source_key}.amount_usd"
                )
                evidence.append(
                    Evidence(
                        id=uuid.uuid4().hex,
                        claim_id=claim.id,
                        source_type=SourceType.CRUSTDATA_COMPANY,
                        locator=CRUSTDATA_ENDPOINT,
                        field_or_quote=field_or_quote,
                        value=m["amount"],
                        record_date=m_date,
                        retrieved_at=now_iso(),
                        call_id=call_id,
                    )
                )
    else:
        # Fallback to last_round_* / total_investment_usd only if milestones is absent
        last_date = funding_obj.get("last_fundraise_date") if isinstance(funding_obj, dict) else None
        if not last_date and isinstance(data, dict):
            last_date = data.get("last_fundraise_date")

        last_date_str: str | None = None
        if last_date:
            last_date_str = str(last_date).split("T")[0]

        if last_date_str and (ref_date is None or last_date_str <= ref_date):
            rec_date = last_date_str

        last_round_amt = funding_obj.get("last_round_amount_usd") if isinstance(funding_obj, dict) else None
        last_round_type = funding_obj.get("last_round_type") if isinstance(funding_obj, dict) else None
        tot_inv = funding_obj.get("total_investment_usd") if isinstance(funding_obj, dict) else None
        if tot_inv is None and isinstance(data, dict):
            tot_inv = data.get("total_investment_usd")

        if tot_inv is not None:
            try:
                total_raised_val = float(tot_inv)
            except (ValueError, TypeError):
                total_raised_val = None

        if last_round_type and last_round_amt is not None:
            try:
                amt_f = float(last_round_amt)
                matched_round = {
                    "stage": str(last_round_type).strip(),
                    "amount": amt_f,
                    "currency": currency,
                    "date": last_date_str,
                    "investors": [],
                }
            except (ValueError, TypeError):
                pass

        if matched_round is not None and matched_round.get("amount") is not None:
            evidence.append(
                Evidence(
                    id=uuid.uuid4().hex,
                    claim_id=claim.id,
                    source_type=SourceType.CRUSTDATA_COMPANY,
                    locator=CRUSTDATA_ENDPOINT,
                    field_or_quote="funding.last_round_amount_usd",
                    value=matched_round["amount"],
                    record_date=rec_date,
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
        **_common.company_identity(ctx),
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
