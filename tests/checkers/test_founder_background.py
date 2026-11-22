"""Tests for checkers/founder_background.py using recorded Crustdata fakes."""

import pytest

from checker_fakes import make_ctx
from checkers.founder_background import check
from core.config import load_rules
from core.models import Claim, ClaimType, SourceType, VerdictLabel
from verdict.engine import decide


@pytest.fixture
def rules():
    r = load_rules()
    r["verdict"] = {"supported_margin": 0.5, "strong_margin": 2.0, "fresh_days": 90}
    return r


@pytest.fixture
def person_profile_fixture() -> dict:
    return {
        "basic_profile": {
            "name": "Priya Sharma",
            "current_title": "Co-founder & CTO",
        },
        "experience": {
            "employment_details": {
                "past": [
                    {
                        "employer": "Flipkart",
                        "title": "VP Engineering",
                        "start_date": "2015-01-01",
                        "end_date": "2020-01-01",
                    }
                ],
                "current": [
                    {
                        "employer": "LogiFast",
                        "title": "Co-founder & CTO",
                        "start_date": "2020-02-01",
                        "end_date": None,
                    }
                ],
            }
        },
        "updated_at": "2024-05-15T00:00:00Z",
    }


def test_founder_past_employer_success(person_profile_fixture: dict, rules: dict) -> None:
    claim = Claim(
        id="c_founder_1",
        run_id="run_1",
        slide=1,
        quote="Priya Sharma was previously VP Engineering at Flipkart",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Priya Sharma",
        metric="past_employer",
        value="Flipkart",
    )
    ctx = make_ctx(run_id="run_1", company=person_profile_fixture, deck_date="2024-05-15")

    result = check(claim, ctx)

    assert result.comparable is True
    assert result.held_reason is None
    assert result.observed["identity"] == "confirmed"
    assert result.observed["identity_signals"] == 2
    assert result.observed["employer_found"] is True
    assert len(result.observed["positions"]) == 1
    assert result.observed["positions"][0]["employer"] == "Flipkart"
    assert result.observed["positions"][0]["title"] == "VP Engineering"
    assert result.observed["title_observed"] == "VP Engineering"
    assert len(result.evidence) == 1
    assert result.evidence[0].source_type == SourceType.CRUSTDATA_PERSON

    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.SUPPORTED
    assert v.reason_code == "employer_listed"


def test_founder_title_check(person_profile_fixture: dict, rules: dict) -> None:
    claim = Claim(
        id="c_founder_title",
        run_id="run_1",
        slide=1,
        quote="Former VP Engineering at Flipkart",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Priya Sharma",
        metric="title",
        value="VP Engineering",
    )
    ctx = make_ctx(run_id="run_1", company=person_profile_fixture, deck_date="2024-05-15")

    result = check(claim, ctx)
    assert result.observed["employer_found"] is True
    assert result.observed["title_observed"] == "VP Engineering"

    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.SUPPORTED
    assert v.reason_code == "title_level_met"


def test_founder_title_contradicted(person_profile_fixture: dict, rules: dict) -> None:
    claim = Claim(
        id="c_founder_title_contra",
        run_id="run_1",
        slide=1,
        quote="Former CEO of Flipkart",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Priya Sharma",
        metric="title",
        value="CEO",
    )
    ctx = make_ctx(run_id="run_1", company=person_profile_fixture, deck_date="2024-05-15")

    result = check(claim, ctx)
    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.CONTRADICTED
    assert v.reason_code == "title_level_lower"


def test_founder_tenure_check(person_profile_fixture: dict, rules: dict) -> None:
    claim = Claim(
        id="c_founder_tenure",
        run_id="run_1",
        slide=1,
        quote="5 years as VP Engineering at Flipkart",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Priya Sharma",
        metric="tenure_years",
        value=5,
    )
    ctx = make_ctx(run_id="run_1", company=person_profile_fixture, deck_date="2024-05-15")

    result = check(claim, ctx)
    assert len(result.observed["positions"]) == 1

    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.SUPPORTED
    assert v.reason_code == "tenure_within_tolerance"


def test_founder_employer_not_found(person_profile_fixture: dict, rules: dict) -> None:
    claim = Claim(
        id="c_founder_missing_emp",
        run_id="run_1",
        slide=1,
        quote="Former VP at Amazon",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Priya Sharma",
        metric="past_employer",
        value="Amazon",
    )
    ctx = make_ctx(run_id="run_1", company=person_profile_fixture, deck_date="2024-05-15")

    result = check(claim, ctx)
    assert result.observed["employer_found"] is False
    assert len(result.observed["positions"]) == 0
    assert result.observed["title_observed"] is None

    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.CANNOT_VERIFY
    assert v.reason_code == "employer_not_in_profile"


def test_founder_missing_payload(rules: dict) -> None:
    claim = Claim(
        id="c_founder_none",
        run_id="run_1",
        slide=1,
        quote="Worked at Google",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Unknown Person",
        metric="past_employer",
        value="Google",
    )
    ctx = make_ctx(run_id="run_1", company=None)

    result = check(claim, ctx)
    assert result.comparable is True
    assert result.observed["identity"] == "not_found"
    assert len(result.evidence) == 0

    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.CANNOT_VERIFY
    assert v.reason_code == "no_evidence"
