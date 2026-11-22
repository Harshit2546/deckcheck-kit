"""T33 tests: market_size and customer verdict rules (D16 web source), every label plus the never-CONTRADICTED cases.

Called by: pytest. Calls: verdict.engine with hand-built CheckResult fixtures (tests only).
"""

from core.models import ClaimType, Confidence as C, VerdictLabel as L
from tests.verdict.fakes import FRESH, make_claim, make_result
from verdict.engine import decide

MKT, CUST = ClaimType.MARKET_SIZE, ClaimType.CUSTOMER


def est(value, currency="USD", domain="a.com", date=FRESH):
    return {"value": value, "currency": currency, "url": f"https://{domain}/r", "domain": domain,
            "quote": f"{value} {currency}", "published_date": date, "evidence_id": "e1"}


def market(rules, value, estimates, unit="USD", **obs):
    observed = {"identity": "not_applicable", "identity_signals": 0, "estimates": estimates, **obs}
    v = decide(make_claim(MKT, "market_size", value, unit), make_result(observed), rules)
    return v.label, v.reason_code, v.confidence


def mention(independent, domain="news.com", date=FRESH):
    return {"url": f"https://{domain}/p", "domain": domain, "quote": "Acme serves BigCo",
            "published_date": date, "independent": independent, "evidence_id": "e1"}


def customer(rules, mentions, **obs):
    v = decide(make_claim(CUST, "customer", "BigCo"),
               make_result({"customer_name": "BigCo", "mentions": mentions, **obs}), rules)
    return v


# ---------- market_size ----------

def test_market_not_applicable_identity_passes_and_supports(rules):
    assert market(rules, 10e9, [est(11e9)]) == (L.SUPPORTED, "within_tolerance", C.MEDIUM)


def test_market_support_never_above_medium_even_exact(rules):
    assert market(rules, 10e9, [est(10e9), est(10e9, domain="b.com")])[2] is C.MEDIUM


def test_market_one_close_estimate_beats_disagreeing_ones(rules):
    ests = [est(40e9, domain="a.com"), est(41e9, domain="b.com"), est(12e9, domain="c.com")]
    assert market(rules, 10e9, ests)[0] is L.SUPPORTED


def test_market_currency_mismatch(rules):
    assert market(rules, 10e9, [est(10e9, currency="INR")])[:2] == (L.NOT_COMPARABLE, "currency_mismatch")


def test_market_other_currency_estimates_are_ignored(rules):
    """A matching INR figure does not support a USD claim; only USD estimates count."""
    ests = [est(10e9, currency="INR"), est(40e9, domain="a.com")]
    assert market(rules, 10e9, ests)[:2] == (L.CANNOT_VERIFY, "source_may_be_incomplete")


def test_market_single_disagreeing_source_is_never_contradicted(rules):
    assert market(rules, 10e9, [est(40e9)])[:2] == (L.CANNOT_VERIFY, "source_may_be_incomplete")


def test_market_two_agreeing_domains_contradict_at_most_medium(rules):
    ests = [est(40e9, domain="a.com"), est(45e9, domain="b.com")]
    assert market(rules, 10e9, ests) == (L.CONTRADICTED, "sources_agree_otherwise", C.MEDIUM)


def test_market_same_domain_twice_is_not_enough(rules):
    ests = [est(40e9, domain="a.com"), est(45e9, domain="a.com")]
    assert market(rules, 10e9, ests)[0] is L.CANNOT_VERIFY


def test_market_disagreeing_sources_that_disagree_with_each_other(rules):
    ests = [est(40e9, domain="a.com"), est(100e9, domain="b.com")]
    assert market(rules, 10e9, ests)[:2] == (L.CANNOT_VERIFY, "source_may_be_incomplete")


def test_market_estimate_after_reference_date_is_ignored(rules):
    assert market(rules, 10e9, [est(10e9, date="2026-06-01")])[:2] == (L.CANNOT_VERIFY, "no_evidence")


def test_market_estimate_too_old_is_ignored(rules):
    assert market(rules, 10e9, [est(10e9, date="2020-01-01")])[:2] == (L.CANNOT_VERIFY, "no_evidence")


def test_market_unusable_claim_value(rules):
    assert market(rules, "huge", [est(10e9)])[:2] == (L.CANNOT_VERIFY, "claim_value_unusable")


def test_not_applicable_identity_only_for_market_size(rules):
    v = decide(make_claim(ClaimType.TEAM_SIZE, "headcount", 40),
               make_result({"identity": "not_applicable", "identity_signals": 0, "headcount": 40}), rules)
    assert (v.label, v.reason_code) == (L.CANNOT_VERIFY, "identity_unclear")


# ---------- customer ----------

def test_customer_independent_mention_supports_medium(rules):
    v = customer(rules, [mention(False, "acme.com"), mention(True)])
    assert (v.label, v.reason_code, v.confidence) == (L.SUPPORTED, "independent_mention", C.MEDIUM)


def test_customer_self_published_only(rules):
    v = customer(rules, [mention(False, "acme.com")])
    assert (v.label, v.reason_code) == (L.CANNOT_VERIFY, "self_reported_only")
    assert v.missing == "A page from the customer or a news outlet naming the customer."


def test_customer_independent_must_be_true_not_truthy(rules):
    assert customer(rules, [mention("yes")]).reason_code == "self_reported_only"


def test_customer_mention_after_reference_date_ignored(rules):
    assert customer(rules, [mention(True, date="2026-06-01")]).reason_code == "no_evidence"


def test_customer_is_never_contradicted(rules):
    for mentions in ([], [mention(False, "acme.com")], [mention(True, date="2019-01-01")]):
        assert customer(rules, mentions).label is not L.CONTRADICTED


def test_customer_unclear_company_identity_stops_first(rules):
    assert customer(rules, [mention(True)], identity="unclear").reason_code == "identity_unclear"
