"""Tests for the shared order of checks in verdict/engine.py (DESIGN.md section 2), one test per row.

Called by: pytest. Calls: verdict.engine with hand-built CheckResult fixtures (tests only).
"""

import copy

import pytest

from core.models import CheckResult, ClaimType, Confidence, VerdictLabel as L
from tests.verdict.fakes import make_claim, make_result
from verdict.engine import REQUIRED_KEYS, check_rules, decide, held_verdict

HEAD = ClaimType.TEAM_SIZE


def claim(value=40):
    return make_claim(HEAD, "headcount", value, "people")


@pytest.mark.parametrize("reason", ["timeout", "error", "budget", "time", "no_checker"])
def test_row1_held_reason_wins_over_everything(rules, reason):
    res = CheckResult(observed={"held_detail": "x", "headcount": 40}, comparable=False, held_reason=reason)
    v = decide(claim(), res, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.HELD, reason, Confidence.LOW)
    assert v.missing


def test_held_verdict_helper():
    v = held_verdict("c9", "budget")
    assert v.label is L.HELD and v.claim_id == "c9" and "max_cost_inr" in v.missing


def test_row2_no_evidence(rules):
    v = decide(claim(), CheckResult(), rules)
    assert (v.label, v.reason_code) == (L.CANNOT_VERIFY, "no_evidence")
    v2 = decide(claim(), make_result({}, evidence=[]), rules)
    assert v2.reason_code == "no_evidence"


def test_row3_identity_unclear_flag(rules):
    v = decide(claim(), make_result({"headcount": 40, "identity": "unclear"}), rules)
    assert (v.label, v.reason_code) == (L.CANNOT_VERIFY, "identity_unclear")


def test_row3_too_few_signals_or_missing_identity(rules):
    one = decide(claim(), make_result({"headcount": 40, "identity_signals": 1}), rules)
    assert one.reason_code == "identity_unclear" and "1 signal" in one.explanation
    res = make_result({"headcount": 40})
    del res.observed["identity"]
    assert decide(claim(), res, rules).reason_code == "identity_unclear"


def test_row4_entity_not_found(rules):
    v = decide(claim(), make_result({"identity": "not_found"}), rules)
    assert (v.label, v.reason_code) == (L.CANNOT_VERIFY, "entity_not_found")


def test_row5_not_comparable_uses_checker_reason(rules):
    res = make_result({"not_comparable_reason": "metric_mismatch"}, comparable=False)
    v = decide(claim(), res, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.NOT_COMPARABLE, "metric_mismatch", Confidence.MEDIUM)
    assert v.missing


def test_row5_not_comparable_without_identity_key_is_still_not_comparable(rules):
    res = CheckResult(observed={"not_comparable_reason": "period_mismatch"}, comparable=False)
    res.evidence = make_result({}).evidence
    assert decide(claim(), res, rules).reason_code == "period_mismatch"


def test_row6_claim_value_unusable(rules):
    for bad in (None, "many", True, -3):
        v = decide(claim(bad), make_result({"headcount": 40}), rules)
        assert (v.label, v.reason_code) == (L.CANNOT_VERIFY, "claim_value_unusable"), bad


def test_row7_missing_record_date(rules):
    res = make_result({"headcount": 40, "record_date": None})
    assert decide(claim(), res, rules).reason_code == "missing_record_date"
    assert decide(claim(), make_result({"headcount": 40, "record_date": "last year"}), rules).reason_code == "missing_record_date"


def test_row8_no_reference_date(rules):
    res = make_result({"headcount": 40, "reference_date": None})
    c = make_claim(HEAD, "headcount", 40, "people", as_of=None)
    assert decide(c, res, rules).reason_code == "no_reference_date"


def test_reference_date_falls_back_to_claim_as_of(rules):
    res = make_result({"headcount": 40, "reference_date": None})
    assert decide(claim(), res, rules).label is L.SUPPORTED


def test_row9_stale_record(rules):
    res = make_result({"headcount": 40, "record_date": "2024-01-01"})
    v = decide(claim(), res, rules)
    assert (v.label, v.reason_code, v.confidence) == (L.NOT_COMPARABLE, "stale_record", Confidence.MEDIUM)


def test_record_after_reference_is_also_stale_when_far(rules):
    res = make_result({"headcount": 40, "record_date": "2027-06-01"})
    assert decide(claim(), res, rules).reason_code == "stale_record"


@pytest.mark.parametrize("source", ["pdf_metadata", "missing"])
def test_deck_date_not_given_caps_confidence_at_medium(rules, source):
    res = make_result({"headcount": 40, "reference_date_source": source})
    v = decide(claim(), res, rules)
    assert v.label is L.SUPPORTED and v.confidence is Confidence.MEDIUM


def test_unsupported_claim_type(rules):
    c = make_claim(ClaimType.CUSTOMER, "customer", "BigCo")
    v = decide(c, make_result({"anything": 1}), rules)
    assert (v.label, v.reason_code) == (L.CANNOT_VERIFY, "unsupported_metric")


def test_unsupported_metric_on_supported_type(rules):
    c = make_claim(HEAD, "attrition", 5)
    assert decide(c, make_result({"headcount": 40}), rules).reason_code == "unsupported_metric"


def test_evidence_ids_are_carried(rules):
    assert decide(claim(), make_result({"headcount": 40}), rules).evidence_ids == ["e1"]


def test_missing_rules_key_fails_fast_and_names_all_keys(rules):
    broken = copy.deepcopy(rules)
    del broken["verdict"]
    with pytest.raises(ValueError) as e:
        decide(claim(), make_result({"headcount": 40}), broken)
    for key in ("verdict.supported_margin", "verdict.strong_margin", "verdict.fresh_days"):
        assert key in str(e.value)
    with pytest.raises(ValueError):
        check_rules({})


def test_required_keys_all_exist_in_real_rules_except_verdict_block(rules):
    from core.config import load_rules, rule
    real = load_rules()
    for key in REQUIRED_KEYS:
        if key.startswith("verdict."):
            continue
        rule(real, key)
