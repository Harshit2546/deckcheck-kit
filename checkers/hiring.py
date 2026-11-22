"""Checker for hiring claims against live Crustdata company data.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: sources.crust (get_company), core/models.py, core/log.py.
Extracts active openings_count, openings_growth_percent, and open roles and returns CheckResult.
These are snapshot values with no record date: `updated_at` is the provider's refresh date, not
the record's own date (D13), so Evidence and observed record_date are None (D17 decides use).
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

from checkers import _common

CRUSTDATA_ENDPOINT = "https://api.crustdata.com/company/enrich"


def _reference_date(claim: Claim, ctx: RunContext) -> tuple[str | None, str]:
    """(reference_date, reference_date_source): claim.as_of if ISO, else the deck date."""
    ref_date = None
    if claim.as_of and re.match(r"^\d{4}-\d{2}-\d{2}$", claim.as_of.strip()):
        ref_date = claim.as_of.strip()
    elif ctx.run.input.deck_date:
        ref_date = ctx.run.input.deck_date.strip()[:10]
    return ref_date, ctx.run.input.deck_date_source or "input"


def check(claim: Claim, ctx: RunContext) -> CheckResult:
    """Check a hiring claim against Crustdata company data."""
    domain = ctx.run.input.domain
    payload, call_id = _common.get_company(ctx, domain)

    ref_date, ref_source = _reference_date(claim, ctx)

    if not payload:
        log_step(ctx.run.id, claim.id, "check.hiring", "cannot_verify", reason="no_payload")
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

    evidence: list[Evidence] = []
    observed: dict[str, Any] = {
        **_common.company_identity(ctx),
        "record_date": None,   # snapshot values; updated_at is never a record date (D13)
        "reference_date": ref_date,
        "reference_date_source": ref_source,
        "undated_items_used": 0,
    }

    if openings_count is not None:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_JOB,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="hiring.openings_count",
                value=openings_count,
                record_date=None,
                retrieved_at=now_iso(),
                call_id=call_id,
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
                record_date=None,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )
        observed["growth_percent"] = growth_percent

    if openings:
        observed["openings"] = openings
    observed["undated_items_used"] = len(evidence)

    log_step(
        ctx.run.id,
        claim.id,
        "check.hiring",
        "ok",
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=True,
        held_reason=None,
    )
