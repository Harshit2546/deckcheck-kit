"""Resolve stage: decides which company and which people the deck means, using the two-signal rule (T10).

Who calls it: core/runner.py (stage `resolve`, D7: run(ctx, claims) -> dict, saved in the `resolutions` table).
What it calls: sources/crust.py (get_company, get_people, search_people; built by codex-a), resolve/payloads.py,
resolve/names.py, core.config.rule for `identity.min_signals`. Source errors (limit, timeout, failure) are NOT caught:
the runner stops the run in its state and a resume repeats this stage, so nothing is mislabelled "unclear".
Output holds ids, identity, signal counts and signal codes only: no raw payloads, no contact fields.
"""

from __future__ import annotations

from typing import Any

from core.config import rule
from core.log import log_step
from core.models import Claim, ClaimType, RunContext
from resolve import payloads
from resolve.names import (company_names_match, is_profile_url, normalize_domain, normalize_url,
                           person_key, person_names_match)

FOUNDER_TYPES = {ClaimType.FOUNDER_BACKGROUND, ClaimType.PRIOR_EXIT}


def _crust() -> Any:
    """sources.crust, imported at call time (lane codex-a); a missing module raises and the run waits."""
    import sources.crust as crust

    return crust


def _confidence(signals: int, minimum: int) -> str:
    """high: more signals than required; medium: exactly the required number; low: fewer."""
    return "high" if signals > minimum else "medium" if signals == minimum else "low"


def _entity(ident: str, signals: list[str], minimum: int, *, id: str | None = None, name: str | None = None,
            profile_url: str | None = None, reason: str | None = None, call_id: str | None = None) -> dict[str, Any]:
    entity: dict[str, Any] = {"id": id, "identity": ident, "identity_signals": len(signals),
                              "confidence": _confidence(len(signals), minimum), "signals": signals,
                              "reason": reason, "call_id": call_id}
    if name is not None or profile_url is not None:
        entity.update({"name": name, "profile_url": profile_url})
    return entity


def _deck_names(claims: list[Claim]) -> tuple[list[str], list[str]]:
    """(company names, founder names) as the deck states them, in claim order, without duplicates."""
    companies: list[str] = []
    founders: list[str] = []
    for claim in claims:
        subject = (claim.subject or "").strip()
        if not subject:
            continue
        bucket = founders if claim.type in FOUNDER_TYPES else companies
        if subject not in bucket:
            bucket.append(subject)
    return companies, founders


def _company_signals(cand: dict[str, Any], domain: str, deck_companies: list[str],
                     deck_founders: list[str]) -> list[str]:
    signals = ["domain"] if domain in cand["domains"] else []
    if any(company_names_match(cand["name"], n) for n in deck_companies):
        signals.append("name")
    if any(person_names_match(f, n) for f in cand["founder_names"] for n in deck_founders):
        signals.append("founder")
    return signals


