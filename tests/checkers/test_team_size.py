"""Tests for checkers/team_size.py using recorded Crustdata fixtures."""

import pytest

from checker_fakes import make_ctx
from checkers.team_size import check
from core.models import Claim, ClaimType, SourceType


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


def test_team_size_check_success(crustdata_company_fixture: dict) -> None:
    claim = Claim(
        id="claim_team_1",
        run_id="run_1",
        slide=2,
        quote="Team of 45 full-time logistics specialists",
        type=ClaimType.TEAM_SIZE,
        subject="SwiftRoute Logistics",
        metric="headcount",
        value=45,
        unit="employees",
    )

    ctx = make_ctx(
        run_id="run_1",
        company_domain="swiftroute.in",
        company=crustdata_company_fixture,
        deck_date="2024-05-15",
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
    assert ev_headcount.call_id == "call-test"
    assert ev_headcount.retrieved_at is not None
    assert "https://api.crustdata.com" in ev_headcount.locator


def test_team_size_check_missing_data() -> None:
    claim = Claim(
        id="claim_team_2",
        run_id="run_1",
        slide=1,
        quote="40 employees",
        type=ClaimType.TEAM_SIZE,
        subject="EmptyCorp",
        value=40,
    )
    ctx = make_ctx(
        run_id="run_1",
        company_domain="empty.com",
        company={},
    )

    result = check(claim, ctx)
    assert result.comparable is True
    assert result.held_reason is None
    assert result.observed["identity"] == "not_found"
    assert len(result.evidence) == 0
