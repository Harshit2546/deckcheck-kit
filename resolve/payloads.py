"""Reads the few identity fields out of Crustdata company and person payloads; everything else is ignored.

Who calls it: resolve/entities.py and checkers/founder_background.py. What it calls: resolve/names.py.
Shapes follow docs/crustdata_fields.md (matches[].company_data, matches[].person_data, profiles[]) and are
NOT yet verified against a live response (T02 pending): every lookup is tolerant and returns "nothing" on a miss.
Only ids, names, domains, profile URLs and employer ids are kept; contact fields are never read.
"""

from __future__ import annotations

from typing import Any

from resolve.names import normalize_domain, normalize_url


def _get(node: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str | None:
    return str(value).strip() if value not in (None, "") else None


def _records(payload: Any, *wrappers: str) -> list[dict[str, Any]]:
    """Candidate records: matches[].<wrapper>, profiles[], a list of records, or the payload itself."""
    if not isinstance(payload, dict):
        return []
    out: list[dict[str, Any]] = []
    for match in _as_list(payload.get("matches")):
        if isinstance(match, dict):
            inner = next((match[w] for w in wrappers if isinstance(match.get(w), dict)), match)
            out.append(inner)
    out += [p for p in _as_list(payload.get("profiles")) if isinstance(p, dict)]
    if not out:
        inner = next((payload[w] for w in wrappers if isinstance(payload.get(w), dict)), payload)
        if any(k in inner for k in ("basic_info", "basic_profile", "crustdata_company_id", "crustdata_person_id")):
            out.append(inner)
    return out


def company_candidates(payload: Any) -> list[dict[str, Any]]:
    """[{id, name, domains, founder_ids, founder_names}] for each company record in the payload."""
    result = []
    for rec in _records(payload, "company_data"):
        domains = {normalize_domain(_get(rec, "basic_info", "primary_domain"))}
        domains |= {normalize_domain(d) for d in _as_list(_get(rec, "basic_info", "all_domains"))}
        founders = [f for f in _as_list(_get(rec, "people", "founders")) if isinstance(f, dict)]
        result.append({
            "id": _text(rec.get("crustdata_company_id")),
            "name": _text(_get(rec, "basic_info", "name")),
            "domains": domains - {""},
            "founder_ids": {_text(f.get("crustdata_person_id")) for f in founders} - {None},
            "founder_names": [n for n in (_text(_get(f, "basic_profile", "name")) for f in founders) if n],
        })
    return result


def person_records(payload: Any) -> list[dict[str, Any]]:
    """Raw person records (matches[].person_data or profiles[]) as sources.crust returns them (D18)."""
    return _records(payload, "person_data")


def person_candidates(payload: Any) -> list[dict[str, Any]]:
    """[{id, name, profile_url, company_ids, company_names}] for each person record in the payload."""
    result = []
    for rec in _records(payload, "person_data"):
        details = _get(rec, "experience", "employment_details")
        roles: list[Any] = []
        if isinstance(details, dict):
            roles = _as_list(details.get("current")) + _as_list(details.get("past"))
        elif isinstance(details, list):
            roles = details
        roles = [r for r in roles if isinstance(r, dict)]
        url = _get(rec, "social_handles", "professional_network_identifier", "profile_url")
        result.append({
            "id": _text(rec.get("crustdata_person_id")),
            "name": _text(_get(rec, "basic_profile", "name")),
            "profile_url": normalize_url(url) or None,
            "company_ids": {_text(r.get("crustdata_company_id")) for r in roles} - {None},
            "company_names": [n for n in (_text(r.get("name")) for r in roles) if n],
        })
    return result
