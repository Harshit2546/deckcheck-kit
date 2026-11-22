"""Verdict rule for company_fact claims: founded year and headquarters city.

Who calls it: verdict/engine.py after the shared checks (DESIGN.md section 3.6).
What it calls: verdict/common.py and core.config.rule (tolerances.company_fact.year_gap_cannot_verify).
Founded year: exact match SUPPORTED; a gap up to year_gap_cannot_verify is CANNOT_VERIFY (incorporation vs launch);
a larger gap is CONTRADICTED at medium. Headquarters: a normalised city match is SUPPORTED, anything else
CANNOT_VERIFY (spellings and offices differ), never CONTRADICTED. Other metrics: unsupported_metric.
"""

from __future__ import annotations

import re
from typing import Any

from core.config import rule
from core.models import CheckResult, Claim, Confidence, Verdict, VerdictLabel
from verdict.common import make, num, source_text

# Different names for the same city.
CITY_ALIASES = {"bangalore": "bengaluru", "gurgaon": "gurugram", "bombay": "mumbai", "new delhi": "delhi",
                "madras": "chennai", "calcutta": "kolkata", "poona": "pune"}


def judge(claim: Claim, result: CheckResult, rules: dict[str, Any], st: dict[str, Any]) -> Verdict:
    metric = (claim.metric or "").strip().lower()
    if "year" in metric or "found" in metric:
        return _year(claim, result, rules, st)
    if "headquarter" in metric or "hq" in metric or "location" in metric:
        return _city(claim, result, st)
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "unsupported_metric", Confidence.LOW,
                f"No verdict rule exists yet for company_fact / {claim.metric!r}.")


def _year(claim: Claim, result: CheckResult, rules: dict[str, Any], st: dict[str, Any]) -> Verdict:
    claimed, observed = num(claim.value), num(result.observed.get("year_founded"))
    latest = st["ref"].year
    if claimed is None or not 1800 <= claimed <= latest or claimed != int(claimed):
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    f"The deck's founded year {claim.value!r} is not a usable year.")
    if observed is None or not 1800 <= observed <= latest:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "no_evidence", Confidence.LOW,
                    "The source gave no usable founded year for this company.")
    gap = abs(int(observed) - int(claimed))
    facts = f"Deck says founded in {int(claimed)}; {source_text(result)} says {int(observed)}."
    if gap == 0:
        return make(claim, result, st, VerdictLabel.SUPPORTED, "within_tolerance", Confidence.HIGH, facts)
    if gap <= int(rule(rules, "tolerances.company_fact.year_gap_cannot_verify")):
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "founding_year_close", Confidence.LOW,
                    facts + " A small gap is often incorporation versus launch date.")
    return make(claim, result, st, VerdictLabel.CONTRADICTED, "outside_tolerance", Confidence.MEDIUM, facts)


def city_key(value: Any) -> str | None:
    """'Bangalore, Karnataka, India' -> 'bengaluru'. Accepts a string or a dict with a city/name field."""
    if isinstance(value, dict):
        value = value.get("city") or value.get("name") or value.get("location")
    if not isinstance(value, str) or not value.strip():
        return None
    city = re.sub(r"[^a-z ]", " ", value.split(",")[0].lower())
    city = " ".join(city.split())
    return CITY_ALIASES.get(city, city) or None


def _city(claim: Claim, result: CheckResult, st: dict[str, Any]) -> Verdict:
    claimed, observed = city_key(claim.value), city_key(result.observed.get("headquarters"))
    if claimed is None:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "claim_value_unusable", Confidence.LOW,
                    f"The deck's headquarters {claim.value!r} is not a usable place name.")
    if observed is None:
        return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "no_evidence", Confidence.LOW,
                    "The source gave no headquarters for this company.")
    facts = f"Deck says headquarters {claim.value!r}; {source_text(result)} says {result.observed.get('headquarters')!r}."
    if claimed == observed:
        return make(claim, result, st, VerdictLabel.SUPPORTED, "within_tolerance", Confidence.MEDIUM, facts)
    return make(claim, result, st, VerdictLabel.CANNOT_VERIFY, "location_unclear", Confidence.LOW,
                facts + " Company records often list a registered office rather than the operating base.")
