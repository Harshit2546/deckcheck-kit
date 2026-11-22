"""Checker for team_size claims against live Crustdata company timeseries data.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: checkers._common (get_company, company_identity), core/models.py, core/log.py.
Extracts headcount from the latest timeseries point on or before reference date (DECISIONS D13).
Never uses snapshot headcount.total or updated_at.
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


def _parse_range(range_str: str) -> list[float] | None:
    """Parse range string like '11-50' into [11.0, 50.0]."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*$", range_str)
    if m:
        try:
            return [float(m.group(1)), float(m.group(2))]
        except ValueError:
            return None
    return None


def _get_reference_date(claim: Claim, ctx: RunContext) -> tuple[str | None, str]:
    """Extract (reference_date, reference_date_source). Never reads updated_at."""
    ref_date = None
    if claim.as_of and re.match(r"^\d{4}-\d{2}-\d{2}$", claim.as_of.strip()):
        ref_date = claim.as_of.strip()
    elif ctx.run.input.deck_date:
        ref_date = ctx.run.input.deck_date.strip()[:10]

    ref_source = ctx.run.input.deck_date_source or "input"
    return ref_date, ref_source


def _get_timeseries_points(data: dict[str, Any], ref_date: str | None) -> list[tuple[str, float]]:
    """Extract valid (date, employee_count) points dated on or before ref_date, sorted ascending."""
    headcount_obj = data.get("headcount") or {}
    raw_series = []
    if isinstance(headcount_obj, dict):
        raw_series = (
            headcount_obj.get("timeseries")
            or headcount_obj.get("headcount_timeseries")
            or []
        )
    if not raw_series:
        raw_series = data.get("headcount_timeseries") or data.get("timeseries") or []

    valid_points: list[tuple[str, float]] = []
    if isinstance(raw_series, list):
        for pt in raw_series:
            if not isinstance(pt, dict):
                continue
            pt_date_raw = pt.get("date") or pt.get("month") or pt.get("timestamp")
            if not pt_date_raw:
                continue
            pt_date = str(pt_date_raw).split("T")[0]
            cnt = pt.get("employee_count") if pt.get("employee_count") is not None else pt.get("count")
            if cnt is None and "headcount" in pt:
                cnt = pt.get("headcount")
            if cnt is not None:
                try:
                    cnt_val = float(cnt)
                except (ValueError, TypeError):
                    continue
                if ref_date is None or pt_date <= ref_date:
                    valid_points.append((pt_date, cnt_val))

    valid_points.sort(key=lambda x: x[0])
    return valid_points


def check(claim: Claim, ctx: RunContext) -> CheckResult:
    """Check a team_size claim against Crustdata company timeseries data.

    Per DECISIONS D13:
    - Never uses snapshot headcount.total or updated_at.
    - Picks the latest headcount.timeseries[] point on or before reference date.
    - Observed headcount = that point's employee_count.
    - Record_date = that point's date.
    - Evidence field_or_quote = 'headcount.timeseries[<date>].employee_count'.
    - If no such point exists, adds no headcount evidence.
    """
    domain = ctx.run.input.domain
    payload, call_id = _common.get_company(ctx, domain)

    ref_date, ref_source = _get_reference_date(claim, ctx)

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

    valid_points = _get_timeseries_points(data, ref_date)

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {
        **_common.company_identity(ctx),
        "record_date": None,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
    }

    if valid_points:
        latest_date, employee_count = valid_points[-1]
        observed["record_date"] = latest_date
        observed["headcount"] = employee_count
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote=f"headcount.timeseries[{latest_date}].employee_count",
                value=employee_count,
                record_date=latest_date,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )

    basic_info = data.get("basic_info") or {}
    raw_range = basic_info.get("employee_count_range") or data.get("employee_count_range")
    if raw_range:
        parsed_range = _parse_range(str(raw_range))
        if parsed_range is not None:
            observed["headcount_range"] = parsed_range

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
