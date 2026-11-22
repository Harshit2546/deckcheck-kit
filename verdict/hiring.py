"""Verdict rule for hiring claims: open roles (openings_count) or openings growth (growth_percent).

Who calls it: verdict/engine.py after the shared checks (DESIGN.md section 3.4).
What it calls: verdict/common.py; the tolerance comes from rules.yaml (tolerances.hiring.tolerance_pct).
Job indexes undercount, so this rule never returns CONTRADICTED and SUPPORTED is at most medium.
A claim about a subset of roles ("40 engineers") can never be supported by the total opening count.
"""

from __future__ import annotations

from typing import Any

from core.models import CheckResult, Claim, Confidence, Verdict, VerdictLabel
from verdict.common import make, num, rel_diff, source_text

# Units that mean "all openings". Anything else ("engineers", "sales") names a subset.
GENERIC_UNITS = {"", "people", "roles", "role", "openings", "opening", "jobs", "job", "positions",
                 "position", "open_roles", "hires"}


def judge(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    metric = (claim.metric or "").strip().lower()
    unit = (claim.unit or "").strip().lower()
    claimed = num(claim.value)
    if claimed is None or claimed < 0:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    f"The deck's hiring value {claim.value!r} is not a usable number.")
    if "growth" in metric:
        if unit not in ("%", "percent"):
            return _mismatch(claim, result, st, f"a growth claim in unit {claim.unit!r}, not a percentage")
        return _compare(claim, result, st, claimed, num(result.observed.get("growth_percent")), "openings growth %")
    if unit not in GENERIC_UNITS:
        return _mismatch(claim, result, st, f"openings of one kind ({claim.unit}), while the source counts all openings")
    return _compare(claim, result, st, claimed, num(result.observed.get("openings_count")), "open roles")


def _mismatch(claim: Claim, result: CheckResult, st: dict[str, Any], what: str) -> Verdict:
    return make(claim, result, st, VerdictLabel.NOT_COMPARABLE, "metric_mismatch", Confidence.MEDIUM,
                f"The deck states {what}; the source cannot be compared with it.")


def _compare(claim: Claim, result: CheckResult, st: dict[str, Any], claimed: float, observed: float | None,
             label: str) -> Verdict:
    if observed is None:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "no_evidence", Confidence.LOW,
                    f"The source gave no {label} figure for this company.")
    diff, tol = rel_diff(observed, claimed), st["tol"]
    facts = (f"Deck says {claimed:g} {label}; {source_text(result)} shows {observed:g} on {st['rec']} "
             f"(difference {diff:.0%}, allowed {tol:.0%}).")
    if diff <= tol:
        conf = Confidence.MEDIUM if diff <= st["supported_margin"] * tol and st["fresh"] else Confidence.LOW
        return make(claim, result, st, VerdictLabel.SUPPORTED, "within_tolerance", conf, facts)
    if observed < claimed:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "source_may_be_incomplete", Confidence.LOW,
                    facts + " Job indexes miss many openings, so a lower count does not contradict the deck.")
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "observed_more_than_claimed", Confidence.LOW,
                facts + " The source shows more than the deck claims; the deck is not overstating, but the numbers differ.")
