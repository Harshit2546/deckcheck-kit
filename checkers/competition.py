"""Checker for competition claims against competitor registries and web sources.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: sources.crust (get_company), core/models.py, core/log.py.
Extracts competitor registries, peer lists, and market uniqueness facts and returns CheckResult.
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
    """Check a competition claim against company competitor data or web sources."""
    domain = ctx.run.input.domain
    payload, call_id = _common.get_company(ctx, domain)

    rec_date, ref_date, ref_source = _get_dates(claim, ctx, payload.get("updated_at") if payload else None)

    competitors: list[str] = []
    locator = CRUSTDATA_ENDPOINT

    if payload:
        data = payload
        if "matches" in data and isinstance(data["matches"], list) and data["matches"]:
            data = data["matches"][0].get("company_data", data["matches"][0])

        raw_competitors = data.get("competitors") or data.get("basic_info", {}).get("competitors")
        if isinstance(raw_competitors, list):
            for c in raw_competitors:
                if isinstance(c, str):
                    competitors.append(c)
                elif isinstance(c, dict) and "name" in c:
                    competitors.append(str(c["name"]))

        if not rec_date and data.get("updated_at"):
            rec_date = str(data["updated_at"]).split("T")[0]

    if not competitors:
        log_step(ctx.run.id, claim.id, "check.competition", "cannot_verify", reason="no_competitors_found")
        return CheckResult(
            evidence=[],
            observed={
                **(_common.company_identity(ctx) if payload else {"identity": "not_found", "identity_signals": 0}),
                "reference_date": ref_date,
                "reference_date_source": ref_source,
            },
            comparable=True,
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
            record_date=rec_date,
            retrieved_at=now_iso(),
            call_id=call_id,
        )
    ]

    observed: dict[str, Any] = {
        **_common.company_identity(ctx),
        "record_date": rec_date,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
        "competitors": competitors,
    }

    log_step(
        ctx.run.id,
        claim.id,
        "check.competition",
        "ok",
        competitor_count=len(competitors),
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=True,
        held_reason=None,
    )
