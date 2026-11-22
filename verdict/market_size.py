"""Verdict rule for market_size claims: third-party estimates from dated web pages (D16, T33).

Who calls it: verdict/engine.py after the shared checks (DESIGN.md section 3.10).
What it calls: verdict/common.py, verdict/web_common.py, core.config.rule (tolerances.market_size.tolerance_pct,
min_agreeing_sources, max_record_age_days). Only estimates in the claim's currency count.
SUPPORTED: at least one estimate within tolerance (max medium). CONTRADICTED (max medium) only when at least
min_agreeing_sources estimates from different domains all lie outside tolerance AND agree with each other within
tolerance; one disagreeing source is never enough. Everything else is CANNOT_VERIFY source_may_be_incomplete.
"""

from __future__ import annotations

from typing import Any

from core.config import rule
from core.models import CheckResult, Claim, Confidence, Verdict, VerdictLabel
from verdict.common import make, num, rel_diff
from verdict.web_common import admissible

MISSING_MARKET = "A dated market report (analyst firm or industry body) giving the market size in the deck's currency."


def judge(claim: Claim, result: CheckResult, rules: dict[str, Any], st: dict[str, Any]) -> Verdict:
    claimed = num(claim.value)
    if claimed is None or claimed <= 0:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    f"The deck's market size {claim.value!r} is not a usable number.")
    max_age = float(rule(rules, "tolerances.market_size.max_record_age_days"))
    dated = [e for e in admissible(result.observed.get("estimates"), st["ref"], max_age)
             if num(e.get("value")) is not None and num(e.get("value")) > 0]
    if not dated:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "no_evidence", Confidence.LOW,
                    "No dated market-size estimate on or before the deck date was found.", missing=MISSING_MARKET)
    currency = (claim.unit or "").strip().upper()
    same = [e for e in dated if str(e.get("currency") or "").strip().upper() == currency] if currency else []
    if not same:
        found = sorted({str(e.get("currency")) for e in dated})
        return make(claim, result, st, VerdictLabel.NOT_COMPARABLE, "currency_mismatch", Confidence.MEDIUM,
                    f"The deck states the market in {claim.unit or 'no currency'}; the estimates found are in "
                    f"{', '.join(found)}.")
    tol = float(rule(rules, "tolerances.market_size.tolerance_pct")) / 100
    values = [(num(e["value"]), e) for e in same]
    listing = "; ".join(f"{v:,.0f} {currency} ({e.get('domain') or e.get('url')}, {e.get('published_date')})"
                        for v, e in values)
    facts = f"Deck says {claimed:,.0f} {currency}; estimates found: {listing} (allowed difference {tol:.0%})."
    close = [v for v, _ in values if rel_diff(v, claimed) <= tol]
    if close:
        near = min(rel_diff(v, claimed) for v in close) <= st["supported_margin"] * tol
        return make(claim, result, st, VerdictLabel.SUPPORTED, "within_tolerance",
                    Confidence.MEDIUM if near else Confidence.LOW, facts)
    domains = {str(e.get("domain")).strip().lower() for _, e in values if e.get("domain")}
    agree = all(max(rel_diff(a, b), rel_diff(b, a)) <= tol for a, _ in values for b, _ in values)
    if len(domains) >= int(rule(rules, "tolerances.market_size.min_agreeing_sources")) and agree:
        return make(claim, result, st, VerdictLabel.CONTRADICTED, "sources_agree_otherwise",
                    Confidence.MEDIUM if st["fresh"] else Confidence.LOW, facts)
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "source_may_be_incomplete", Confidence.LOW,
                facts + " Too few independent estimates agree to say the deck is wrong.", missing=MISSING_MARKET)
