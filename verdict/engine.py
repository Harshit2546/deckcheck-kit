"""The verdict engine: code, not the LLM, turns a claim plus a CheckResult into a labelled Verdict (D1).

Who calls it: core/runner.py (stage `decide`, signature fixed by D7: decide(claim, result, rules) -> Verdict).
What it calls: verdict/common.py and the per-type rules (team_size.py, funding.py, founder.py);
every threshold is read from config/rules.yaml via core.config.rule and a missing key fails fast.
Order of checks and what checkers must provide are in verdict/DESIGN.md.
"""

from __future__ import annotations

from typing import Any

from core.config import rule
from core.models import (CheckResult, Claim, ClaimType, Confidence, Verdict, VerdictLabel)
from verdict import company_fact, founder, funding, hiring, prior_exit, team_growth, team_size, traction
from verdict.common import MISSING_TEXT, headcount_missing, make, num, parse_date

REQUIRED_KEYS = [
    "identity.min_signals", "tolerances.max_record_age_days", "title_levels",
    "tolerances.team_size.tolerance_pct", "tolerances.funding.tolerance_pct",
    "tolerances.founder_background.min_title_level", "tolerances.founder_background.tenure_tolerance_months",
    "verdict.supported_margin", "verdict.strong_margin", "verdict.fresh_days",
]

_HELD_MISSING = {
    "budget": "Raise limits.max_cost_inr or limits.max_credits in config/rules.yaml, then resume the run.",
    "time": "Raise limits.max_seconds in config/rules.yaml, then resume the run.",
    "timeout": "Re-run this claim; the source did not answer within limits.per_call_timeout_s.",
    "error": "Re-run this claim once the source or checker error is fixed.",
    "no_checker": "No checker exists for this claim type (cut or not built yet).",
}
_TYPES_WITH_RULES = {
    ClaimType.TEAM_SIZE: "team_size", ClaimType.FUNDING: "funding", ClaimType.FOUNDER_BACKGROUND: "founder_background",
    ClaimType.HIRING: "hiring", ClaimType.TRACTION: "traction", ClaimType.COMPANY_FACT: "company_fact",
    ClaimType.PRIOR_EXIT: "prior_exit", ClaimType.TEAM_GROWTH: "team_growth",
}


def check_rules(rules: dict[str, Any]) -> None:
    """Raise ValueError naming every key this engine needs that rules.yaml lacks (call at start-up and per decision)."""
    missing = []
    for key in REQUIRED_KEYS:
        try:
            rule(rules, key)
        except KeyError:
            missing.append(key)
    if missing:
        raise ValueError("config/rules.yaml is missing keys the verdict engine needs: " + ", ".join(missing))


def held_verdict(claim_id: str, reason: str, detail: str | None = None) -> Verdict:
    """HELD verdict for a limit, timeout or error. reason_code is the reason itself (D7)."""
    text = f"The check did not complete ({reason}); no verdict was reached."
    if detail:
        text += f" Detail: {detail}"
    return Verdict(claim_id=claim_id, label=VerdictLabel.HELD, reason_code=reason, explanation=text,
                   confidence=Confidence.LOW, missing=_HELD_MISSING.get(reason, "Re-run this claim."))


def decide(claim: Claim, result: CheckResult, rules: dict[str, Any]) -> Verdict:
    """Return the verdict for one claim. Pure and deterministic; see DESIGN.md section 2 for the order."""
    if result.held_reason:
        return held_verdict(claim.id, str(result.held_reason), result.observed.get("held_detail"))
    check_rules(rules)
    obs = result.observed
    # NOT_COMPARABLE needs an explicit reason from the checker; without evidence and reason it is just "no evidence".
    if (not result.evidence or not obs) and (result.comparable or not obs.get("not_comparable_reason")):
        return make(claim, result, None, VerdictLabel.CANNOT_VERIFY, "no_evidence", Confidence.LOW,
                    "The checker returned no dated evidence for this claim.", missing=headcount_missing(claim, result))
    early = _identity_and_comparable(claim, result, rules)
    if early is not None:
        return early
    if claim.type is ClaimType.PRIOR_EXIT:   # T29: the checker fetches the deck's own company today
        early = prior_exit.guard(claim, result)
        if early is not None:
            return early
    prepared = _prepare(claim, result, rules)
    if isinstance(prepared, Verdict):
        return prepared
    return _route(claim, result, rules, prepared)


