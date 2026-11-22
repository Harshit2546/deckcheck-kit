"""Checker for prior_exit claims against live Crustdata company data.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: checkers._common (get_company, company_identity), core/models.py, core/log.py.
Extracts acquisition status, acquirer, transaction amount, and exit date and returns CheckResult.
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
    """Check a prior_exit claim against Crustdata company data."""
    domain = ctx.run.input.domain
    payload, call_id = _common.get_company(ctx, domain)

    rec_date, ref_date, ref_source = _get_dates(claim, ctx, payload.get("updated_at") if payload else None)

    if not payload:
        log_step(ctx.run.id, claim.id, "check.prior_exit", "cannot_verify", reason="no_payload")
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

    if not rec_date and data.get("updated_at"):
        rec_date = str(data["updated_at"]).split("T")[0]

    revenue_obj = data.get("revenue") or {}
    funding_obj = data.get("funding") or {}
    basic_info = data.get("basic_info") or {}

    acq_status = (
        revenue_obj.get("acquisition_status")
        or data.get("acquisition_status")
        or basic_info.get("status")
    )

    raw_acquisitions = funding_obj.get("acquisitions") or data.get("acquisitions") or []
    acquisitions: list[dict[str, Any]] = []
    if isinstance(raw_acquisitions, list):
        for acq in raw_acquisitions:
            if isinstance(acq, dict):
                acquirer = acq.get("acquirer_name") or acq.get("buyer") or acq.get("acquired_by")
                amt = acq.get("amount_usd") if acq.get("amount_usd") is not None else acq.get("price")
                d = acq.get("date") or acq.get("acquisition_date")
                acquisitions.append({
                    "acquired_by": str(acquirer).strip() if acquirer else None,
                    "amount_usd": float(amt) if amt is not None else None,
                    "date": str(d).split("T")[0] if d else None,
                })

    exit_found = bool(
        acquisitions
        or (isinstance(acq_status, str) and acq_status.lower() in ("acquired", "subsidiary", "sold"))
    )

    acquired_by: str | None = None
    exit_amount: float | None = None
    exit_date: str | None = None

    if acquisitions:
        first = acquisitions[0]
        acquired_by = first.get("acquired_by")
        exit_amount = first.get("amount_usd")
        exit_date = first.get("date")
        if exit_date and not rec_date:
            rec_date = exit_date

    evidence: list[Evidence] = []
    if exit_found:
        evidence.append(
            Evidence(
                id=uuid.uuid4().hex,
                claim_id=claim.id,
                source_type=SourceType.CRUSTDATA_COMPANY,
                locator=CRUSTDATA_ENDPOINT,
                field_or_quote="funding.acquisitions",
                value={"status": acq_status, "acquisitions": acquisitions},
                record_date=rec_date,
                retrieved_at=now_iso(),
                call_id=call_id,
            )
        )

    observed: dict[str, Any] = {
        **_common.company_identity(ctx),
        "record_date": rec_date,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
        "exit_found": exit_found,
        "acquisition_status": acq_status,
        "acquisitions": acquisitions,
        "acquired_by": acquired_by,
        "exit_amount": exit_amount,
        "exit_date": exit_date,
    }

    log_step(
        ctx.run.id,
        claim.id,
        "check.prior_exit",
        "ok",
        exit_found=exit_found,
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=True,
        held_reason=None,
    )
