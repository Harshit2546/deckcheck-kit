"""Tests for checkers/team_size.py using recorded Crustdata fixtures."""

import pytest

from checker_fakes import make_ctx
from checkers.team_size import check
from core.models import Claim, ClaimType, SourceType


@pytest.fixture
def crustdata_company_fixture() -> dict:
    """Recorded Crustdata company enrichment fixture with headcount timeseries."""
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
                        "timeseries": [
                            {"date": "2023-05-15", "employee_count": 35},
                            {"date": "2024-05-15", "employee_count": 45},
                            {"date": "2024-11-01", "employee_count": 55},
                        ],
                    },
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

    assert len(result.evidence) == 1
    ev_headcount = result.evidence[0]
    assert ev_headcount.field_or_quote == "headcount.timeseries[2024-05-15].employee_count"
    assert ev_headcount.value == 45.0
    assert ev_headcount.source_type == SourceType.CRUSTDATA_COMPANY
    assert ev_headcount.record_date == "2024-05-15"
    assert ev_headcount.call_id == "call-test"
    assert ev_headcount.retrieved_at is not None
    assert "https://api.crustdata.com" in ev_headcount.locator


def test_team_size_check_no_point_before_deck_date(crustdata_company_fixture: dict) -> None:
    """When all timeseries points are after deck date, add no headcount evidence (D13)."""
    claim = Claim(
        id="claim_team_old",
        run_id="run_1",
        slide=1,
        quote="20 employees",
        type=ClaimType.TEAM_SIZE,
        subject="SwiftRoute Logistics",
        metric="headcount",
        value=20,
    )
    ctx = make_ctx(
        run_id="run_1",
        company_domain="swiftroute.in",
        company=crustdata_company_fixture,
        deck_date="2022-01-01",  # Before any timeseries point (earliest is 2023-05-15)
    )

    result = check(claim, ctx)
    assert result.comparable is True
    assert result.held_reason is None
    assert len(result.evidence) == 0
    assert "headcount" not in result.observed
    assert result.observed["record_date"] is None


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


def _team_claim() -> Claim:
    return Claim(id="claim_team_snap", run_id="run_1", slide=5, quote="Team of 349 people",
                 type=ClaimType.TEAM_SIZE, subject="SwiftRoute Logistics", metric="headcount", value=349)


def _payload(timeseries: list[dict], total: object = 349) -> dict:
    return {"matches": [{"company_data": {"headcount": {"total": total, "timeseries": timeseries}}}]}


def test_snapshot_total_used_when_no_dated_point() -> None:
    """D17: no timeseries point on or before the reference date -> undated headcount.total."""
    ctx = make_ctx(run_id="run_snap", company_domain="swiftroute.in",
                   company=_payload([{"date": "2024-11-01", "employee_count": 55}]), deck_date="2024-06-01")
    result = check(_team_claim(), ctx)
    assert result.observed["headcount"] == 349.0
    assert result.observed["record_date"] is None
    assert result.observed["undated_items_used"] == 1
    assert len(result.evidence) == 1
    ev = result.evidence[0]
    assert ev.field_or_quote == "headcount.total"
    assert ev.record_date is None
    assert ev.value == 349.0
    assert ev.source_type == SourceType.CRUSTDATA_COMPANY
    assert ev.call_id == "call-test"


def test_snapshot_total_used_when_no_timeseries() -> None:
    ctx = make_ctx(run_id="run_snap2", company_domain="swiftroute.in", company=_payload([]),
                   deck_date="2024-06-01")
    result = check(_team_claim(), ctx)
    assert result.observed["headcount"] == 349.0 and result.evidence[0].record_date is None


def test_dated_point_wins_over_snapshot_total() -> None:
    ctx = make_ctx(run_id="run_snap3", company_domain="swiftroute.in",
                   company=_payload([{"date": "2024-05-15", "employee_count": 45}]), deck_date="2024-06-01")
    result = check(_team_claim(), ctx)
    assert result.observed["headcount"] == 45.0
    assert result.observed["record_date"] == "2024-05-15"
    assert result.observed["undated_items_used"] == 0
    assert [e.field_or_quote for e in result.evidence] == ["headcount.timeseries[2024-05-15].employee_count"]


@pytest.mark.parametrize("total", [None, "n/a", True])
def test_missing_or_bad_snapshot_total_gives_no_evidence(total: object) -> None:
    ctx = make_ctx(run_id="run_snap4", company_domain="swiftroute.in", company=_payload([], total=total),
                   deck_date="2024-06-01")
    result = check(_team_claim(), ctx)
    assert result.evidence == [] and "headcount" not in result.observed
