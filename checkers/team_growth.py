"""Checker for team_growth claims against live Crustdata company timeseries data.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: checkers._common (get_company, company_identity), core/models.py, core/log.py.
Computes growth in code from two timeseries points on or before reference date (DECISIONS D13).
Never uses snapshot growth or updated_at.
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
    """Check a team_growth claim against Crustdata company timeseries data.

    Per DECISIONS D13:
    - Never uses snapshot growth or updated_at.
    - Computes growth in code from two timeseries points on or before reference date.
    - If fewer than two such points exist, adds no headcount evidence.
    """
    domain = ctx.run.input.domain
    payload, call_id = _common.get_company(ctx, domain)

    ref_date, ref_source = _get_reference_date(claim, ctx)

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

    valid_points = _get_timeseries_points(data, ref_date)

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {
        **_common.company_identity(ctx),
        "record_date": None,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
    }

    if len(valid_points) >= 2:
        d2, c2 = valid_points[-1]

        # Determine earlier baseline point
        quote_lower = (claim.quote or "").lower()
        d1, c1 = valid_points[0]
        if ("year-to-date" in quote_lower or "ytd" in quote_lower) and len(valid_points) > 2:
            year_pts = [p for p in valid_points[:-1] if p[0][:4] == d2[:4]]
            if year_pts:
                d1, c1 = year_pts[0]

        growth_abs = c2 - c1
        growth_pct = round(((c2 - c1) / c1) * 100.0, 2) if c1 > 0 else 0.0

        observed["record_date"] = d2
        observed["growth_percent"] = growth_pct
        observed["growth_absolute"] = growth_abs

        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote=f"headcount.timeseries[{d1}..{d2}].growth_percent",
                value=growth_pct,
                record_date=d2,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote=f"headcount.timeseries[{d1}..{d2}].growth_absolute",
                value=growth_abs,
                record_date=d2,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )

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
