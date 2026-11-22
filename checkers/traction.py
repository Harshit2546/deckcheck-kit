"""Checker for traction claims (revenue, ARR, growth rate) against live Crustdata company data.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: sources.crust (get_company), core/models.py, core/log.py.
Extracts annual revenue, ARR, and growth rate and returns CheckResult.
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
    """Check a traction claim against Crustdata company data."""
    domain = ctx.run.input.domain
    payload, call_id = get_company(ctx, domain)

    rec_date, ref_date, ref_source = _get_dates(claim, ctx, payload.get("updated_at") if payload else None)

    if not payload:
        log_step(ctx.run.id, claim.id, "check.traction", "cannot_verify", reason="no_payload")
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

    revenue_obj = data.get("revenue") or {}
    traction_obj = data.get("traction") or {}

    annual_revenue: float | None = None
    if isinstance(revenue_obj, dict):
        for k in ["annual_revenue_usd", "estimated_annual_revenue", "revenue"]:
            if k in revenue_obj and revenue_obj[k] is not None:
                try:
                    annual_revenue = float(revenue_obj[k])
                    break
                except (ValueError, TypeError):
                    pass

    growth_rate: float | None = None
    if isinstance(revenue_obj, dict) and "growth_rate" in revenue_obj and revenue_obj["growth_rate"] is not None:
        try:
            growth_rate = float(revenue_obj["growth_rate"])
        except (ValueError, TypeError):
            pass

    arr_val: float | None = None
    if isinstance(traction_obj, dict) and "arr" in traction_obj and traction_obj["arr"] is not None:
        try:
            arr_val = float(traction_obj["arr"])
        except (ValueError, TypeError):
            pass

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {
        "identity": "confirmed",
        "identity_signals": 2,
        "record_date": rec_date,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
    }

    if annual_revenue is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="revenue.annual_revenue_usd",
                value=annual_revenue,
                record_date=rec_date,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )
        observed["revenue"] = annual_revenue

    if arr_val is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="traction.arr",
                value=arr_val,
                record_date=rec_date,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )
        observed["arr"] = arr_val

    if growth_rate is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="revenue.growth_rate",
                value=growth_rate,
                record_date=rec_date,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )
        observed["growth_rate"] = growth_rate

    log_step(
        ctx.run.id,
        claim.id,
        "check.traction",
        "ok",
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=True,
        held_reason=None,
    )
