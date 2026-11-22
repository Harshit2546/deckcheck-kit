"""Checker for hiring claims against live Crustdata company data.

Who calls it: core/runner.py (or pipeline checker stage).
What it calls: sources/crust.py (or context company data), core/models.py, core/log.py.
Extracts active job openings count, openings growth, and open roles and returns CheckResult.
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
    """Check a hiring claim against Crustdata company data.

    Extracts openings_count, openings_growth_percent, and open roles.
    Populates observed with "openings_count", "growth_percent", "openings", and "as_of".
    Never chooses the verdict label.
    """
    company_data, held_reason = _get_company_data(ctx)
    if held_reason is not None:
        log_step(
            ctx.run_id,
            "check_hiring",
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
            "check_hiring",
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

    hiring_obj = data.get("hiring") or {}

    openings_count: int | None = None
    if isinstance(hiring_obj, dict) and "openings_count" in hiring_obj:
        val = hiring_obj["openings_count"]
        if val is not None:
            try:
                openings_count = int(val)
            except (ValueError, TypeError):
                openings_count = None

    growth_percent: float | None = None
    if isinstance(hiring_obj, dict) and "openings_growth_percent" in hiring_obj:
        val = hiring_obj["openings_growth_percent"]
        if val is not None:
            try:
                growth_percent = float(val)
            except (ValueError, TypeError):
                growth_percent = None

    openings_raw = hiring_obj.get("recent_openings") if isinstance(hiring_obj, dict) else None
    openings: list[str] = []
    if isinstance(openings_raw, list):
        for item in openings_raw:
            if isinstance(item, str):
                openings.append(item)
            elif isinstance(item, dict) and "title" in item:
                openings.append(str(item["title"]))

    record_date: str | None = data.get("updated_at")
    if record_date and "T" in str(record_date):
        record_date = str(record_date).split("T")[0]

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {}

    if openings_count is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_JOB,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="hiring.openings_count",
                value=openings_count,
                record_date=record_date,
            )
        )
        observed["openings_count"] = openings_count

    if growth_percent is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_JOB,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="hiring.openings_growth_percent",
                value=growth_percent,
                record_date=record_date,
            )
        )
        observed["growth_percent"] = growth_percent

    if openings:
        observed["openings"] = openings

    if record_date:
        observed["as_of"] = record_date

    comparable = bool(openings_count is not None or growth_percent is not None or openings)

    log_step(
        ctx.run_id,
        "check_hiring",
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
check_hiring = check
