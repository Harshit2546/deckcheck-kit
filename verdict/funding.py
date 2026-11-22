"""Verdict rules for funding claims: total_raised, round_amount and investor (DESIGN.md section 3.2).

Who calls it: verdict/engine.py after the shared checks.
What it calls: verdict/common.py. Tolerance and margins arrive ready-made in `st` (read from rules.yaml).
Cautious by design: a total lower than the deck is CANNOT_VERIFY (databases miss rounds), and an investor
that is not listed is never a contradiction. Currencies are never converted.
"""

from __future__ import annotations

from typing import Any

from core.models import CheckResult, Claim, Confidence, Verdict, VerdictLabel
from verdict.common import make, num, pick, rel_diff, source_text

METRICS = ("total_raised", "round_amount", "investor")


def judge(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    """Route by claim.metric. Any other metric is CANNOT_VERIFY (unsupported_metric)."""
    metric = (claim.metric or "").strip().lower()
    if metric == "investor":
        return _investor(claim, result, st)
    if metric in ("total_raised", "round_amount"):
        return _amount(claim, result, st, metric)
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "unsupported_metric", Confidence.LOW,
                f"No rule exists yet for the funding metric {claim.metric!r}.")


def _investor(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    name = str(claim.value or "").strip().casefold()
    if not name:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    "The deck names no investor in a usable form.")
    found = result.observed.get("investors_found") or []
    if name in {str(x).strip().casefold() for x in found}:
        return make(claim, result, st, VerdictLabel.SUPPORTED, "investor_listed", Confidence.MEDIUM,
                    f"{source_text(result)} lists {claim.value} as an investor (record {st['rec']}).")
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "investor_not_listed", Confidence.LOW,
                f"{claim.value} is not among the investors in {source_text(result)}; a missing name is not proof.")


def _amount(claim: Claim, result: CheckResult, st: dict[str, Any], metric: str) -> Verdict:
    claimed = num(claim.value)
    unit = str(claim.unit or "").strip().upper()
    if claimed is None or claimed < 0 or not unit:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    f"The deck's amount {claim.value!r} {claim.unit or ''} is not a usable number with a currency.")
    if metric == "round_amount":
        rnd = result.observed.get("matched_round")
        if not isinstance(rnd, dict) or num(rnd.get("amount")) is None:
            return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "round_not_found", Confidence.LOW,
                        "No funding round in the source could be matched to the round the deck describes.")
        observed, currency = num(rnd["amount"]), rnd.get("currency") or result.observed.get("currency")
    else:
        observed, currency = num(result.observed.get("total_raised")), result.observed.get("currency")
        if observed is None:
            return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "no_evidence", Confidence.LOW,
                        "The source gave no total raised for this company.")
    if str(currency or "").strip().upper() != unit:
        return make(claim, result, st, VerdictLabel.NOT_COMPARABLE, "currency_mismatch", Confidence.MEDIUM,
                    f"Deck states {unit}; the source states {currency or 'no currency'}. No conversion is done.")
    return _compare(claim, result, st, metric, claimed, observed, unit)


def _compare(claim: Claim, result: CheckResult, st: dict[str, Any], metric: str, claimed: float,
             observed: float, unit: str) -> Verdict:
    diff, tol = rel_diff(observed, claimed), st["tol"]
    undated = int(num(result.observed.get("undated_rounds")) or 0)
    facts = (f"Deck says {claimed:,.0f} {unit}; {source_text(result)} shows {observed:,.0f} {unit} "
             f"as of {st['rec']} (difference {diff:.0%}, allowed {tol:.0%}).")
    if diff <= tol:
        if metric == "total_raised" and undated > 0:
            return make(claim, result, st, VerdictLabel.SUPPORTED, "within_tolerance_undated_rounds",
                        Confidence.LOW, facts + f" {undated} round(s) have no date and are not counted.")
        return make(claim, result, st, VerdictLabel.SUPPORTED, "within_tolerance",
                    pick(diff <= st["supported_margin"] * tol and st["fresh"]), facts)
    if metric == "round_amount":
        strong = diff >= st["strong_margin"] * tol and st["fresh"]
        return make(claim, result, st, VerdictLabel.CONTRADICTED, "outside_tolerance", pick(strong), facts)
    if observed > claimed:
        conf = Confidence.LOW if undated > 0 else Confidence.MEDIUM
        return make(claim, result, st, VerdictLabel.CONTRADICTED, "observed_higher", conf, facts)
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "source_may_be_incomplete", Confidence.LOW,
                facts + " The source may be missing rounds, so this is not treated as a contradiction.")
