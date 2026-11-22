"""T29 tests: verdict rules for hiring, traction, company_fact, prior_exit, team_growth, competition.

Called by: pytest. Calls: verdict.engine with hand-built CheckResult fixtures (tests only).
Every label each rule can give is covered, plus explicit "never CONTRADICTED" tests on the cautious paths.
"""

import pytest

from core.models import ClaimType, Confidence as C, VerdictLabel as L
from tests.verdict.fakes import make_claim, make_result
from verdict.engine import decide

HI = ClaimType.HIRING


def verdict(rules, ctype, metric, value, unit, observed):
    v = decide(make_claim(ctype, metric, value, unit), make_result(observed), rules)
    return v.label, v.reason_code, v.confidence


# ----------------------------------------------------------------- hiring (tolerance 30%)

@pytest.mark.parametrize("metric,value,unit,observed,expected", [
    ("open_roles", 40, "roles", {"openings_count": 40}, (L.SUPPORTED, "within_tolerance", C.MEDIUM)),
    ("open_roles", 40, None, {"openings_count": 50}, (L.SUPPORTED, "within_tolerance", C.LOW)),       # 25%: in, not close
    ("open_roles", 40, "roles", {"openings_count": 10}, (L.CANNOT_VERIFY, "source_may_be_incomplete", C.LOW)),
    ("open_roles", 40, "roles", {"openings_count": 90}, (L.CANNOT_VERIFY, "observed_more_than_claimed", C.LOW)),
    ("open_roles", 40, "engineers", {"openings_count": 40}, (L.NOT_COMPARABLE, "metric_mismatch", C.MEDIUM)),  # Deck A slide 8
    ("openings_growth", 50, "%", {"growth_percent": 55}, (L.SUPPORTED, "within_tolerance", C.MEDIUM)),
    ("openings_growth", 50, "roles", {"growth_percent": 50}, (L.NOT_COMPARABLE, "metric_mismatch", C.MEDIUM)),
    ("open_roles", 40, "roles", {"growth_percent": 10}, (L.CANNOT_VERIFY, "no_evidence", C.LOW)),
    ("open_roles", "many", "roles", {"openings_count": 40}, (L.CANNOT_VERIFY, "claim_value_unusable", C.LOW)),
])
def test_hiring(rules, metric, value, unit, observed, expected):
    assert verdict(rules, HI, metric, value, unit, observed) == expected


@pytest.mark.parametrize("observed", [0, 1, 10, 39, 41, 100, 10_000])
def test_hiring_never_contradicted(rules, observed):
    label, _, conf = verdict(rules, HI, "open_roles", 40, "roles", {"openings_count": observed})
    assert label is not L.CONTRADICTED and conf is not C.HIGH


# ----------------------------------------------------------------- traction (tolerance 15%, strong margin 2.0 -> 30%)

TR = ClaimType.TRACTION


@pytest.mark.parametrize("metric,value,unit,observed,expected", [
    ("revenue", 1_000_000, "USD", {"revenue": 1_000_000}, (L.SUPPORTED, "within_tolerance", C.MEDIUM)),
    ("arr", 1_000_000, "USD", {"arr": 880_000}, (L.SUPPORTED, "within_tolerance", C.LOW)),          # 12%: in, not close
    ("revenue", 1_000_000, "USD", {"revenue": 800_000}, (L.CANNOT_VERIFY, "estimate_gap_unclear", C.LOW)),  # 20%
    ("revenue", 1_000_000, "USD", {"revenue": 500_000}, (L.CONTRADICTED, "outside_tolerance", C.MEDIUM)),   # 50%
    ("arr", 1_000_000, "USD", {"revenue": 1_000_000}, (L.CANNOT_VERIFY, "no_evidence", C.LOW)),       # ARR vs revenue
    ("gmv", 1_000_000, "USD", {"revenue": 1_000_000}, (L.NOT_COMPARABLE, "metric_mismatch", C.MEDIUM)),
    ("revenue_run_rate", 1_000_000, "USD", {"revenue": 1_000_000}, (L.NOT_COMPARABLE, "metric_mismatch", C.MEDIUM)),
    ("customers", 50, None, {"revenue": 1}, (L.NOT_COMPARABLE, "metric_mismatch", C.MEDIUM)),
    ("revenue", 80_000_000, "INR", {"revenue": 1_000_000}, (L.NOT_COMPARABLE, "currency_mismatch", C.MEDIUM)),
    ("revenue", 1_000_000, None, {"revenue": 1_000_000}, (L.NOT_COMPARABLE, "currency_mismatch", C.MEDIUM)),
    ("revenue_growth", 50, "%", {"growth_rate": 0.5}, (L.CANNOT_VERIFY, "growth_scale_unclear", C.LOW)),
    ("revenue", "big", "USD", {"revenue": 1}, (L.CANNOT_VERIFY, "claim_value_unusable", C.LOW)),
])
def test_traction(rules, metric, value, unit, observed, expected):
    assert verdict(rules, TR, metric, value, unit, observed) == expected


def test_traction_never_high_confidence(rules):
    for obs in (1, 500_000, 1_000_000, 5_000_000):
        assert verdict(rules, TR, "revenue", 1_000_000, "USD", {"revenue": obs})[2] is not C.HIGH


@pytest.mark.parametrize("metric,unit", [("gmv", "USD"), ("revenue", "INR"), ("revenue_growth", "%"),
                                         ("mrr", "USD")])
def test_traction_cautious_paths_never_contradicted(rules, metric, unit):
    label = verdict(rules, TR, metric, 1_000_000, unit, {"revenue": 1, "arr": 1, "growth_rate": 99})[0]
    assert label is not L.CONTRADICTED