def resolve_company(ctx: RunContext, minimum: int, deck_companies: list[str],
                    deck_founders: list[str]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """(company entity, the matched provider candidate or None). One call to sources.crust.get_company."""
    domain = normalize_domain(ctx.run.input.domain)
    payload, call_id = _crust().get_company(ctx, domain)
    cands = payloads.company_candidates(payload)
    if not cands:
        return _entity("not_found", [], minimum, reason="no_match", call_id=call_id), None
    scored = [(c, _company_signals(c, domain, deck_companies, deck_founders)) for c in cands]
    scored = [(c, s) for c, s in scored if "domain" in s]
    if not scored:
        return _entity("not_found", [], minimum, reason="domain_mismatch", call_id=call_id), None
    if len({c["id"] for c, _ in scored}) > 1:
        best = max(scored, key=lambda cs: len(cs[1]))
        return _entity("unclear", best[1], minimum, reason="multiple_candidates", call_id=call_id), None
    cand, signals = scored[0]
    if cand["id"] is None:
        return _entity("unclear", signals, minimum, reason="no_company_id", call_id=call_id), cand
    ident = "confirmed" if len(signals) >= minimum else "unclear"
    reason = None if ident == "confirmed" else "too_few_signals"
    return _entity(ident, signals, minimum, id=cand["id"], reason=reason, call_id=call_id), cand


def _person_signals(cand: dict[str, Any], company: dict[str, Any], company_cand: dict[str, Any] | None,
                    deck_name: str | None) -> list[str]:
    signals = ["name"] if deck_name and person_names_match(cand["name"], deck_name) else []
    cid = company.get("id")
    if cid and cid in cand["company_ids"]:
        signals.append("employer")
    if company_cand and cand["id"] and cand["id"] in company_cand["founder_ids"]:
        signals.append("company_founder_list")
    return signals


def _from_urls(ctx: RunContext, urls: list[str], minimum: int, company: dict[str, Any],
               company_cand: dict[str, Any] | None, deck_founders: list[str]) -> tuple[list[dict[str, Any]], set[frozenset[str]]]:
    """Founders given by profile URL (one batched call). Returns (entities, deck-name keys already matched)."""
    payload, call_id = _crust().get_people(ctx, urls)
    by_url = {c["profile_url"]: c for c in payloads.person_candidates(payload) if c["profile_url"]}
    entities: list[dict[str, Any]] = []
    matched: set[frozenset[str]] = set()
    for url in urls:
        cand = by_url.get(normalize_url(url))
        if cand is None:
            entities.append(_entity("not_found", [], minimum, profile_url=url, reason="url_not_returned", call_id=call_id))
            continue
        deck_name = next((n for n in deck_founders if person_names_match(cand["name"], n)), None)
        signals = ["profile_url"] + _person_signals(cand, company, company_cand, deck_name)
        ident = "confirmed" if len(signals) >= minimum else "unclear"
        if deck_name:
            matched.add(person_key(deck_name))
        entities.append(_entity(ident, signals, minimum, id=cand["id"], name=deck_name, profile_url=url,
                                reason=None if ident == "confirmed" else "too_few_signals", call_id=call_id))
    return entities, matched


def _by_search(ctx: RunContext, name: str, minimum: int, company: dict[str, Any],
               company_cand: dict[str, Any] | None) -> dict[str, Any]:
    """One founder found by name and employer. A namesake without the company link never qualifies."""
    if not person_key(name):
        return _entity("unclear", [], minimum, name=name, reason="name_incomplete")
    if company.get("identity") != "confirmed":
        return _entity("unclear", [], minimum, name=name, reason="company_unresolved")
    payload, call_id = _crust().search_people(ctx, name, company["id"])
    scored = [(c, _person_signals(c, company, company_cand, name)) for c in payloads.person_candidates(payload)]
    named = [(c, s) for c, s in scored if "name" in s]
    if not named:
        reason = "no_candidates" if not scored else "no_name_match"
        return _entity("not_found", [], minimum, name=name, reason=reason, call_id=call_id)
    qualifying = [(c, s) for c, s in named if len(s) >= minimum]
    if len({c["id"] for c, _ in qualifying}) == 1:
        cand, signals = qualifying[0]
        return _entity("confirmed", signals, minimum, id=cand["id"], name=name, call_id=call_id)
    best = max(named, key=lambda cs: len(cs[1]))[1]
    reason = "multiple_candidates" if qualifying else "namesake_or_weak_match"
    return _entity("unclear", best, minimum, name=name, reason=reason, call_id=call_id)


def run(ctx: RunContext, claims: list[Claim]) -> dict[str, Any]:
    """Resolve the company by domain, then every founder named in the deck or given as a profile URL."""
    minimum = int(rule(ctx.rules, "identity.min_signals"))
    deck_companies, deck_founders = _deck_names(claims)
    company, company_cand = resolve_company(ctx, minimum, deck_companies, deck_founders)
    log_step(ctx.run.id, None, "resolve.company", company["identity"], signals=company["identity_signals"],
             reason=company["reason"])

    urls = list(dict.fromkeys(u for u in ctx.run.input.founder_urls if is_profile_url(u)))
    founders: list[dict[str, Any]] = []
    matched: set[frozenset[str]] = set()
    if urls:
        founders, matched = _from_urls(ctx, urls, minimum, company, company_cand, deck_founders)
    for name in deck_founders:
        if person_key(name) and person_key(name) in matched:
            continue
        founders.append(_by_search(ctx, name, minimum, company, company_cand))
    for f in founders:
        log_step(ctx.run.id, None, "resolve.founder", f["identity"], signals=f["identity_signals"], reason=f["reason"])
    return {"company": company, "founders": founders}
