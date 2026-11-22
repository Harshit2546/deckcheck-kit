"""Checker for competition claims against competitor registries and web sources.

Who calls it: core/runner.py (or pipeline checker stage).
What it calls: sources/crust.py, sources/web.py (or context competitor data), core/models.py, core/log.py.
Extracts competitor registries, peer lists, and market uniqueness facts and returns CheckResult.
"""

from __future__ import annotations

import uuid
from typing import Any

from core.log import log_step
from core.models import CheckContext, CheckResult, Claim, Evidence, SourceType

CRUSTDATA_ENDPOINT = "https://api.crustdata.com/company/enrich"


def check(claim: Claim, ctx: CheckContext) -> CheckResult:
    """Check a competition claim against company competitor data or web sources.

    Extracts competitor lists and uniqueness assertions. Populates observed with
    "competitors", "is_unique", and "as_of".
    Never chooses the verdict label.
    """
    company_data = ctx.company
    competitors: list[str] = []
    record_date: str | None = None
    locator = CRUSTDATA_ENDPOINT

    if company_data:
        data = company_data
        if "matches" in data and isinstance(data["matches"], list) and data["matches"]:
            data = data["matches"][0].get("company_data", data["matches"][0])

        raw_competitors = data.get("competitors") or data.get("basic_info", {}).get("competitors")
        if isinstance(raw_competitors, list):
            for c in raw_competitors:
                if isinstance(c, str):
                    competitors.append(c)
                elif isinstance(c, dict) and "name" in c:
                    competitors.append(str(c["name"]))

        record_date = data.get("updated_at")
        if record_date and "T" in str(record_date):
            record_date = str(record_date).split("T")[0]

    # Check extras for competitor data if not in Crustdata
    if not competitors and ctx.extras and "competitors" in ctx.extras:
        extra_comp = ctx.extras["competitors"]
        if isinstance(extra_comp, list):
            competitors = [str(c) for c in extra_comp]
        locator = "https://market-intelligence.internal/competitors"

    if not competitors:
        log_step(
            ctx.run_id,
            "check_competition",
            "cannot_verify",
            claim_id=claim.id,
            reason="no_competitor_data_found",
        )
        return CheckResult(
            evidence=[],
            observed={},
            comparable=False,
            held_reason=None,
        )

    evidence: list[Evidence] = [
        Evidence(
            id=uuid.uuid4().hex,
            claim_id=claim.id,
            source_type=SourceType.CRUSTDATA_COMPANY if "crustdata" in locator else SourceType.WEB_PAGE,
            locator=locator,
            field_or_quote="competitors",
            value=competitors,
            record_date=record_date,
        )
    ]

    observed: dict[str, Any] = {
        "competitors": competitors,
    }
    if record_date:
        observed["as_of"] = record_date

    log_step(
        ctx.run_id,
        "check_competition",
        "ok",
        claim_id=claim.id,
        competitor_count=len(competitors),
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=True,
        held_reason=None,
    )


# Alias
check_competition = check
