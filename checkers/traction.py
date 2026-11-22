"""Checker for traction claims (revenue, ARR, growth rate) against company data.

Who calls it: core/runner.py (or pipeline checker stage).
What it calls: sources/crust.py (or context company data), core/models.py, core/log.py.
Extracts annual revenue, ARR, growth rate, and operational traction metrics and returns CheckResult.
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
    """Check a traction claim against Crustdata company data.

    Extracts revenue, ARR, and growth rate. Populates observed with
    "revenue", "arr", "growth_rate", and "as_of".
    Never chooses the verdict label.
    """
    company_data, held_reason = _get_company_data(ctx)
    if held_reason is not None:
        log_step(
            ctx.run_id,
            "check_traction",
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
            "check_traction",
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

    record_date: str | None = data.get("updated_at")
    if record_date and "T" in str(record_date):
        record_date = str(record_date).split("T")[0]

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {}

    if annual_revenue is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="revenue.annual_revenue_usd",
                value=annual_revenue,
                record_date=record_date,
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
                record_date=record_date,
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
                record_date=record_date,
            )
        )
        observed["growth_rate"] = growth_rate

    if record_date:
        observed["as_of"] = record_date

    comparable = bool(annual_revenue is not None or arr_val is not None or growth_rate is not None)

    log_step(
        ctx.run_id,
        "check_traction",
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
check_traction = check
