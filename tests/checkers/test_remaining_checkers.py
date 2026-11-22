"""Tests for team_growth, hiring, traction, market_size, and competition checkers."""

import sys
import types
import pytest

from checkers.competition import check as check_competition
from checkers.hiring import check as check_hiring
from checkers.market_size import check as check_market_size
from checkers.team_growth import check as check_team_growth
from checkers.traction import check as check_traction
from core.models import Claim, ClaimType, SourceType


def test_team_growth_check(make_ctx, monkeypatch) -> None:
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
    ctx = make_ctx(domain="logifast.in", deck_date="2024-03-01")
    monkeypatch.setattr("checkers.team_growth.get_company", lambda c, dom: (company_data, "call_growth_1"))

    claim = Claim(
        id="c_growth",
        run_id=ctx.run.id,
        slide=2,
        quote="Team grew 25% year-to-date",
        type=ClaimType.TEAM_GROWTH,
        subject="LogiFast",
        value=25,
        unit="%",
    )

    res = check_team_growth(claim, ctx)
    assert res.comparable is True
    assert res.observed["growth_percent"] == 25.0
    assert res.observed["growth_absolute"] == 10.0
    assert res.observed["record_date"] == "2024-03-01"
    assert len(res.evidence) == 2
    assert res.evidence[0].call_id == "call_growth_1"
    assert res.evidence[0].retrieved_at is not None


def test_hiring_check(make_ctx, monkeypatch) -> None:
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
    ctx = make_ctx(domain="logifast.in", deck_date="2024-04-15")
    monkeypatch.setattr("checkers.hiring.get_company", lambda c, dom: (company_data, "call_hiring_1"))

    claim = Claim(
        id="c_hiring",
        run_id=ctx.run.id,
        slide=3,
        quote="Currently hiring 8 open roles across engineering and ops",
        type=ClaimType.HIRING,
        subject="LogiFast",
        value=8,
        unit="roles",
    )

    res = check_hiring(claim, ctx)
    assert res.comparable is True
    assert res.observed["openings_count"] == 8
    assert res.observed["growth_percent"] == 33.3
    assert "Route Planner" in res.observed["openings"]
    assert len(res.evidence) == 2
    assert res.evidence[0].call_id == "call_hiring_1"
    assert res.evidence[0].retrieved_at is not None


def test_traction_check(make_ctx, monkeypatch) -> None:
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
    ctx = make_ctx(domain="logifast.in", deck_date="2024-02-28")
    monkeypatch.setattr("checkers.traction.get_company", lambda c, dom: (company_data, "call_traction_1"))

    claim = Claim(
        id="c_traction",
        run_id=ctx.run.id,
        slide=4,
        quote="Reached $5M ARR with 120% annual growth",
        type=ClaimType.TRACTION,
        subject="LogiFast",
        metric="arr",
        value=5000000,
        unit="USD",
    )

    res = check_traction(claim, ctx)
    assert res.comparable is True
    assert res.observed["revenue"] == 4500000.0
    assert res.observed["arr"] == 5000000.0
    assert res.observed["growth_rate"] == 120.0
    assert len(res.evidence) == 3
    assert res.evidence[0].call_id == "call_traction_1"
    assert res.evidence[0].retrieved_at is not None


def test_market_size_check(make_ctx, monkeypatch) -> None:
    market_benchmark = {
        "market_size": 215000000000,
        "unit": "USD",
        "year": "2028",
        "quote": "India 3PL market projected to reach $215B",
        "record_date": "2024-01-15",
        "source_url": "https://logistics-reports.org/india-3pl",
        "call_id": "call_market_1",
    }
    ctx = make_ctx(domain="logifast.in", deck_date="2024-01-15")

    if "sources" not in sys.modules:
        sys.modules["sources"] = types.ModuleType("sources")
    if "sources.web" not in sys.modules:
        m = types.ModuleType("sources.web")
        sys.modules["sources.web"] = m
        setattr(sys.modules["sources"], "web", m)
    monkeypatch.setattr(
        "sources.web.search_market_data",
        lambda q, run_id=None: market_benchmark,
        raising=False,
    )

    claim = Claim(
        id="c_market",
        run_id=ctx.run.id,
        slide=5,
        quote="India 3PL market estimated at $215B by 2028",
        type=ClaimType.MARKET_SIZE,
        subject="India 3PL",
        value=215000000000,
        unit="USD",
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


def test_competition_check(make_ctx, monkeypatch) -> None:
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
    ctx = make_ctx(domain="logifast.in", deck_date="2024-05-01")
    monkeypatch.setattr("checkers.competition.get_company", lambda c, dom: (company_data, "call_comp_1"))

    claim = Claim(
        id="c_comp",
        run_id=ctx.run.id,
        slide=6,
        quote="Competing with Delhivery and Shadowfax in hyperlocal delivery",
        type=ClaimType.COMPETITION,
        subject="LogiFast",
    )

    res = check_competition(claim, ctx)
    assert res.comparable is True
    assert "Delhivery" in res.observed["competitors"]
    assert "Shadowfax" in res.observed["competitors"]
    assert len(res.evidence) == 1
    assert res.evidence[0].call_id == "call_comp_1"
    assert res.evidence[0].retrieved_at is not None
