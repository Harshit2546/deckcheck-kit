"""Checker for team_size claims against live Crustdata company data.

Who calls it: core/runner.py (or pipeline checker stage).
What it calls: sources/crust.py (or context company data), core/models.py, core/log.py.
Extracts headcount and employee count range from Crustdata company enrichment and returns CheckResult.
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
    """Check a team_size claim against Crustdata company data.

    Extracts headcount and employee count range. Populates observed with
    keys expected by verdict/engine: "headcount", "range", and "as_of".
    Never chooses the verdict label.
    """
    company_data, held_reason = _get_company_data(ctx)
    if held_reason is not None:
        log_step(
            ctx.run_id,
            "check_team_size",
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
            "check_team_size",
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

    # In Crustdata response, company details can be under matches[0].company_data or at root
    data = company_data
    if "matches" in data and isinstance(data["matches"], list) and data["matches"]:
        data = data["matches"][0].get("company_data", data["matches"][0])

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

    range_str: str | None = None
    if isinstance(basic_info, dict) and "employee_count_range" in basic_info:
        range_str = basic_info["employee_count_range"]
    elif "employee_count_range" in data:
        range_str = data["employee_count_range"]

    record_date: str | None = data.get("updated_at")
    if record_date and "T" in str(record_date):
        record_date = str(record_date).split("T")[0]

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {}

    if total_headcount is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="headcount.total",
                value=total_headcount,
                record_date=record_date,
            )
        )
        observed["headcount"] = total_headcount

    if range_str is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="basic_info.employee_count_range",
                value=range_str,
                record_date=record_date,
            )
        )
        observed["range"] = range_str

    if record_date:
        observed["as_of"] = record_date

    comparable = bool(observed and (total_headcount is not None or range_str is not None))

    log_step(
        ctx.run_id,
        "check_team_size",
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
check_team_size = check
