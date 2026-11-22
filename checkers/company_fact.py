"""Checker for company_fact claims against live Crustdata company data.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: checkers._common (get_company, company_identity), core/models.py, core/log.py.
Extracts company identity facts, founding year, headquarters, company type, and legal status.
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


def _get_dates(claim: Claim, ctx: RunContext, updated_at: Any) -> tuple[str | None, str | None, str]:
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
    """Check a company_fact claim against Crustdata company data."""
    domain = ctx.run.input.domain
    payload, call_id = _common.get_company(ctx, domain)

    rec_date, ref_date, ref_source = _get_dates(claim, ctx, payload.get("updated_at") if payload else None)

    if not payload:
        log_step(ctx.run.id, claim.id, "check.company_fact", "cannot_verify", reason="no_payload")
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

    basic_info = data.get("basic_info") or {}
    locations = data.get("locations") or {}

    year_founded: int | None = None
    raw_year = basic_info.get("year_founded") or data.get("year_founded")
    if raw_year is not None:
        try:
            year_founded = int(raw_year)
        except (ValueError, TypeError):
            year_founded = None

    headquarters = locations.get("headquarters") or basic_info.get("headquarters")
    company_type = basic_info.get("company_type") or data.get("company_type")
    status = basic_info.get("status") or data.get("status")
    name = basic_info.get("name") or data.get("name")
    primary_domain = basic_info.get("primary_domain") or data.get("primary_domain") or domain

    evidence: list[Evidence] = []
    metric_str = (claim.metric or "").strip().lower()

    if "year" in metric_str or "found" in metric_str:
        if year_founded is not None:
            evidence.append(
                Evidence(
                    id=uuid.uuid4().hex,
                    claim_id=claim.id,
                    source_type=SourceType.CRUSTDATA_COMPANY,
                    locator=CRUSTDATA_ENDPOINT,
                    field_or_quote="basic_info.year_founded",
                    value=year_founded,
                    record_date=rec_date,
                    retrieved_at=now_iso(),
                    call_id=call_id,
                )
            )
    elif "headquarter" in metric_str or "location" in metric_str or "hq" in metric_str:
        if headquarters:
            evidence.append(
                Evidence(
                    id=uuid.uuid4().hex,
                    claim_id=claim.id,
                    source_type=SourceType.CRUSTDATA_COMPANY,
                    locator=CRUSTDATA_ENDPOINT,
                    field_or_quote="locations.headquarters",
                    value=headquarters,
                    record_date=rec_date,
                    retrieved_at=now_iso(),
                    call_id=call_id,
                )
            )
    else:
        # General company fact
        fact_val = year_founded or headquarters or name
        if fact_val is not None:
            evidence.append(
                Evidence(
                    id=uuid.uuid4().hex,
                    claim_id=claim.id,
                    source_type=SourceType.CRUSTDATA_COMPANY,
                    locator=CRUSTDATA_ENDPOINT,
                    field_or_quote="basic_info",
                    value={
                        "name": name,
                        "year_founded": year_founded,
                        "headquarters": headquarters,
                        "company_type": company_type,
                        "status": status,
                    },
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
        "year_founded": year_founded,
        "headquarters": headquarters,
        "company_type": company_type,
        "status": status,
        "name": name,
        "domain": primary_domain,
    }

    log_step(
        ctx.run.id,
        claim.id,
        "check.company_fact",
        "ok",
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=True,
        held_reason=None,
    )
