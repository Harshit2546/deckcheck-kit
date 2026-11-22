"""Tests for the metric rules in verdict/team_size.py, funding.py and founder.py (DESIGN.md section 3).

Called by: pytest. Calls: verdict.engine with hand-built CheckResult fixtures (tests only).
Reference date is 2026-01-15; FRESH record is 5 days older; max_record_age_days and tolerances come from rules.yaml.
"""

import pytest

from core.models import CheckResult, ClaimType, Confidence as C, SourceType, VerdictLabel as L
from tests.verdict.fakes import make_claim, make_result
from verdict.engine import decide

TS, FU, FB = ClaimType.TEAM_SIZE, ClaimType.FUNDING, ClaimType.FOUNDER_BACKGROUND


def team(value, observed, **kw):
    return make_claim(TS, "headcount", value, "people"), make_result(observed, **kw)


# ----------------------------------------------------------------- team_size (tolerance 20%, margins 0.5 / 2.0)

@pytest.mark.parametrize("claimed,observed,label,reason,conf", [
    (40, 40, L.SUPPORTED, "within_tolerance", C.HIGH),        # exact, fresh
    (40, 43, L.SUPPORTED, "within_tolerance", C.HIGH),        # 7.5% <= 0.5 * 20%
    (40, 46, L.SUPPORTED, "within_tolerance", C.MEDIUM),      # 15%: inside tolerance, not close
    (40, 48, L.SUPPORTED, "within_tolerance", C.MEDIUM),      # exactly at the edge (20%)
    (40, 49, L.CONTRADICTED, "outside_tolerance", C.MEDIUM),  # never high for headcount
    (100, 30, L.CONTRADICTED, "outside_tolerance", C.MEDIUM),
])
def test_team_size_exact(rules, claimed, observed, label, reason, conf):
    c, r = team(claimed, {"headcount": observed})
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (label, reason, conf)
    assert (v.missing is None) == (label is L.SUPPORTED)


def test_team_size_old_record_lowers_confidence(rules):
    c, r = team(40, {"headcount": 40, "record_date": "2025-06-01"})   # 228 days: valid but not fresh
    assert decide(c, r, rules).confidence is C.MEDIUM
    c, r = team(100, {"headcount": 30, "record_date": "2025-06-01"})
    assert (decide(c, r, rules).label, decide(c, r, rules).confidence) == (L.CONTRADICTED, C.LOW)


def test_team_size_band(rules):
    c, r = team(120, {"headcount_range": [51, 200]})
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.SUPPORTED, "within_band", C.MEDIUM)
    c, r = team(45, {"headcount_range": [51, 200]})        # 45 >= 51 * 0.8 = 40.8: inside the widened band
    assert decide(c, r, rules).label is L.SUPPORTED
    c, r = team(30, {"headcount_range": [51, 200]})
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.CONTRADICTED, "outside_band", C.LOW)


def test_team_size_no_headcount_key(rules):
    c, r = team(40, {"something_else": 1})
    v = decide(c, r, rules)
    assert v.reason_code == "no_evidence" and v.missing == "A headcount record dated on or before 2026-01-15."


def test_d13_no_history_point_gives_headcount_missing_text(rules):
    c = make_claim(TS, "headcount", 40, "people", as_of=None)
    res = CheckResult(evidence=[], observed={"reference_date": "2026-03-01"})       # checker found no dated point
    v = decide(c, res, rules)
    assert (v.label, v.reason_code) == (L.CANNOT_VERIFY, "no_evidence")
    assert v.missing == "A headcount record dated on or before 2026-03-01."
    other = decide(make_claim(FU, "total_raised", 1, "USD"), CheckResult(), rules)
    assert other.missing == "Any dated record for this claim from a named source."


def test_team_size_zero_claim(rules):
    c, r = team(0, {"headcount": 0})
    assert decide(c, r, rules).label is L.SUPPORTED
    c, r = team(0, {"headcount": 3})
    assert decide(c, r, rules).label is L.CONTRADICTED


# ----------------------------------------------------------------- funding (tolerance 10%)

def fund(metric, value, observed, unit="USD"):
    return make_claim(FU, metric, value, unit), make_result({"currency": "USD", **observed})


