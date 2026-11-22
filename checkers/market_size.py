"""Checker for market_size claims against market data and web sources.

Who calls it: core/runner.py (or pipeline checker stage).
What it calls: sources/web.py (or context benchmark data), core/models.py, core/log.py.
Extracts market size estimates, projections, and industry metrics and returns CheckResult.
"""

from __future__ import annotations

import uuid
from typing import Any

from core.log import log_step
from core.models import CheckContext, CheckResult, Claim, Evidence, SourceType


def check(claim: Claim, ctx: CheckContext) -> CheckResult:
    """Check a market_size claim against industry benchmarks or web sources.

    Extracts market size estimates. Populates observed with "market_size",
    "unit", "year", and "as_of".
    Never chooses the verdict label.
    """
    # Context extras may provide verified market benchmark data
    market_data = ctx.extras.get("market_data") if ctx.extras else None

    # If sources/web is available, web search could be attempted
    if not market_data:
        try:
            from sources.web import search_market_data

            market_data = search_market_data(claim.subject or claim.quote, run_id=ctx.run_id)
        except (ImportError, Exception):
            pass

    if not market_data:
        log_step(
            ctx.run_id,
            "check_market_size",
            "cannot_verify",
            claim_id=claim.id,
            reason="no_market_data_found",
        )
        return CheckResult(
            evidence=[],
            observed={},
            comparable=False,
            held_reason=None,
        )

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {}

    size_val: float | None = None
    if "market_size" in market_data and market_data["market_size"] is not None:
        try:
            size_val = float(market_data["market_size"])
        except (ValueError, TypeError):
            pass

    record_date: str | None = market_data.get("record_date") or market_data.get("year")
    locator = market_data.get("source_url") or "https://industry-benchmarks.internal/market-size"

    if size_val is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.WEB_PAGE,
                locator=locator,
                field_or_quote=str(market_data.get("quote") or "market_size"),
                value=size_val,
                record_date=str(record_date) if record_date else None,
            )
        )
        observed["market_size"] = size_val

    if "unit" in market_data:
        observed["unit"] = market_data["unit"]
    if "year" in market_data:
        observed["year"] = market_data["year"]
    if record_date:
        observed["as_of"] = str(record_date)

    comparable = bool(size_val is not None)

    log_step(
        ctx.run_id,
        "check_market_size",
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
check_market_size = check
