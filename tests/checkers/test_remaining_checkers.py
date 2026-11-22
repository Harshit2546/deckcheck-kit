"""Tests for team_growth, hiring, traction, market_size, and competition checkers."""

import pytest

from checker_fakes import make_ctx
from checkers.competition import check as check_competition
from checkers.hiring import check as check_hiring
from checkers.team_growth import check as check_team_growth
from checkers.traction import check as check_traction
from core.models import Claim, ClaimType, SourceType


def test_team_growth_check() -> None:
    company_data = {
        "matches": [
            {
                "company_data": {
                    "headcount": {
                        "timeseries": [
                            {"date": "2023-03-01", "employee_count": 40},
                            {"date": "2024-03-01", "employee_count": 50},
                            {"date": "2024-09-01", "employee_count": 65},
                        ],
                    },
                }
            }
        ]
    }
    claim = Claim(
        id="c_growth",
        run_id="run_1",
        slide=2,
        quote="Team grew 25% year-to-date",
        type=ClaimType.TEAM_GROWTH,
        subject="LogiFast",
        value=25,
        unit="%",
    )
    ctx = make_ctx(run_id="run_1", company_domain="logifast.in", company=company_data, deck_date="2024-03-01")

    res = check_team_growth(claim, ctx)
    assert res.comparable is True
    assert res.observed["growth_percent"] == 25.0
    assert res.observed["growth_absolute"] == 10.0
    assert res.observed["record_date"] == "2024-03-01"
    assert "as_of" not in res.observed
    assert len(res.evidence) == 2
    assert res.evidence[0].call_id == "call-test"
    assert res.evidence[0].retrieved_at is not None
    assert "headcount.timeseries" in res.evidence[0].field_or_quote


def test_team_growth_no_point_before_deck_date() -> None:
    """When fewer than two timeseries points are on or before deck date, add no evidence (D13)."""
    company_data = {
        "headcount": {
            "timeseries": [
                {"date": "2024-03-01", "employee_count": 50},
            ]
        }
    }
    claim = Claim(
        id="c_growth_old",
        run_id="run_1",
        slide=2,
        quote="Team grew 25%",
        type=ClaimType.TEAM_GROWTH,
        subject="LogiFast",
        value=25,
        unit="%",
    )
    ctx = make_ctx(run_id="run_1", company_domain="logifast.in", company=company_data, deck_date="2022-01-01")

    res = check_team_growth(claim, ctx)
    assert res.comparable is True
    assert len(res.evidence) == 0
    assert "growth_percent" not in res.observed
    assert res.observed["record_date"] is None


def test_hiring_check() -> None:
    company_data = {
        "matches": [
            {
                "company_data": {
                    "hiring": {
                        "openings_count": 8,
                        "openings_growth_percent": 33.3,
                        "recent_openings": ["Route Planner", "Warehouse Tech Lead"],
                    },
                    "updated_at": "2024-04-15",
                }
            }
        ]
    }
    claim = Claim(
        id="c_hiring",
        run_id="run_1",
        slide=3,
        quote="Currently hiring 8 open roles across engineering and ops",
        type=ClaimType.HIRING,
        subject="LogiFast",
        value=8,
        unit="roles",
    )
    ctx = make_ctx(run_id="run_1", company_domain="logifast.in", company=company_data, deck_date="2024-04-15")

    res = check_hiring(claim, ctx)
    assert res.comparable is True
    assert res.observed["openings_count"] == 8
    assert res.observed["growth_percent"] == 33.3
    assert "Route Planner" in res.observed["openings"]
    assert len(res.evidence) == 2
    assert res.evidence[0].call_id == "call-test"
    assert res.evidence[0].retrieved_at is not None
    # updated_at (2024-04-15) is the provider's refresh date, never the record date (D13, D17).
    assert res.observed["record_date"] is None
    assert [e.record_date for e in res.evidence] == [None, None]
    assert [e.field_or_quote for e in res.evidence] == ["hiring.openings_count",
                                                        "hiring.openings_growth_percent"]
    assert res.observed["undated_items_used"] == 2


def test_hiring_top_level_updated_at_is_not_a_record_date() -> None:
    payload = {"updated_at": "2024-04-15T10:00:00Z", "hiring": {"openings_count": 40}}
    claim = Claim(id="c_hiring_2", run_id="run_1", slide=8, quote="We are hiring 40 engineers",
                  type=ClaimType.HIRING, subject="Locus", value=40, unit="engineers")
    ctx = make_ctx(run_id="run_hire2", company_domain="locus.sh", company=payload, deck_date="2024-04-15")
    res = check_hiring(claim, ctx)
    assert res.observed["openings_count"] == 40
    assert res.observed["record_date"] is None
    assert res.evidence[0].record_date is None


def test_traction_check() -> None:
    company_data = {
        "matches": [
            {
                "company_data": {
                    "revenue": {
                        "annual_revenue_usd": 4500000,
                        "growth_rate": 120.0,
                    },
                    "traction": {
                        "arr": 5000000,
                    },
                    "updated_at": "2024-02-28",
                }
            }
        ]
    }
    claim = Claim(
        id="c_traction",
        run_id="run_1",
        slide=4,
        quote="Reached $5M ARR with 120% annual growth",
        type=ClaimType.TRACTION,
        subject="LogiFast",
        metric="arr",
        value=5000000,
        unit="USD",
    )
    ctx = make_ctx(run_id="run_1", company_domain="logifast.in", company=company_data, deck_date="2024-02-28")

    res = check_traction(claim, ctx)
    assert res.comparable is True
    assert res.observed["revenue"] == 4500000.0
    assert res.observed["arr"] == 5000000.0
    assert res.observed["growth_rate"] == 120.0
    assert len(res.evidence) == 3
    assert res.evidence[0].call_id == "call-test"
    assert res.evidence[0].retrieved_at is not None


def test_competition_check() -> None:
    company_data = {
        "matches": [
            {
                "company_data": {
                    "competitors": ["Delhivery", "Shadowfax", "Shiprocket"],
                    "updated_at": "2024-05-01",
                }
            }
        ]
    }
    claim = Claim(
        id="c_comp",
        run_id="run_1",
        slide=6,
        quote="Competing with Delhivery and Shadowfax in hyperlocal delivery",
        type=ClaimType.COMPETITION,
        subject="LogiFast",
    )
    ctx = make_ctx(run_id="run_1", company_domain="logifast.in", company=company_data, deck_date="2024-05-01")

    res = check_competition(claim, ctx)
    assert res.comparable is True
    assert "Delhivery" in res.observed["competitors"]
    assert "Shadowfax" in res.observed["competitors"]
    assert len(res.evidence) == 1
    assert res.evidence[0].call_id == "call-test"
    assert res.evidence[0].retrieved_at is not None