def test_total_raised_supported_and_confidence(rules):
    c, r = fund("total_raised", 5_000_000, {"total_raised": 5_100_000})   # 2% <= 0.5 * 10%
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.SUPPORTED, "within_tolerance", C.HIGH)
    c, r = fund("total_raised", 5_000_000, {"total_raised": 5_400_000})   # 8%
    assert decide(c, r, rules).confidence is C.MEDIUM


def test_total_raised_undated_rounds_never_confident(rules):
    c, r = fund("total_raised", 5_000_000, {"total_raised": 5_000_000, "undated_rounds": 1})
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.SUPPORTED, "within_tolerance_undated_rounds", C.LOW)


def test_total_raised_lower_than_deck_is_cannot_verify(rules):
    c, r = fund("total_raised", 10_000_000, {"total_raised": 4_000_000})
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.CANNOT_VERIFY, "source_may_be_incomplete", C.LOW)
    assert "4,000,000" in v.explanation and v.missing


def test_total_raised_higher_than_deck_is_contradicted(rules):
    c, r = fund("total_raised", 5_000_000, {"total_raised": 20_000_000})
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.CONTRADICTED, "observed_higher", C.MEDIUM)
    c, r = fund("total_raised", 5_000_000, {"total_raised": 20_000_000, "undated_rounds": 2})
    assert decide(c, r, rules).confidence is C.LOW


def test_total_raised_missing_total(rules):
    c, r = fund("total_raised", 5_000_000, {})
    assert decide(c, r, rules).reason_code == "no_evidence"


def test_currency_mismatch_and_missing_unit(rules):
    c, r = fund("total_raised", 5_000_000, {"total_raised": 5_000_000}, unit="INR")
    v = decide(c, r, rules)
    assert (v.label, v.reason_code) == (L.NOT_COMPARABLE, "currency_mismatch")
    c, r = fund("total_raised", 5_000_000, {"total_raised": 5_000_000}, unit=None)
    assert decide(c, r, rules).reason_code == "claim_value_unusable"


def test_round_amount(rules):
    rnd = {"stage": "Series A", "amount": 5_000_000, "currency": "USD", "date": "2025-12-01", "investors": []}
    c, r = fund("round_amount", 5_000_000, {"matched_round": rnd})
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.SUPPORTED, "within_tolerance", C.HIGH)
    c, r = fund("round_amount", 8_000_000, {"matched_round": rnd})        # 37.5% >= 2 * 10%, fresh
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.CONTRADICTED, "outside_tolerance", C.HIGH)
    c, r = fund("round_amount", 5_700_000, {"matched_round": rnd})        # 14%: outside 10% but under 2x
    assert (decide(c, r, rules).label, decide(c, r, rules).confidence) == (L.CONTRADICTED, C.MEDIUM)


def test_round_amount_not_found_and_currency(rules):
    c, r = fund("round_amount", 5_000_000, {"matched_round": None})
    assert (decide(c, r, rules).label, decide(c, r, rules).reason_code) == (L.CANNOT_VERIFY, "round_not_found")
    rnd = {"amount": 5_000_000, "currency": "EUR"}
    c, r = fund("round_amount", 5_000_000, {"matched_round": rnd})
    assert decide(c, r, rules).reason_code == "currency_mismatch"


def test_investor(rules):
    c, r = fund("investor", "Sequoia Capital", {"investors_found": ["sequoia capital ", "Accel"]}, unit=None)
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.SUPPORTED, "investor_listed", C.MEDIUM)
    c, r = fund("investor", "Sequoia Capital", {"investors_found": ["Accel"]}, unit=None)
    v = decide(c, r, rules)
    assert (v.label, v.reason_code) == (L.CANNOT_VERIFY, "investor_not_listed")
    c, r = fund("investor", None, {"investors_found": ["Accel"]}, unit=None)
    assert decide(c, r, rules).reason_code == "claim_value_unusable"


def test_unsupported_funding_metric(rules):
    c, r = fund("valuation", 1, {})
    assert decide(c, r, rules).reason_code == "unsupported_metric"


# ----------------------------------------------------------------- founder_background

def founder(metric, value, observed, **kw):
    obs = {"employer_found": True, **observed}
    return (make_claim(FB, metric, value, None, subject="Priya"),
            make_result(obs, source=SourceType.CRUSTDATA_PERSON, **kw))


