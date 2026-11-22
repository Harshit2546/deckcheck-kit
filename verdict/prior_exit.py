"""Verdict rule for prior_exit claims: the acquirer or the exit amount of a founder's EARLIER company.

Who calls it: verdict/engine.py (guard right after the identity check, rule after the shared checks; DESIGN.md 3.7).
What it calls: verdict/common.py, resolve/names.py (company_names_match); tolerance from rules.yaml
(tolerances.prior_exit.tolerance_pct). The prior_exit checker today fetches the deck's OWN company, so every
claim stops at CANNOT_VERIFY prior_company_not_checked unless the checker sets observed["prior_company_checked"]
to True. Even then this rule never returns CONTRADICTED: a missing or different record is CANNOT_VERIFY.
"""

from __future__ import annotations

from typing import Any

from core.models import CheckResult, Claim, Confidence, Verdict, VerdictLabel
from resolve.names import company_names_match
from verdict.common import make, num, rel_diff, source_text

MISSING_DEAL = "The deal announcement naming the acquirer and the amount for the founder's earlier company."


def guard(claim: Claim, result: CheckResult) -> Verdict | None:
    """Stop unless the checker says it fetched the founder's prior company (an explicit True, nothing else)."""
    if result.observed.get("prior_company_checked") is True:
        return None
    return make(claim, result, None, VerdictLabel.CANNOT_VERIFY, "prior_company_not_checked", Confidence.LOW,
                "The source record is the deck's own company, not the founder's earlier company, so it says "
                "nothing about this exit.")


def judge(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    metric = (claim.metric or "").strip().lower()
    if any(w in metric for w in ("amount", "value", "price", "valuation")):
        return _amount(claim, result, st)
    if any(w in metric for w in ("acquir", "buyer", "exit", "sold")):
        return _acquirer(claim, result, st)
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "unsupported_metric", Confidence.LOW,
                f"No verdict rule exists yet for prior_exit / {claim.metric!r}.")


def _acquirer(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    observed = result.observed.get("acquired_by")
    if not isinstance(claim.value, str) or not claim.value.strip():
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    f"The deck's acquirer {claim.value!r} is not a usable name.")
    if not observed:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "source_may_be_incomplete", Confidence.LOW,
                    "The source lists no acquirer for the earlier company.", missing=MISSING_DEAL)
    facts = f"Deck says acquired by {claim.value!r}; {source_text(result)} says {observed!r}."
    if company_names_match(claim.value, observed):
        return make(claim, result, st, VerdictLabel.SUPPORTED, "acquirer_matches", Confidence.MEDIUM, facts)
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "acquirer_differs", Confidence.LOW,
                facts + " Names differ; a parent company or a later deal may explain it.")


def _amount(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    if (claim.unit or "").strip().upper() != "USD":
        return make(claim, result, st, VerdictLabel.NOT_COMPARABLE, "currency_mismatch", Confidence.MEDIUM,
                    f"The deck states the exit amount in {claim.unit or 'no currency'}; the source reports USD.")
    claimed, observed = num(claim.value), num(result.observed.get("exit_amount"))
    if claimed is None or claimed <= 0:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    f"The deck's exit amount {claim.value!r} is not a usable number.")
    if observed is None:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "source_may_be_incomplete", Confidence.LOW,
                    "The source gives no amount for this exit; most deal prices are not disclosed.", missing=MISSING_DEAL)
    diff, tol = rel_diff(observed, claimed), st["tol"]
    facts = (f"Deck says exit USD {claimed:,.0f}; {source_text(result)} says USD {observed:,.0f} "
             f"(difference {diff:.0%}, allowed {tol:.0%}).")
    if diff <= tol:
        return make(claim, result, st, VerdictLabel.SUPPORTED, "within_tolerance", Confidence.MEDIUM, facts)
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "estimate_gap_unclear", Confidence.LOW, facts,
                missing=MISSING_DEAL)
