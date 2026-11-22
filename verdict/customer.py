"""Verdict rule for customer claims: is the customer named on a dated page the company does not control (D16, T33)?

Who calls it: verdict/engine.py after the shared checks (DESIGN.md section 3.11).
What it calls: verdict/common.py, verdict/web_common.py, core.config.rule (tolerances.customer.max_record_age_days).
SUPPORTED (medium) on one independent mention; only self-published mentions -> CANNOT_VERIFY self_reported_only.
Never CONTRADICTED: not finding a customer is not evidence against the claim.
"""

from __future__ import annotations

from typing import Any

from core.config import rule
from core.models import CheckResult, Claim, Confidence, Verdict, VerdictLabel
from verdict.common import make
from verdict.web_common import admissible


def judge(claim: Claim, result: CheckResult, rules: dict[str, Any], st: dict[str, Any]) -> Verdict:
    name = result.observed.get("customer_name") or claim.value
    max_age = float(rule(rules, "tolerances.customer.max_record_age_days"))
    mentions = admissible(result.observed.get("mentions"), st["ref"], max_age)
    if not mentions:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "no_evidence", Confidence.LOW,
                    f"No dated page on or before the deck date names {name!r} with the company.")
    independent = [m for m in mentions if m.get("independent") is True]
    if independent:
        m = independent[0]
        return make(claim, result, st, VerdictLabel.SUPPORTED, "independent_mention", Confidence.MEDIUM,
                    f"{m.get('domain') or m.get('url')} ({m.get('published_date')}), a site the company does not "
                    f"run, names {name!r} with the company: \"{m.get('quote')}\"")
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "self_reported_only", Confidence.LOW,
                f"{name!r} is named only on the company's own pages ({len(mentions)} found); no independent source.")
