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


# ----------------------------------------------------------------- company_fact (year gap 1 -> CANNOT_VERIFY)

CF = ClaimType.COMPANY_FACT


@pytest.mark.parametrize("metric,value,observed,expected", [
    ("year_founded", 2015, {"year_founded": 2015}, (L.SUPPORTED, "within_tolerance", C.HIGH)),
    ("founded", "2015", {"year_founded": 2016}, (L.CANNOT_VERIFY, "founding_year_close", C.LOW)),
    ("year_founded", 2015, {"year_founded": 2019}, (L.CONTRADICTED, "outside_tolerance", C.MEDIUM)),
    ("year_founded", 2015, {"year_founded": None}, (L.CANNOT_VERIFY, "no_evidence", C.LOW)),
    ("year_founded", 2099, {"year_founded": 2015}, (L.CANNOT_VERIFY, "claim_value_unusable", C.LOW)),
    ("headquarters", "Bengaluru", {"headquarters": "Bangalore, Karnataka, India"},
     (L.SUPPORTED, "within_tolerance", C.MEDIUM)),
    ("hq", "Gurgaon", {"headquarters": {"city": "Gurugram", "country": "India"}},
     (L.SUPPORTED, "within_tolerance", C.MEDIUM)),
    ("headquarters", "Bengaluru", {"headquarters": "Singapore"}, (L.CANNOT_VERIFY, "location_unclear", C.LOW)),
    ("headquarters", "Bengaluru", {"headquarters": None}, (L.CANNOT_VERIFY, "no_evidence", C.LOW)),
    ("status", "private", {"status": "private"}, (L.CANNOT_VERIFY, "unsupported_metric", C.LOW)),
])
def test_company_fact(rules, metric, value, observed, expected):
    assert verdict(rules, CF, metric, value, None, observed) == expected


def test_company_fact_year_gap_comes_from_rules(rules):
    rules["tolerances"]["company_fact"]["year_gap_cannot_verify"] = 3
    assert verdict(rules, CF, "year_founded", 2015, None, {"year_founded": 2018})[1] == "founding_year_close"


@pytest.mark.parametrize("hq", ["Mumbai", "Delhi", "London, UK", "", 42])
def test_company_fact_hq_never_contradicted(rules, hq):
    assert verdict(rules, CF, "headquarters", "Bengaluru", None, {"headquarters": hq})[0] is not L.CONTRADICTED


# ----------------------------------------------------------------- prior_exit (guarded; tolerance 10%)

PE = ClaimType.PRIOR_EXIT
CHECKED = {"prior_company_checked": True}


def test_prior_exit_stops_on_the_deck_company_record(rules):
    # Locus shape: the deck's OWN company shows an acquisition; it must not support a founder's prior exit.
    own = {"exit_found": True, "acquired_by": "Ingka Investments", "exit_amount": None, "exit_date": "2025-03-01"}
    assert verdict(rules, PE, "acquired_by", "Ingka Investments", None, own) == \
        (L.CANNOT_VERIFY, "prior_company_not_checked", C.LOW)


@pytest.mark.parametrize("flag", [None, False, "yes", 1, "true"])
def test_prior_exit_guard_needs_explicit_true(rules, flag):
    obs = {"acquired_by": "Flipkart", "prior_company_checked": flag}
    assert verdict(rules, PE, "acquired_by", "Flipkart", None, obs)[1] == "prior_company_not_checked"


@pytest.mark.parametrize("metric,value,unit,observed,expected", [
    ("acquired_by", "Flipkart", None, {"acquired_by": "Flipkart Pvt Ltd"}, (L.SUPPORTED, "acquirer_matches", C.MEDIUM)),
    ("acquired_by", "Flipkart", None, {"acquired_by": "Amazon"}, (L.CANNOT_VERIFY, "acquirer_differs", C.LOW)),
    ("acquired_by", "Flipkart", None, {"acquired_by": None, "x": 1}, (L.CANNOT_VERIFY, "source_may_be_incomplete", C.LOW)),
    ("exit_amount", 10_000_000, "USD", {"exit_amount": 10_500_000}, (L.SUPPORTED, "within_tolerance", C.MEDIUM)),
    ("exit_amount", 10_000_000, "USD", {"exit_amount": 3_000_000}, (L.CANNOT_VERIFY, "estimate_gap_unclear", C.LOW)),
    ("exit_amount", 10_000_000, "USD", {"exit_amount": None, "x": 1}, (L.CANNOT_VERIFY, "source_may_be_incomplete", C.LOW)),
    ("exit_amount", 800_000_000, "INR", {"exit_amount": 10_000_000}, (L.NOT_COMPARABLE, "currency_mismatch", C.MEDIUM)),
    ("founders", "x", None, {"acquired_by": "y"}, (L.CANNOT_VERIFY, "unsupported_metric", C.LOW)),
])
def test_prior_exit_when_prior_company_was_checked(rules, metric, value, unit, observed, expected):
    assert verdict(rules, PE, metric, value, unit, {**CHECKED, **observed}) == expected


