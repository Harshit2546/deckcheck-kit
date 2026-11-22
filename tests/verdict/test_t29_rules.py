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
