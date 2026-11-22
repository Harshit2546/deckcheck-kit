"""Checker for founder_background claims (past_employer, title, tenure_years) against Crustdata (D18).

Who calls it: core/runner.py (STAGES["check"]).
What it calls: resolve.names.find_founder (the founder resolve confirmed), sources.crust get_people /
search_people (the same cached call resolve made), resolve.payloads.person_records, core/models.py, core/log.py.
Reads the founder's OWN person record (employer, title, start/end dates); identity is the founder entity's.
Strictly professional fields only: never stores or emits emails, phone numbers, or addresses.
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
from resolve import payloads
from resolve.names import find_founder, normalize_url
from sources import crust

CRUSTDATA_PERSON_ENDPOINT = "https://api.crustdata.com/person/enrich"
CRUSTDATA_PERSON_SEARCH_ENDPOINT = "https://api.crustdata.com/person/search"


def _normalize_name(name: str | None) -> str:
    """Normalize company or person name for loose matching."""
    if not name:
        return ""
    text = re.sub(r"[^\w\s]", "", str(name).lower())
    # Strip common corporate designations
    for suffix in [" pvt ltd", " ltd", " inc", " corp", " llc", " co"]:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text.strip()


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


def _founder_record(ctx: RunContext, founder: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None, str]:
    """(person record whose id is the founder entity's id, call_id, endpoint). Same call as resolve, so cached."""
    if founder.get("profile_url"):
        urls = list(dict.fromkeys(u for u in ctx.run.input.founder_urls if normalize_url(u)))
        if normalize_url(founder["profile_url"]) not in {normalize_url(u) for u in urls}:
            urls.append(founder["profile_url"])
        payload, call_id = crust.get_people(ctx, urls)
        endpoint = CRUSTDATA_PERSON_ENDPOINT
    else:
        company_id = ((ctx.entities or {}).get("company") or {}).get("id")
        payload, call_id = crust.search_people(ctx, founder.get("name") or "", company_id or "")
        endpoint = CRUSTDATA_PERSON_SEARCH_ENDPOINT
    wanted = str(founder.get("id") or "")
    for rec in payloads.person_records(payload):
        if wanted and str(rec.get("crustdata_person_id") or "") == wanted:
            return rec, call_id, endpoint
    return None, call_id, endpoint


def _extract_positions(person: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract strictly professional position dicts (employer, title, start_date, end_date)."""
    raw_positions: list[dict[str, Any]] = []

    exp = person.get("experience") or {}
    if isinstance(exp, dict):
        emp_details = exp.get("employment_details") or {}
        if isinstance(emp_details, dict):
            for role_list in [emp_details.get("current"), emp_details.get("past")]:
                if isinstance(role_list, list):
                    raw_positions.extend(r for r in role_list if isinstance(r, dict))
        pos_list = exp.get("positions") or exp.get("jobs")
        if isinstance(pos_list, list):
            raw_positions.extend(r for r in pos_list if isinstance(r, dict))
    elif isinstance(exp, list):
        raw_positions.extend(r for r in exp if isinstance(r, dict))

    direct_pos = person.get("positions") or person.get("employment_history")
    if isinstance(direct_pos, list):
        raw_positions.extend(r for r in direct_pos if isinstance(r, dict))

    cleaned: list[dict[str, Any]] = []
    for r in raw_positions:
        emp = r.get("employer") or r.get("company_name") or r.get("company") or r.get("name")
        if not emp:
            continue
        title = r.get("title") or r.get("role") or r.get("designation") or ""
        start = r.get("start_date") or r.get("from")
        end = r.get("end_date") or r.get("to")

        cleaned.append({
            "employer": str(emp).strip(),
            "title": str(title).strip() if title else "",
            "start_date": str(start).split("T")[0] if start else None,
            "end_date": str(end).split("T")[0] if end else None,
        })

    return cleaned


def check(claim: Claim, ctx: RunContext) -> CheckResult:
    """Check a founder_background claim against Crustdata person/company data.

    Populates observed per verdict/DESIGN.md section 3.3:
    'identity', 'identity_signals', 'record_date', 'reference_date',
    'reference_date_source', 'employer_found', 'positions', 'title_observed'.
    """
    founder = find_founder(ctx.entities, claim.subject)
    identity = {
        "identity": founder.get("identity", "unclear") if founder else "not_found",
        "identity_signals": int(founder.get("identity_signals", 0)) if founder else 0,
    }
    person: dict[str, Any] | None = None
    call_id: str | None = None
    endpoint = CRUSTDATA_PERSON_ENDPOINT
    if founder and founder.get("identity") == "confirmed" and founder.get("id"):
        person, call_id, endpoint = _founder_record(ctx, founder)

    updated = None
    if person:
        updated = person.get("updated_at") or (person.get("basic_profile") or {}).get("last_updated")
    rec_date, ref_date, ref_source = _get_dates(claim, ctx, updated)

    if not person:
        reason = "founder_not_resolved" if not founder or founder.get("identity") != "confirmed" else "no_record"
        log_step(ctx.run.id, claim.id, "check.founder_background", "cannot_verify", reason=reason)
        return CheckResult(
            evidence=[],
            observed={
                **identity,
                "record_date": rec_date,
                "reference_date": ref_date,
                "reference_date_source": ref_source,
            },
            comparable=True,
            held_reason=None,
        )

    all_positions = _extract_positions(person) if person else []

    # Determine which employer to match
    target_employer = ""
    metric = (claim.metric or "").strip().lower()
    if metric == "past_employer" and claim.value:
        target_employer = str(claim.value).strip()
    else:
        # Search for employer mentioned in claim.quote or claim.subject
        quote_lower = (claim.quote or "").lower()
        for pos in all_positions:
            emp_norm = _normalize_name(pos["employer"])
            if emp_norm and emp_norm in quote_lower:
                target_employer = pos["employer"]
                break
        if not target_employer and all_positions:
            # If all positions belong to one employer or claim.value matches
            target_employer = all_positions[0]["employer"]

    target_norm = _normalize_name(target_employer)
    matched_positions: list[dict[str, Any]] = []

    if target_norm:
        for pos in all_positions:
            pos_norm = _normalize_name(pos["employer"])
            if target_norm in pos_norm or pos_norm in target_norm:
                matched_positions.append(pos)

    employer_found = len(matched_positions) > 0

    # Pick observed title from matched employer roles
    title_observed: str | None = None
    if employer_found:
        # Prefer position with latest end date or ongoing (None end_date)
        ongoing = [p for p in matched_positions if p.get("end_date") is None]
        if ongoing and ongoing[0].get("title"):
            title_observed = ongoing[0]["title"]
        else:
            sorted_pos = sorted(
                matched_positions,
                key=lambda p: str(p.get("end_date") or p.get("start_date") or ""),
                reverse=True,
            )
            title_observed = sorted_pos[0].get("title") or None

    evidence: list[Evidence] = []
    if person:
        if employer_found:
            evidence.append(
                Evidence(
                    id=uuid.uuid4().hex,
                    claim_id=claim.id,
                    source_type=SourceType.CRUSTDATA_PERSON,
                    locator=endpoint,
                    field_or_quote=f"experience.employment_details[{target_employer}]",
                    value=[
                        {
                            "employer": p["employer"],
                            "title": p["title"],
                            "start_date": p["start_date"],
                            "end_date": p["end_date"],
                        }
                        for p in matched_positions
                    ],
                    record_date=rec_date,
                    retrieved_at=now_iso(),
                    call_id=call_id,
                )
            )
        else:
            evidence.append(
                Evidence(
                    id=uuid.uuid4().hex,
                    claim_id=claim.id,
                    source_type=SourceType.CRUSTDATA_PERSON,
                    locator=endpoint,
                    field_or_quote="experience.employment_details",
                    value=[],
                    record_date=rec_date,
                    retrieved_at=now_iso(),
                    call_id=call_id,
                )
            )

    observed: dict[str, Any] = {
        **identity,
        "record_date": rec_date,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
        "employer_found": employer_found,
        "positions": matched_positions,
        "title_observed": title_observed,
    }

    log_step(
        ctx.run.id,
        claim.id,
        "check.founder_background",
        "ok",
        employer_found=employer_found,
        evidence_count=len(evidence),
    )

    return CheckResult(
        evidence=evidence,
        observed=observed,
        comparable=True,
        held_reason=None,
    )