def test_past_employer(rules):
    c, r = founder("past_employer", "Flipkart", {})
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.SUPPORTED, "employer_listed", C.HIGH)
    c, r = founder("past_employer", "Flipkart", {"employer_found": False})
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.CANNOT_VERIFY, "employer_not_in_profile", C.LOW)


def test_past_employer_namesake_stops_at_identity(rules):
    c, r = founder("past_employer", "Flipkart", {"identity": "unclear"})
    assert decide(c, r, rules).reason_code == "identity_unclear"


@pytest.mark.parametrize("claimed,observed,label,reason,conf", [
    ("VP Engineering", "VP Engineering", L.SUPPORTED, "title_level_met", C.HIGH),
    ("VP Engineering", "Chief Technology Officer, CTO", L.SUPPORTED, "title_level_met", C.MEDIUM),  # more senior
    ("CEO", "Director of Sales", L.CONTRADICTED, "title_level_lower", C.HIGH),       # c_level vs director: 2 levels
    ("CTO", "VP Engineering", L.CONTRADICTED, "title_level_lower", C.MEDIUM),        # 1 level
    ("Director of Product", "Product Manager", L.CONTRADICTED, "title_level_lower", C.MEDIUM),
    ("Engineering Manager", "Software Engineer", L.NOT_COMPARABLE, "informal_title", C.LOW),   # below threshold
    ("Head of Growth", "Senior Wizard", L.CANNOT_VERIFY, "title_unmapped", C.LOW),
    ("Chief Wizard", "CEO", L.CANNOT_VERIFY, "title_unmapped", C.LOW),
])
def test_title_levels(rules, claimed, observed, label, reason, conf):
    c, r = founder("title", claimed, {"title_observed": observed})
    v = decide(c, r, rules)
    assert (v.label, v.reason_code, v.confidence) == (label, reason, conf)


def test_title_keyword_must_be_a_whole_word(rules):
    # "ceo" must not match inside another word, "lead" must not match inside "leader"
    c, r = founder("title", "Product Leader", {"title_observed": "Product Leader"})
    assert decide(c, r, rules).reason_code == "title_unmapped"


def test_title_without_observed_title(rules):
    c, r = founder("title", "CEO", {"title_observed": None})
    assert decide(c, r, rules).reason_code == "employer_not_in_profile"
    c, r = founder("title", "CEO", {"employer_found": False, "title_observed": "CEO"})
    assert decide(c, r, rules).reason_code == "employer_not_in_profile"


def test_title_unknown_threshold_in_rules_raises(rules):
    rules["tolerances"]["founder_background"]["min_title_level"] = "nonsense"
    c, r = founder("title", "CEO", {"title_observed": "Director"})
    with pytest.raises(ValueError):
        decide(c, r, rules)


def pos(start, end=None):
    return {"employer": "Flipkart", "title": "x", "start_date": start, "end_date": end}


@pytest.mark.parametrize("claimed,positions,label,reason", [
    (5, [pos("2015-01-01", "2020-01-01")], L.SUPPORTED, "tenure_within_tolerance"),
    (5, [pos("2015-01-01", "2019-09-01")], L.SUPPORTED, "tenure_within_tolerance"),   # 56 months, gap 4 <= 6
    (5, [pos("2015-01-01", "2018-01-01")], L.CONTRADICTED, "tenure_outside_tolerance"),
    (4, [pos("2024-01-01", None)], L.CONTRADICTED, "tenure_outside_tolerance"),       # current role: ends at record date
    (5, [pos("2015-01-01", "2017-01-01"), pos("2017-06-01", "2020-01-01")], L.SUPPORTED, "tenure_within_tolerance"),
])
def test_tenure(rules, claimed, positions, label, reason):
    c, r = founder("tenure_years", claimed, {"positions": positions})
    v = decide(c, r, rules)
    assert (v.label, v.reason_code) == (label, reason) and v.confidence is C.MEDIUM


def test_tenure_missing_dates_and_bad_value(rules):
    c, r = founder("tenure_years", 5, {"positions": [pos(None, None)]})
    assert decide(c, r, rules).reason_code == "missing_dates"
    c, r = founder("tenure_years", "five", {"positions": [pos("2015-01-01")]})
    assert decide(c, r, rules).reason_code == "claim_value_unusable"


def test_unsupported_founder_metric(rules):
    c, r = founder("education", "IIT", {})
    assert decide(c, r, rules).reason_code == "unsupported_metric"
