"""T34 tests: the guarded undated fallback (DECISIONS D17) in verdict/engine.py and verdict/web_common.py.

Called by: pytest. Calls: verdict.engine with hand-built CheckResult fixtures (tests only).
"""

import pytest

from core.models import ClaimType, Confidence as C, Evidence, SourceType, VerdictLabel as L
from tests.verdict.fakes import FRESH, make_claim, make_result
from verdict.engine import decide

HEAD = ClaimType.TEAM_SIZE


def ev(retrieved="2026-01-20T10:00:00+00:00", record_date=None, eid="e1"):
    return Evidence(id=eid, claim_id="c1", source_type=SourceType.CRUSTDATA_COMPANY, locator="/api",
                    field_or_quote="headcount", value=None, record_date=record_date, retrieved_at=retrieved,
                    call_id="L1")


@pytest.fixture
def on(rules):
    rules["verdict"].update({"undated_fallback": True, "undated_max_deck_age_days": 90})
    return rules


def undated(rules, observed, claim=None, evidence=None):
    obs = {"record_date": None, **observed}
    return decide(claim or make_claim(HEAD, "headcount", 40), make_result(obs, evidence=evidence or [ev()]), rules)


# ---------- engine ----------

def test_fallback_on_recent_deck_decides_low_undated(on):
    v = undated(on, {"headcount": 41})
    assert (v.label, v.reason_code, v.confidence) == (L.SUPPORTED, "within_tolerance_undated", C.LOW)
    assert v.explanation.startswith("No dated record was found; this uses an undated source retrieved on 2026-01-20. ")
    assert "to replace the undated source" in v.missing


def test_fallback_contradiction_is_low_and_suffixed(on):
    v = undated(on, {"headcount": 200})
    assert (v.label, v.reason_code, v.confidence) == (L.CONTRADICTED, "outside_tolerance_undated", C.LOW)


def test_latest_retrieved_at_is_used(on):
    evs = [ev("2026-01-16T09:00:00+00:00", eid="a"), ev("2026-02-01T09:00:00+00:00", eid="b")]
    assert "retrieved on 2026-02-01" in undated(on, {"headcount": 40}, evidence=evs).explanation


def test_deck_older_than_limit_stays_missing_record_date(on):
    v = undated(on, {"headcount": 40}, evidence=[ev("2026-06-01T10:00:00+00:00")])   # 137 days after REF
    assert (v.label, v.reason_code) == (L.CANNOT_VERIFY, "missing_record_date")
    assert "undated_max_deck_age_days" in v.missing


def test_deck_after_retrieval_stays_missing_record_date(on):
    v = undated(on, {"headcount": 40}, evidence=[ev("2026-01-01T10:00:00+00:00")])
    assert v.reason_code == "missing_record_date"


def test_fallback_off_stays_missing_record_date(on):
    on["verdict"]["undated_fallback"] = False
    v = undated(on, {"headcount": 40})
    assert v.reason_code == "missing_record_date" and "undated_fallback is off" in v.missing


def test_fallback_keys_absent_means_off(rules):
    assert undated(rules, {"headcount": 40}).reason_code == "missing_record_date"


def test_dated_record_always_wins(on):
    v = decide(make_claim(HEAD, "headcount", 40), make_result({"headcount": 40}, evidence=[ev(record_date=FRESH)]), on)
    assert (v.reason_code, v.confidence) == ("within_tolerance", C.HIGH)


def test_undated_skips_record_after_as_of_and_stale(on):
    """No record date: neither D3 row can fire; the age guard on the deck replaces them."""
    assert undated(on, {"headcount": 40}).label is L.SUPPORTED


def test_undated_not_comparable_hiring_subset(on):
    """Deck A slide 8 shape: 'engineers' against all openings -> NOT_COMPARABLE metric_mismatch_undated."""
    c = make_claim(ClaimType.HIRING, "open_roles", 10, "engineers")
    v = undated(on, {"openings_count": 12}, claim=c)
    assert v.label is L.NOT_COMPARABLE and v.reason_code.endswith("_undated") and v.confidence is C.LOW


def test_team_growth_undated_cannot_match_window(on):
    c = make_claim(ClaimType.TEAM_GROWTH, "headcount_growth_yoy", 50, "%")
    v = undated(on, {"baseline_date": "2025-01-10", "growth_percent": 50}, claim=c)
    assert v.label is not L.SUPPORTED and v.label is not L.CONTRADICTED and v.confidence is C.LOW


# ---------- web items (market_size, customer) ----------

def est(value, date, domain="a.com"):
    return {"value": value, "currency": "USD", "url": f"https://{domain}/r", "domain": domain, "quote": "q",
            "published_date": date, "evidence_id": "e1"}


def market(rules, estimates, record_date=FRESH):
    obs = {"identity": "not_applicable", "identity_signals": 0, "estimates": estimates, "record_date": record_date}
    v = decide(make_claim(ClaimType.MARKET_SIZE, "market_size", 10e9, "USD"), make_result(obs, evidence=[ev()]), rules)
    return v.label, v.reason_code, v.confidence


def test_web_dated_item_wins_over_undated(on):
    assert market(on, [est(10e9, FRESH), est(40e9, None)]) == (L.SUPPORTED, "within_tolerance", C.MEDIUM)


def test_web_undated_items_used_when_no_dated_item(on):
    assert market(on, [est(10e9, None)], record_date=None) == (L.SUPPORTED, "within_tolerance_undated", C.LOW)


def test_web_undated_items_used_when_dated_ones_fail(on):
    """Dated item after the reference date is dropped (D3); the undated one is then used, flagged."""
    assert market(on, [est(10e9, "2026-06-01"), est(11e9, None)]) == (L.SUPPORTED, "within_tolerance_undated", C.LOW)


def test_web_undated_ignored_when_fallback_off(on):
    on["verdict"]["undated_fallback"] = False
    assert market(on, [est(10e9, "2026-06-01"), est(11e9, None)])[:2] == (L.CANNOT_VERIFY, "no_evidence")


def test_customer_undated_mention(on):
    m = {"url": "https://news.com/p", "domain": "news.com", "quote": "q", "published_date": None,
         "independent": True, "evidence_id": "e1"}
    v = undated(on, {"customer_name": "BigCo", "mentions": [m]}, claim=make_claim(ClaimType.CUSTOMER, "customer", "BigCo"))
    assert (v.label, v.reason_code, v.confidence) == (L.SUPPORTED, "independent_mention_undated", C.LOW)
    assert "(undated)" in v.explanation


def test_customer_undated_self_only_never_contradicted(on):
    m = {"url": "https://acme.com/p", "domain": "acme.com", "quote": "q", "published_date": None,
         "independent": False, "evidence_id": "e1"}
    v = undated(on, {"customer_name": "BigCo", "mentions": [m]}, claim=make_claim(ClaimType.CUSTOMER, "customer", "BigCo"))
    assert (v.label, v.reason_code) == (L.CANNOT_VERIFY, "self_reported_only_undated")
