"""Checker for team_growth claims against live Crustdata company data.

Who calls it: core/runner.py (or pipeline checker stage).
What it calls: sources/crust.py (or context company data), core/models.py, core/log.py.
Extracts headcount growth percent and absolute headcount change and returns CheckResult.
"""

from __future__ import annotations

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
    """Check a team_growth claim against Crustdata company data.

    Extracts growth_percent and growth_absolute. Populates observed with
    "growth_percent", "growth_absolute", and "as_of".
    Never chooses the verdict label.
    """
    company_data, held_reason = _get_company_data(ctx)
    if held_reason is not None:
        log_step(
            ctx.run_id,
            "check_team_growth",
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
            "check_team_growth",
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

    record_date: str | None = data.get("updated_at")
    if record_date and "T" in str(record_date):
        record_date = str(record_date).split("T")[0]

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {}

    if growth_pct is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="headcount.growth_percent",
                value=growth_pct,
                record_date=record_date,
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
                record_date=record_date,
            )
        )
        observed["growth_absolute"] = growth_abs

    if record_date:
        observed["as_of"] = record_date

    comparable = bool(growth_pct is not None or growth_abs is not None)

    log_step(
        ctx.run_id,
        "check_team_growth",
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
check_team_growth = check
