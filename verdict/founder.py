"""Verdict rules for founder_background claims: past_employer, title and tenure_years (DESIGN.md section 3.3).

Who calls it: verdict/engine.py after the shared checks (identity already confirmed with enough signals).
What it calls: verdict/common.py and core.config.rule for title_levels and the founder tolerances.
Cautious by design: a missing employer in a profile is never a contradiction (profiles omit jobs).
Seniority order comes from the ORDER of title_levels in rules.yaml: first entry = most senior.
"""

from __future__ import annotations

import re
from typing import Any

from core.config import rule
from core.models import CheckResult, Claim, Confidence, Verdict, VerdictLabel
from verdict.common import make, num, parse_date, pick, source_text

METRICS = ("past_employer", "title", "tenure_years")
_DAYS_PER_MONTH = 30.4375


def judge(claim: Claim, result: CheckResult, rules: dict[str, Any], st: dict[str, Any]) -> Verdict:
    """Route by claim.metric. Any other metric is CANNOT_VERIFY (unsupported_metric)."""
    metric = (claim.metric or "").strip().lower()
    if metric == "past_employer":
        return _employer(claim, result, st)
    if metric == "title":
        return _title(claim, result, rules, st)
    if metric == "tenure_years":
        return _tenure(claim, result, rules, st)
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "unsupported_metric", Confidence.LOW,
                f"No rule exists yet for the founder metric {claim.metric!r}.")


def _employer_listed(result: CheckResult) -> bool:
    return result.observed.get("employer_found") is True


def _no_employer(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "employer_not_in_profile", Confidence.LOW,
                f"{claim.subject}'s profile in {source_text(result)} does not list the employer in the deck; "
                "profiles often omit jobs, so this is not a contradiction.")


def _employer(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    if not _employer_listed(result):
        return _no_employer(claim, result, st)
    return make(claim, result, st, VerdictLabel.SUPPORTED, "employer_listed", pick(st["fresh"]),
                f"{source_text(result)} lists {claim.subject} at {claim.value} (record {st['rec']}).")


def level_of(title: Any, levels: dict[str, list[str]]) -> int | None:
    """Index of the most senior level whose keyword appears as a whole word/phrase in title (0 = most senior)."""
    text = str(title or "").lower()
    for index, keywords in enumerate(levels.values()):
        for kw in keywords:
            if re.search(rf"(?<![a-z]){re.escape(str(kw).lower())}(?![a-z])", text):
                return index
    return None


def _title(claim: Claim, result: CheckResult, rules: dict[str, Any], st: dict[str, Any]) -> Verdict:
    observed_title = result.observed.get("title_observed")
    if not _employer_listed(result) or not observed_title:
        return _no_employer(claim, result, st)
    levels = rule(rules, "title_levels")
    claimed_rank, observed_rank = level_of(claim.value, levels), level_of(observed_title, levels)
    if claimed_rank is None or observed_rank is None:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "title_unmapped", Confidence.LOW,
                    f"Could not place '{claim.value}' or '{observed_title}' on the title levels in rules.yaml.")
    facts = f"Deck says '{claim.value}'; {source_text(result)} shows '{observed_title}' (record {st['rec']})."
    if observed_rank <= claimed_rank:
        return make(claim, result, st, VerdictLabel.SUPPORTED, "title_level_met",
                    pick(observed_rank == claimed_rank and st["fresh"]), facts)
    names = list(levels)
    threshold = rule(rules, "tolerances.founder_background.min_title_level")
    if threshold not in names:
        raise ValueError(f"config/rules.yaml: min_title_level '{threshold}' is not a key of title_levels")
    if claimed_rank > names.index(threshold):
        return make(claim, result, st, VerdictLabel.NOT_COMPARABLE, "informal_title", Confidence.LOW,
                    facts + " The claimed title is below the level checked for contradictions.")
    wide = observed_rank - claimed_rank >= 2
    return make(claim, result, st, VerdictLabel.CONTRADICTED, "title_level_lower", pick(wide and st["fresh"]), facts)


def _tenure(claim: Claim, result: CheckResult, rules: dict[str, Any], st: dict[str, Any]) -> Verdict:
    claimed_years = num(claim.value)
    if claimed_years is None or claimed_years < 0:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    f"The deck's tenure value {claim.value!r} is not a usable number of years.")
    positions = [p for p in result.observed.get("positions") or [] if isinstance(p, dict)]
    starts = [d for d in (parse_date(p.get("start_date")) for p in positions) if d]
    if not _employer_listed(result) or not starts:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "missing_dates", Confidence.LOW,
                    f"No start date for {claim.subject}'s role in {source_text(result)}.")
    ends = [parse_date(p.get("end_date")) or st["rec"] for p in positions]
    months = (max(ends) - min(starts)).days / _DAYS_PER_MONTH
    allowed = float(rule(rules, "tolerances.founder_background.tenure_tolerance_months"))
    gap = abs(months - claimed_years * 12)
    facts = (f"Deck says {claimed_years:g} years; {source_text(result)} shows {months / 12:.1f} years "
             f"(gap {gap:.0f} months, allowed {allowed:g}).")
    if gap <= allowed:
        return make(claim, result, st, VerdictLabel.SUPPORTED, "tenure_within_tolerance", Confidence.MEDIUM, facts)
    return make(claim, result, st, VerdictLabel.CONTRADICTED, "tenure_outside_tolerance", Confidence.MEDIUM, facts)
