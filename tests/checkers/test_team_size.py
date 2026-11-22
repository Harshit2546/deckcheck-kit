"""Tests for checkers/team_size.py using recorded Crustdata fixtures."""

import pytest

from checkers.team_size import check
from core.models import Claim, ClaimType, SourceType, VerdictLabel
from verdict.engine import decide


@pytest.fixture
def crustdata_company_fixture() -> dict:
    """Recorded Crustdata company enrichment fixture for team size testing."""
    return {
        "matches": [
            {
                "confidence_score": 0.98,
                "company_data": {
                    "crustdata_company_id": "comp_123",
                    "basic_info": {
                        "name": "SwiftRoute Logistics",
                        "primary_domain": "swiftroute.in",
                        "employee_count_range": "11-50",
                    },
                    "headcount": {
                        "total": 45,
                        "growth_percent": 18.5,
                        "growth_absolute": 7,
                    },
                    "updated_at": "2024-05-15T12:00:00Z",
                },
            }
        ]
    }


def test_team_size_check_success(make_ctx, monkeypatch, crustdata_company_fixture: dict) -> None:
    ctx = make_ctx(domain="swiftroute.in", deck_date="2024-05-15")
    monkeypatch.setattr("checkers.team_size.get_company", lambda c, dom: (crustdata_company_fixture, "call_123"))

    claim = Claim(
        id="claim_team_1",
        run_id=ctx.run.id,
        slide=2,
        quote="Team of 45 full-time logistics specialists",
        type=ClaimType.TEAM_SIZE,
        subject="SwiftRoute Logistics",
        metric="headcount",
        value=45,
        unit="employees",
    )

    result = check(claim, ctx)

    assert result.comparable is True
    assert result.held_reason is None
    assert result.observed["headcount"] == 45.0
    assert result.observed["headcount_range"] == [11.0, 50.0]
    assert result.observed["identity"] == "confirmed"
    assert result.observed["identity_signals"] == 2
    assert result.observed["record_date"] == "2024-05-15"
    assert result.observed["reference_date"] == "2024-05-15"
    assert result.observed["reference_date_source"] == "input"

    # Strict contract: no obsolete keys
    assert "range" not in result.observed
    assert "as_of" not in result.observed

    assert len(result.evidence) == 2
    ev_headcount = next(e for e in result.evidence if e.field_or_quote == "headcount.total")
    assert ev_headcount.value == 45.0
    assert ev_headcount.source_type == SourceType.CRUSTDATA_COMPANY
    assert ev_headcount.record_date == "2024-05-15"
    assert ev_headcount.call_id == "call_123"
    assert ev_headcount.retrieved_at is not None
    assert "https://api.crustdata.com" in ev_headcount.locator

    # Check verdict engine integration
    verdict = decide(claim, result, ctx.rules)
    assert verdict.label == VerdictLabel.SUPPORTED
    assert verdict.reason_code == "within_tolerance"


def test_team_size_check_band_fallback(make_ctx, monkeypatch) -> None:
    band_fixture = {
        "basic_info": {"employee_count_range": "11-50"},
        "updated_at": "2024-05-15T00:00:00Z",
    }
    ctx = make_ctx(domain="swiftroute.in", deck_date="2024-05-15")
    monkeypatch.setattr("checkers.team_size.get_company", lambda c, dom: (band_fixture, "call_band_1"))

    claim = Claim(
        id="claim_team_band",
        run_id=ctx.run.id,
        slide=1,
        quote="30 team members",
        type=ClaimType.TEAM_SIZE,
        subject="SwiftRoute Logistics",
        metric="headcount",
        value=30,
        unit="people",
    )

    result = check(claim, ctx)
    assert result.comparable is True
    assert result.observed["headcount_range"] == [11.0, 50.0]
    assert "headcount" not in result.observed

    verdict = decide(claim, result, ctx.rules)
    assert verdict.label == VerdictLabel.SUPPORTED
    assert verdict.reason_code == "within_band"


def test_team_size_contradicted(make_ctx, monkeypatch, crustdata_company_fixture: dict) -> None:
    ctx = make_ctx(domain="swiftroute.in", deck_date="2024-05-15")
    monkeypatch.setattr("checkers.team_size.get_company", lambda c, dom: (crustdata_company_fixture, "call_123"))

    claim = Claim(
        id="claim_team_contra",
        run_id=ctx.run.id,
        slide=2,
        quote="Team of 100 people",
        type=ClaimType.TEAM_SIZE,
        subject="SwiftRoute Logistics",
        metric="headcount",
        value=100,
        unit="people",
    )

    result = check(claim, ctx)
    verdict = decide(claim, result, ctx.rules)
    assert verdict.label == VerdictLabel.CONTRADICTED
    assert verdict.reason_code == "outside_tolerance"


def test_team_size_check_missing_data(make_ctx, monkeypatch) -> None:
    ctx = make_ctx(domain="empty.com")
    monkeypatch.setattr("checkers.team_size.get_company", lambda c, dom: ({}, None))

    claim = Claim(
        id="claim_team_2",
        run_id=ctx.run.id,
        slide=1,
        quote="40 employees",
        type=ClaimType.TEAM_SIZE,
        subject="EmptyCorp",
        metric="headcount",
        value=40,
    )

    result = check(claim, ctx)
    assert result.comparable is True
    assert result.held_reason is None
    assert result.observed["identity"] == "not_found"
    assert len(result.evidence) == 0

    verdict = decide(claim, result, ctx.rules)
    assert verdict.label == VerdictLabel.CANNOT_VERIFY
    assert verdict.reason_code == "no_evidence"
