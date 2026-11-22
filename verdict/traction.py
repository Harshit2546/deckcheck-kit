"""Verdict rule for traction claims: revenue to revenue, ARR to ARR, nothing else.

Who calls it: verdict/engine.py after the shared checks (DESIGN.md section 3.5).
What it calls: verdict/common.py; tolerance and margins come from rules.yaml (tolerances.traction.tolerance_pct,
verdict.strong_margin). Source revenue figures are estimates in USD: a claim in another currency is
NOT_COMPARABLE, a gap between the tolerance and strong_margin x tolerance is CANNOT_VERIFY, and nothing
is ever above medium confidence. Growth claims wait for the checker to state the growth_rate scale.
"""

from __future__ import annotations

from typing import Any

from core.models import CheckResult, Claim, Confidence, Verdict, VerdictLabel
from verdict.common import make, num, rel_diff, source_text

# Metrics that sound like revenue but are not the same figure.
_OTHER = ("gmv", "booking", "run_rate", "run rate", "mrr", "monthly", "order", "volume", "profit", "ebitda")
_FIELDS = {"revenue": "revenue", "annual_revenue": "revenue", "revenue_usd": "revenue", "turnover": "revenue",
           "arr": "arr", "annual_recurring_revenue": "arr"}


def judge(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    metric = (claim.metric or "").strip().lower().replace(" ", "_")
    if any(word in metric for word in _OTHER):
        return _mismatch(claim, result, st)
    if "growth" in metric:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "growth_scale_unclear", Confidence.LOW,
                    "The source's growth_rate does not state whether it is a fraction or a percent, or over which "
                    "period, so it is not compared with the deck's growth figure.")
    field = _FIELDS.get(metric)
    if field is None:
        return _mismatch(claim, result, st)
    if (claim.unit or "").strip().upper() != "USD":
        return make(claim, result, st, VerdictLabel.NOT_COMPARABLE, "currency_mismatch", Confidence.MEDIUM,
                    f"The deck states {field} in {claim.unit or 'no currency'}; the source reports USD.")
    claimed = num(claim.value)
    if claimed is None or claimed <= 0:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    f"The deck's {field} value {claim.value!r} is not a usable number.")
    observed = num(result.observed.get(field))
    if observed is None:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "no_evidence", Confidence.LOW,
                    f"The source gave no {field} figure for this company.")
    diff, tol = rel_diff(observed, claimed), st["tol"]
    facts = (f"Deck says {field} USD {claimed:,.0f}; {source_text(result)} estimates USD {observed:,.0f} on "
             f"{st['rec']} (difference {diff:.0%}, allowed {tol:.0%}).")
    if diff <= tol:
        conf = Confidence.MEDIUM if diff <= st["supported_margin"] * tol and st["fresh"] else Confidence.LOW
        return make(claim, result, st, VerdictLabel.SUPPORTED, "within_tolerance", conf, facts)
    if diff < st["strong_margin"] * tol:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "estimate_gap_unclear", Confidence.LOW,
                    facts + " The gap is too small to rule out an estimation error.")
    conf = Confidence.MEDIUM if st["fresh"] else Confidence.LOW
    return make(claim, result, st, VerdictLabel.CONTRADICTED, "outside_tolerance", conf, facts)


def _mismatch(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    return make(claim, result, st, VerdictLabel.NOT_COMPARABLE, "metric_mismatch", Confidence.MEDIUM,
                f"The deck's metric {claim.metric!r} is not revenue or ARR; the source cannot be compared with it.")