def _identity_and_comparable(claim: Claim, result: CheckResult, rules: dict[str, Any]) -> Verdict | None:
    obs = result.observed
    ident = obs.get("identity")
    if ident == "unclear":
        return _cannot(claim, result, "identity_unclear", "The company or person could not be pinned down; a namesake is possible.")
    if ident == "not_found":
        return _cannot(claim, result, "entity_not_found", "The company or person was not found in the source.")
    if not result.comparable:
        reason = str(obs.get("not_comparable_reason") or "not_comparable")
        return make(claim, result, None, VerdictLabel.NOT_COMPARABLE, reason, Confidence.MEDIUM,
                    f"The source measures something different from the claim ({reason}).")
    signals = num(obs.get("identity_signals")) or 0
    if ident != "confirmed" or signals < rule(rules, "identity.min_signals"):
        return _cannot(claim, result, "identity_unclear",
                       f"Identity is confirmed on {int(signals)} signal(s); {rule(rules, 'identity.min_signals')} are required.")
    return None


def _cannot(claim: Claim, result: CheckResult, reason: str, text: str) -> Verdict:
    return make(claim, result, None, VerdictLabel.CANNOT_VERIFY, reason, Confidence.LOW, text)


def _max_age_days(rules: dict[str, Any], claim: Claim) -> float:
    """Oldest record that still counts: tolerances.<claim type>.max_record_age_days if set, else the global key."""
    try:
        return float(rule(rules, f"tolerances.{claim.type.value}.max_record_age_days"))
    except KeyError:
        return float(rule(rules, "tolerances.max_record_age_days"))


def _prepare(claim: Claim, result: CheckResult, rules: dict[str, Any]) -> dict[str, Any] | Verdict:
    """Dates, freshness, tolerance and confidence ceiling shared by all rules; or an early Verdict."""
    obs = result.observed
    rec = parse_date(obs.get("record_date"))
    if rec is None:
        return _cannot(claim, result, "missing_record_date", "The source gives no date for the record used.")
    ref = parse_date(obs.get("reference_date")) or parse_date(claim.as_of)
    if ref is None:
        return _cannot(claim, result, "no_reference_date", "Neither the claim nor the deck gives a date to compare the record with.")
    if rec > ref:   # D3: no fact from after the as-of date may support or contradict a claim
        return make(claim, result, None, VerdictLabel.NOT_COMPARABLE, "record_after_as_of", Confidence.HIGH,
                    f"The record is dated {rec}, after the date the claim refers to ({ref}); it cannot support or "
                    "contradict the claim.", missing=f"A record dated on or before {ref}.")
    gap = (ref - rec).days
    if gap > _max_age_days(rules, claim):
        return make(claim, result, None, VerdictLabel.NOT_COMPARABLE, "stale_record", Confidence.MEDIUM,
                    f"The record is dated {rec}, {gap} days before the claim's date {ref}; too far apart to compare.")
    ceiling = Confidence.MEDIUM if obs.get("reference_date_source") in ("pdf_metadata", "missing") else Confidence.HIGH
    tol_key = _TYPES_WITH_RULES.get(claim.type)
    tol = (rule(rules, f"tolerances.{tol_key}.tolerance_pct") / 100) if tol_key and tol_key != "founder_background" else 0.0
    return {
        "rec": rec, "ref": ref, "gap": gap, "ceiling": ceiling, "tol": tol,
        "fresh": gap <= rule(rules, "verdict.fresh_days"),
        "supported_margin": float(rule(rules, "verdict.supported_margin")),
        "strong_margin": float(rule(rules, "verdict.strong_margin")),
    }


def _route(claim: Claim, result: CheckResult, rules: dict[str, Any], st: dict[str, Any]) -> Verdict:
    if claim.type is ClaimType.TEAM_SIZE and (claim.metric or "headcount").strip().lower() == "headcount":
        return team_size.judge(claim, result, st)
    if claim.type is ClaimType.FUNDING:
        return funding.judge(claim, result, st)
    if claim.type is ClaimType.FOUNDER_BACKGROUND:
        return founder.judge(claim, result, rules, st)
    if claim.type is ClaimType.HIRING:
        return hiring.judge(claim, result, st)
    if claim.type is ClaimType.TRACTION:
        return traction.judge(claim, result, st)
    if claim.type is ClaimType.COMPANY_FACT:
        return company_fact.judge(claim, result, rules, st)
    if claim.type is ClaimType.PRIOR_EXIT:
        return prior_exit.judge(claim, result, st)
    if claim.type is ClaimType.TEAM_GROWTH:
        return team_growth.judge(claim, result, rules, st)
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "unsupported_metric", Confidence.LOW,
                f"No verdict rule exists yet for {claim.type.value} / {claim.metric!r}.")


__all__ = ["decide", "held_verdict", "check_rules", "REQUIRED_KEYS", "MISSING_TEXT"]
