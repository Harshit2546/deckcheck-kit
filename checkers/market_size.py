"""Checker for market_size claims against market data and web sources.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: sources.web (search_market_data), core/models.py, core/log.py.
Extracts market size estimates, projections, and industry metrics and returns CheckResult.
"""

from __future__ import annotations

import re
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
    """Check a market_size claim against industry benchmarks or web sources."""
    rec_date, ref_date, ref_source = _get_dates(claim, ctx, None)

    # Missing module, errors and timeouts propagate: the runner turns them into HELD (D7).
    from sources.web import search_market_data

    market_data = search_market_data(ctx, claim.subject or claim.quote)

    if not market_data:
        log_step(ctx.run.id, claim.id, "check.market_size", "cannot_verify", reason="no_market_data")
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

    evidence: list[Evidence] = []

    size_val: float | None = None
    if "market_size" in market_data and market_data["market_size"] is not None:
        try:
            size_val = float(market_data["market_size"])
        except (ValueError, TypeError):
            pass

    record_date: str | None = market_data.get("record_date") or market_data.get("year") or rec_date
    locator = market_data.get("source_url")
    if not locator:  # no source, no fact (AGENTS.md): the engine returns CANNOT_VERIFY no_evidence
        log_step(ctx.run.id, claim.id, "check.market_size", "cannot_verify", reason="no_source_url")
        return CheckResult(evidence=[], observed={}, comparable=True, held_reason=None)

    observed: dict[str, Any] = {
        # A market has no company or person to resolve, so there is no namesake risk here.
        "identity": "confirmed",
        "identity_signals": 2,
        "record_date": str(record_date) if record_date else None,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
    }

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
                retrieved_at=now_iso(),
                call_id=market_data.get("call_id"),
            )
        )
        observed["market_size"] = size_val

    if "unit" in market_data:
        observed["unit"] = market_data["unit"]
    if "year" in market_data:
        observed["year"] = market_data["year"]

    log_step(
        ctx.run.id,
        claim.id,
        "check.market_size",
        "ok",
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=True,
        held_reason=None,
    )
