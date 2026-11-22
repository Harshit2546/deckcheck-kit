"""Verdict rule for team_size claims (metric headcount): compare the deck's headcount with the source's.

Who calls it: verdict/engine.py after the shared checks (DESIGN.md section 3.1).
What it calls: verdict/common.py and core.config.rule (tolerance and margins come from rules.yaml).
Headcount is a derived estimate, so a CONTRADICTED here is never above medium confidence.
"""

from __future__ import annotations

from typing import Any

from core.models import CheckResult, Claim, Confidence, Verdict, VerdictLabel
from verdict.common import make, num, pick, rel_diff, source_text


def judge(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    """Return the verdict for one headcount claim. `st` is the prepared state from engine._prepare."""
    claimed = num(claim.value)
    if claimed is None or claimed < 0:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    f"The deck's headcount value {claim.value!r} is not a usable number.")
    exact = num(result.observed.get("headcount"))
    if exact is not None:
        return _exact(claim, result, st, claimed, exact)
    band = result.observed.get("headcount_range")
    if isinstance(band, (list, tuple)) and len(band) == 2 and num(band[0]) is not None and num(band[1]) is not None:
        return _band(claim, result, st, claimed, num(band[0]), num(band[1]))
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "no_evidence", Confidence.LOW,
                "The source gave no headcount figure for this company.")


def _exact(claim: Claim, result: CheckResult, st: dict[str, Any], claimed: float, observed: float) -> Verdict:
    diff, tol = rel_diff(observed, claimed), st["tol"]
    facts = (f"Deck says {claimed:g} people; {source_text(result)} shows {observed:g} on {st['rec']} "
             f"(difference {diff:.0%}, allowed {tol:.0%}).")
    if diff <= tol:
        close = diff <= st["supported_margin"] * tol
        return make(claim, result, st, VerdictLabel.SUPPORTED, "within_tolerance",
                    pick(close and st["fresh"]), facts)
    conf = Confidence.MEDIUM if st["fresh"] else Confidence.LOW  # a derived estimate is never high
    return make(claim, result, st, VerdictLabel.CONTRADICTED, "outside_tolerance", conf, facts)


def _band(claim: Claim, result: CheckResult, st: dict[str, Any], claimed: float, low: float, high: float) -> Verdict:
    tol = st["tol"]
    facts = (f"Deck says {claimed:g} people; {source_text(result)} gives the band {low:g} to {high:g} "
             f"on {st['rec']} (allowed widening {tol:.0%}).")
    if low * (1 - tol) <= claimed <= high * (1 + tol):
        conf = Confidence.MEDIUM if st["fresh"] else Confidence.LOW
        return make(claim, result, st, VerdictLabel.SUPPORTED, "within_band", conf, facts)
    return make(claim, result, st, VerdictLabel.CONTRADICTED, "outside_band", Confidence.LOW, facts)