@pytest.mark.parametrize("observed", [{"acquired_by": "Other Co"}, {"exit_amount": 1}, {"exit_amount": 10**12}])
def test_prior_exit_never_contradicted(rules, observed):
    for metric, value, unit in (("acquired_by", "Flipkart", None), ("exit_amount", 10_000_000, "USD")):
        assert verdict(rules, PE, metric, value, unit, {**CHECKED, **observed})[0] is not L.CONTRADICTED


# ----------------------------------------------------------------- team_growth (tolerance 25%, window 365 +- 45 days)

TG = ClaimType.TEAM_GROWTH


@pytest.mark.parametrize("metric,value,unit,observed,expected", [
    # today's checker: no baseline_date -> never compared
    ("headcount_growth_yoy", 50, "%", {"growth_percent": 50}, (L.NOT_COMPARABLE, "period_mismatch", C.MEDIUM)),
    ("headcount_growth", 50, "%", {"growth_percent": 50, "baseline_date": "2025-01-10"},
     (L.NOT_COMPARABLE, "period_mismatch", C.MEDIUM)),                                  # no period named
    ("headcount_growth_yoy", 50, "%", {"growth_percent": 50, "baseline_date": "2023-01-10"},
     (L.NOT_COMPARABLE, "period_mismatch", C.MEDIUM)),                                  # 3-year window
    ("headcount_growth_yoy", 50, "%", {"growth_percent": 55, "baseline_date": "2025-01-10"},
     (L.SUPPORTED, "within_tolerance", C.MEDIUM)),
    ("headcount_growth_yoy", 50, "%", {"growth_percent": 10, "baseline_date": "2025-01-10"},
     (L.CANNOT_VERIFY, "estimate_gap_unclear", C.LOW)),
    ("headcount_growth_yoy", 2, "x", {"growth_percent": 100, "baseline_date": "2025-01-10"},
     (L.NOT_COMPARABLE, "metric_mismatch", C.MEDIUM)),
    ("headcount_growth_yoy", 50, "%", {"growth_absolute": 5, "baseline_date": "2025-01-10"},
     (L.CANNOT_VERIFY, "no_evidence", C.LOW)),
])
def test_team_growth(rules, metric, value, unit, observed, expected):
    assert verdict(rules, TG, metric, value, unit, observed) == expected


@pytest.mark.parametrize("growth", [-50, 0, 10, 300])
def test_team_growth_never_contradicted(rules, growth):
    obs = {"growth_percent": growth, "baseline_date": "2025-01-10"}
    assert verdict(rules, TG, "headcount_growth_yoy", 50, "%", obs)[0] is not L.CONTRADICTED


# ----------------------------------------------------------------- competition (never decided)

@pytest.mark.parametrize("metric,value", [("competitors", "Shipsy"), ("market_position", "leader"),
                                          ("competitor_count", 3)])
def test_competition_is_never_decided(rules, metric, value):
    obs = {"competitors": ["Shipsy", "FarEye"]}
    assert verdict(rules, ClaimType.COMPETITION, metric, value, None, obs) == \
        (L.CANNOT_VERIFY, "competition_not_judged", C.LOW)


def test_every_new_reason_has_missing_text():
    from verdict.common import MISSING_TEXT
    for code in ("metric_mismatch", "observed_more_than_claimed", "growth_scale_unclear", "estimate_gap_unclear",
                 "founding_year_close", "location_unclear", "prior_company_not_checked", "acquirer_differs",
                 "period_mismatch", "competition_not_judged"):
        assert MISSING_TEXT.get(code), code


def test_reused_reason_codes_ask_for_the_right_document(rules):
    v = decide(make_claim(HI, "open_roles", 40, "roles"), make_result({"openings_count": 5}), rules)
    assert v.reason_code == "source_may_be_incomplete" and "investor" not in v.missing.lower()
    assert "open roles" in v.missing
    v = decide(make_claim(PE, "acquired_by", "Flipkart"), make_result({**CHECKED, "acquired_by": None, "x": 1}), rules)
    assert "deal announcement" in v.missing.lower()
    v = decide(make_claim(TG, "headcount_growth_yoy", 50, "%"),
               make_result({"growth_percent": 10, "baseline_date": "2025-01-10"}), rules)
    assert v.reason_code == "estimate_gap_unclear" and "accounts" not in v.missing.lower()
