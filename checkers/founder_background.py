"""Checker for founder_background claims (past_employer, title, tenure_years) against Crustdata.

Who calls it: core/runner.py (STAGES["check"]).
What it calls: checkers._common (get_company, company_identity), core/models.py, core/log.py.
Extracts professional employment history (employer, title, start/end dates) and returns CheckResult.
Strictly professional fields only: never stores or emits emails, phone numbers, or addresses.
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

CRUSTDATA_PERSON_ENDPOINT = "https://api.crustdata.com/person/enrich"


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


def _extract_candidates(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Find person / founder candidate dicts in the company or person payload."""
    candidates: list[dict[str, Any]] = []

    # Case 1: data has 'people.founders' or 'founders' or 'people' list
    people_obj = data.get("people") or {}
    if isinstance(people_obj, dict):
        founders = people_obj.get("founders") or people_obj.get("people") or []
        if isinstance(founders, list):
            candidates.extend(f for f in founders if isinstance(f, dict))
    elif isinstance(people_obj, list):
        candidates.extend(p for p in people_obj if isinstance(p, dict))

    raw_founders = data.get("founders")
    if isinstance(raw_founders, list):
        candidates.extend(f for f in raw_founders if isinstance(f, dict))

    # Case 2: data has 'matches' with person_data or company_data
    matches = data.get("matches")
    if isinstance(matches, list):
        for m in matches:
            if isinstance(m, dict):
                if "person_data" in m and isinstance(m["person_data"], dict):
                    candidates.append(m["person_data"])
                elif "company_data" in m and isinstance(m["company_data"], dict):
                    cd = m["company_data"]
                    cd_people = cd.get("people") or cd.get("founders") or []
                    if isinstance(cd_people, dict):
                        candidates.extend(f for f in cd_people.get("founders", []) if isinstance(f, dict))
                    elif isinstance(cd_people, list):
                        candidates.extend(f for f in cd_people if isinstance(f, dict))

    # Case 3: data is itself a person record with 'experience' or 'positions'
    if data.get("experience") or data.get("positions") or data.get("basic_profile"):
        candidates.append(data)

    return candidates


def _find_person(candidates: list[dict[str, Any]], subject: str) -> dict[str, Any] | None:
    """Find person matching claim subject (by name or single candidate)."""
    if not candidates:
        return None

    subj_norm = _normalize_name(subject)
    for c in candidates:
        name = ""
        bp = c.get("basic_profile") or {}
        if isinstance(bp, dict) and bp.get("name"):
            name = str(bp["name"])
        elif c.get("name"):
            name = str(c["name"])

        c_norm = _normalize_name(name)
        if subj_norm and (subj_norm in c_norm or c_norm in subj_norm):
            return c

    # Fall back to single candidate if available
    return candidates[0] if len(candidates) == 1 else None


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
    domain = ctx.run.input.domain
    payload, call_id = _common.get_company(ctx, domain)

    rec_date, ref_date, ref_source = _get_dates(claim, ctx, payload.get("updated_at") if payload else None)

    if not payload:
        log_step(ctx.run.id, claim.id, "check.founder_background", "cannot_verify", reason="no_payload")
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

    candidates = _extract_candidates(payload)
    person = _find_person(candidates, claim.subject)

    if person and person.get("updated_at") and not rec_date:
        rec_date = str(person["updated_at"]).split("T")[0]

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
                    locator=CRUSTDATA_PERSON_ENDPOINT,
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
                    locator=CRUSTDATA_PERSON_ENDPOINT,
                    field_or_quote="experience.employment_details",
                    value=[],
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
