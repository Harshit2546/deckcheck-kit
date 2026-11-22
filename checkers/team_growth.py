"""Checker for team_growth claims against live Crustdata company data.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: sources.crust (get_company), core/models.py, core/log.py.
Extracts headcount growth_percent and growth_absolute and returns CheckResult.
"""

from __future__ import annotations

import re
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

from checkers import _common

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
    """Check a team_growth claim against Crustdata company data."""
    domain = ctx.run.input.domain
    payload, call_id = _common.get_company(ctx, domain)

    rec_date, ref_date, ref_source = _get_dates(claim, ctx, payload.get("updated_at") if payload else None)

    if not payload:
        log_step(ctx.run.id, claim.id, "check.team_growth", "cannot_verify", reason="no_payload")
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

    headcount_obj = data.get("headcount") or {}

    growth_pct: float | None = None
    if isinstance(headcount_obj, dict) and "growth_percent" in headcount_obj:
        val = headcount_obj["growth_percent"]
        if val is not None:
            try:
                growth_pct = float(val)
            except (ValueError, TypeError):
                growth_pct = None

    growth_abs: float | None = None
    if isinstance(headcount_obj, dict) and "growth_absolute" in headcount_obj:
        val = headcount_obj["growth_absolute"]
        if val is not None:
            try:
                growth_abs = float(val)
            except (ValueError, TypeError):
                growth_abs = None

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {
        **_common.company_identity(ctx),
        "record_date": rec_date,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
    }

    if growth_pct is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="headcount.growth_percent",
                value=growth_pct,
                record_date=rec_date,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )
        observed["growth_percent"] = growth_pct

    if growth_abs is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="headcount.growth_absolute",
                value=growth_abs,
                record_date=rec_date,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )
        observed["growth_absolute"] = growth_abs

    log_step(
        ctx.run.id,
        claim.id,
        "check.team_growth",
        "ok",
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=True,
        held_reason=None,
    )
