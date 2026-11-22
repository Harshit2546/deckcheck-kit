"""Verdict rule for team_growth claims: headcount growth % over a named period (year on year / 12 months).

Who calls it: verdict/engine.py after the shared checks (DESIGN.md section 3.8).
What it calls: verdict/common.py and core.config.rule (tolerances.team_growth.tolerance_pct,
tolerances.team_growth.window_tolerance_days). The checker today takes the FIRST history point as baseline
(often years back) and does not expose the baseline date, so every claim is NOT_COMPARABLE period_mismatch
until observed carries an explicit baseline_date whose window fits the claim's period. Never CONTRADICTED.
"""

from __future__ import annotations

from typing import Any

from core.config import rule
from core.models import CheckResult, Claim, Confidence, Verdict, VerdictLabel
from verdict.common import make, num, parse_date, rel_diff, source_text

_YEARLY = ("yoy", "year", "annual", "12m", "12_month", "12 month")


def judge(claim: Claim, result: CheckResult, rules: dict[str, Any], st: dict[str, Any]) -> Verdict:
    metric = (claim.metric or "").strip().lower()
    base = parse_date(result.observed.get("baseline_date"))
    if base is None or not any(w in metric for w in _YEARLY):
        return _period(claim, result, st, "the source's growth window is not known to match the deck's period")
    window = (st["rec"] - base).days
    slack = int(rule(rules, "tolerances.team_growth.window_tolerance_days"))
    if abs(window - 365) > slack:
        return _period(claim, result, st, f"the source measures {window} days, the deck one year")
    if (claim.unit or "").strip() not in ("%", "percent"):
        return make(claim, result, st, VerdictLabel.NOT_COMPARABLE, "metric_mismatch", Confidence.MEDIUM,
                    f"The deck states growth in {claim.unit!r}, not a percentage.")
    claimed, observed = num(claim.value), num(result.observed.get("growth_percent"))
    if claimed is None:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    f"The deck's growth value {claim.value!r} is not a usable number.")
    if observed is None:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "no_evidence", Confidence.LOW,
                    "The source gave no growth figure for this window.")
    diff, tol = rel_diff(observed, claimed), st["tol"]
    facts = (f"Deck says {claimed:g}% growth in a year; {source_text(result)} shows {observed:g}% from {base} "
             f"to {st['rec']} (difference {diff:.0%}, allowed {tol:.0%}).")
    if diff <= tol:
        return make(claim, result, st, VerdictLabel.SUPPORTED, "within_tolerance", Confidence.MEDIUM, facts)
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "estimate_gap_unclear", Confidence.LOW, facts)


def _period(claim: Claim, result: CheckResult, st: dict[str, Any], why: str) -> Verdict:
    return make(claim, result, st, VerdictLabel.NOT_COMPARABLE, "period_mismatch", Confidence.MEDIUM,
                f"Growth cannot be compared: {why}.")
