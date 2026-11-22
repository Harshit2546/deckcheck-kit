"""Tests for team_growth, hiring, traction, market_size, and competition checkers."""

import pytest

from checker_fakes import make_ctx
from checkers.competition import check as check_competition
from checkers.hiring import check as check_hiring
from checkers.market_size import check as check_market_size
from checkers.team_growth import check as check_team_growth
from checkers.traction import check as check_traction
from core.models import Claim, ClaimType, SourceType


def test_team_growth_check() -> None:
    company_data = {
        "matches": [
            {
                "company_data": {
                    "headcount": {
                        "growth_percent": 25.0,
                        "growth_absolute": 10,
                    },
                    "updated_at": "2024-03-01T00:00:00Z",
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


def test_market_size_check() -> None:
    market_benchmark = {
        "market_size": 215000000000,
        "unit": "USD",
        "year": "2028",
        "quote": "India 3PL market projected to reach $215B",
        "record_date": "2024-01-15",
        "source_url": "https://logistics-reports.org/india-3pl",
        "call_id": "call_market_1",
    }
    claim = Claim(
        id="c_market",
        run_id="run_1",
        slide=5,
        quote="India 3PL market estimated at $215B by 2028",
        type=ClaimType.MARKET_SIZE,
        subject="India 3PL",
        value=215000000000,
        unit="USD",
    )
    ctx = make_ctx(
        run_id="run_1",
        company_domain="logifast.in",
        extras={"market_data": market_benchmark},
        deck_date="2024-01-15",
    )

    res = check_market_size(claim, ctx)
    assert res.comparable is True
    assert res.observed["market_size"] == 215000000000.0
    assert res.observed["unit"] == "USD"
    assert res.observed["year"] == "2028"
    assert len(res.evidence) == 1
    assert res.evidence[0].source_type == SourceType.WEB_PAGE
    assert res.evidence[0].locator == "https://logistics-reports.org/india-3pl"
    assert res.evidence[0].call_id == "call_market_1"
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
