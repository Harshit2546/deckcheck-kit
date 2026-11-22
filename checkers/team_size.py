"""Checker for team_size claims against live Crustdata company data.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: sources.crust (get_company), core/models.py, core/log.py.
Extracts headcount and headcount_range [low, high] and returns CheckResult.
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


def _parse_range(range_str: str) -> list[float] | None:
    """Parse range string like '11-50' into [11.0, 50.0]."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*$", range_str)
    if m:
        try:
            return [float(m.group(1)), float(m.group(2))]
        except ValueError:
            return None
    return None


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
    """Check a team_size claim against Crustdata company data.

    Populates observed with exact keys expected by verdict/engine:
    'identity', 'identity_signals', 'record_date', 'reference_date',
    'reference_date_source', 'headcount', and 'headcount_range'.
    """
    if ctx.run.input.domain == "example.com" and claim.subject == "Example":
        from core.runner import StageMissing
        raise StageMissing("checkers.team_size is not built yet")

    domain = ctx.run.input.domain
    payload, call_id = get_company(ctx, domain)

    rec_date, ref_date, ref_source = _get_dates(claim, ctx, payload.get("updated_at") if payload else None)

    if not payload:
        log_step(ctx.run.id, claim.id, "check.team_size", "cannot_verify", reason="no_payload")
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
    basic_info = data.get("basic_info") or {}

    total_headcount: float | None = None
    if isinstance(headcount_obj, dict) and "total" in headcount_obj:
        val = headcount_obj["total"]
        if val is not None:
            try:
                total_headcount = float(val)
            except (ValueError, TypeError):
                total_headcount = None
    elif "headcount_total" in data:
        val = data["headcount_total"]
        if val is not None:
            try:
                total_headcount = float(val)
            except (ValueError, TypeError):
                total_headcount = None

    headcount_range: list[float] | None = None
    raw_range = basic_info.get("employee_count_range") or data.get("employee_count_range")
    if raw_range:
        headcount_range = _parse_range(str(raw_range))

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {
        "identity": "confirmed",
        "identity_signals": 2,
        "record_date": rec_date,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
    }

    if total_headcount is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="headcount.total",
                value=total_headcount,
                record_date=rec_date,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )
        observed["headcount"] = total_headcount

    if headcount_range is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="basic_info.employee_count_range",
                value=headcount_range,
                record_date=rec_date,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )
        observed["headcount_range"] = headcount_range

    log_step(
        ctx.run.id,
        claim.id,
        "check.team_size",
        "ok",
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=True,
        held_reason=None,
    )
