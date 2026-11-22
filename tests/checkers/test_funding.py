"""Tests for checkers/funding.py using recorded Crustdata fixtures."""

import pytest

from checkers.funding import check
from core.models import CheckContext, Claim, ClaimType, SourceType


@pytest.fixture
def crustdata_funding_fixture() -> dict:
    """Recorded Crustdata company enrichment fixture for funding testing."""
    return {
        "matches": [
            {
                "confidence_score": 0.99,
                "company_data": {
                    "crustdata_company_id": "comp_456",
                    "basic_info": {
                        "name": "CargoPulse India",
                        "primary_domain": "cargopulse.com",
                    },
                    "funding": {
                        "total_investment_usd": 7000000,
                        "last_round_amount_usd": 5000000,
                        "last_round_type": "Series A",
                        "last_fundraise_date": "2023-11-20T00:00:00Z",
                        "funding_rounds": [
                            {
                                "round_type": "Seed",
                                "amount_usd": 2000000,
                                "date": "2022-04-10",
                            },
                            {
                                "round_type": "Series A",
                                "amount_usd": 5000000,
                                "date": "2023-11-20",
                            },
                        ],
                    },
                    "updated_at": "2024-01-10T00:00:00Z",
                },
            }
        ]
    }


def test_funding_check_specific_seed_round(crustdata_funding_fixture: dict) -> None:
    claim = Claim(
        id="claim_fund_1",
        run_id="run_1",
        slide=3,
        quote="Raised $2M in Seed round in 2022",
        type=ClaimType.FUNDING,
        subject="CargoPulse India",
        metric="seed_round",
        value=2000000,
        unit="USD",
        as_of="2022",
    )

    ctx = CheckContext(
        run_id="run_1",
        company_domain="cargopulse.com",
        company=crustdata_funding_fixture,
    )

    result = check(claim, ctx)

    assert result.comparable is True
    assert result.held_reason is None
    assert result.observed["amount"] == 2000000.0
    assert result.observed["round_type"] == "Seed"
    assert result.observed["date"] == "2022-04-10"
    assert result.observed["total_raised"] == 7000000.0
    assert len(result.evidence) >= 1

    ev = result.evidence[0]
    assert ev.source_type == SourceType.CRUSTDATA_COMPANY
    assert ev.value == 2000000.0


def test_funding_check_last_round(crustdata_funding_fixture: dict) -> None:
    claim = Claim(
        id="claim_fund_2",
        run_id="run_1",
        slide=4,
        quote="Closed $5M Series A round",
        type=ClaimType.FUNDING,
        subject="CargoPulse India",
        metric="series_a",
        value=5000000,
        unit="USD",
    )

    ctx = CheckContext(
        run_id="run_1",
        company_domain="cargopulse.com",
        company=crustdata_funding_fixture,
    )

    result = check(claim, ctx)

    assert result.comparable is True
    assert result.observed["amount"] == 5000000.0
    assert result.observed["round_type"] == "Series A"
    assert result.observed["date"] == "2023-11-20"


def test_funding_check_total_funding(crustdata_funding_fixture: dict) -> None:
    claim = Claim(
        id="claim_fund_3",
        run_id="run_1",
        slide=4,
        quote="Total raised: $7M to date",
        type=ClaimType.FUNDING,
        subject="CargoPulse India",
        metric="total_raised",
        value=7000000,
        unit="USD",
    )

    ctx = CheckContext(
        run_id="run_1",
        company_domain="cargopulse.com",
        company=crustdata_funding_fixture,
    )

    result = check(claim, ctx)

    assert result.comparable is True
    assert result.observed["amount"] == 7000000.0
    assert result.observed["total_raised"] == 7000000.0


def test_funding_check_missing_company() -> None:
    claim = Claim(
        id="claim_fund_4",
        run_id="run_1",
        slide=2,
        quote="Raised $1M",
        type=ClaimType.FUNDING,
        subject="NoFundingCo",
        value=1000000,
    )

    ctx = CheckContext(
        run_id="run_1",
        company_domain="nofunding.com",
        company={},
    )

    result = check(claim, ctx)
    assert result.comparable is False
    assert result.held_reason is None
    assert len(result.evidence) == 0
