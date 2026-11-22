"""Tests for checkers/prior_exit.py and checkers/company_fact.py."""

import pytest

from checker_fakes import make_ctx
from checkers.company_fact import check as check_company_fact
from checkers.prior_exit import check as check_prior_exit
from core.models import Claim, ClaimType, SourceType


@pytest.fixture
def prior_exit_fixture() -> dict:
    return {
        "basic_info": {
            "name": "QuickRoute Systems",
            "status": "acquired",
        },
        "revenue": {
            "acquisition_status": "acquired",
        },
        "funding": {
            "acquisitions": [
                {
                    "acquirer_name": "BigFleet Logistics",
                    "amount_usd": 45000000,
                    "date": "2021-08-15",
                }
            ]
        },
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def company_fact_fixture() -> dict:
    return {
        "basic_info": {
            "name": "LogiFast Inc",
            "primary_domain": "logifast.in",
            "year_founded": 2021,
            "company_type": "Privately Held",
            "status": "Operating",
        },
        "locations": {
            "headquarters": "Bengaluru, India",
        },
        "updated_at": "2024-03-01T00:00:00Z",
    }


def test_prior_exit_check_success(prior_exit_fixture: dict) -> None:
    claim = Claim(
        id="c_exit_1",
        run_id="run_1",
        slide=3,
        quote="Founder previously built QuickRoute, acquired by BigFleet for $45M in 2021",
        type=ClaimType.PRIOR_EXIT,
        subject="QuickRoute Systems",
    )
    ctx = make_ctx(run_id="run_1", company=prior_exit_fixture, deck_date="2024-01-01")

    result = check_prior_exit(claim, ctx)

    assert result.comparable is True
    assert result.held_reason is None
    assert result.observed["identity"] == "confirmed"
    assert result.observed["identity_signals"] == 2
    assert result.observed["exit_found"] is True
    assert result.observed["acquired_by"] == "BigFleet Logistics"
    assert result.observed["exit_amount"] == 45000000.0
    assert result.observed["exit_date"] == "2021-08-15"
    assert len(result.evidence) == 1
    assert result.evidence[0].source_type == SourceType.CRUSTDATA_COMPANY


def test_prior_exit_missing_payload() -> None:
    claim = Claim(
        id="c_exit_none",
        run_id="run_1",
        slide=3,
        quote="Previous exit for $10M",
        type=ClaimType.PRIOR_EXIT,
        subject="UnknownCo",
    )
    ctx = make_ctx(run_id="run_1", company=None)

    result = check_prior_exit(claim, ctx)
    assert result.comparable is True
    assert result.observed["identity"] == "not_found"
    assert len(result.evidence) == 0


def test_company_fact_check_success(company_fact_fixture: dict) -> None:
    claim = Claim(
        id="c_fact_1",
        run_id="run_1",
        slide=1,
        quote="Founded in 2021 and headquartered in Bengaluru",
        type=ClaimType.COMPANY_FACT,
        subject="LogiFast",
        metric="year_founded",
        value=2021,
    )
    ctx = make_ctx(run_id="run_1", company=company_fact_fixture, deck_date="2024-03-01")

    result = check_company_fact(claim, ctx)

    assert result.comparable is True
    assert result.held_reason is None
    assert result.observed["identity"] == "confirmed"
    assert result.observed["identity_signals"] == 2
    assert result.observed["year_founded"] == 2021
    assert result.observed["headquarters"] == "Bengaluru, India"
    assert result.observed["name"] == "LogiFast Inc"
    assert len(result.evidence) == 1
    assert result.evidence[0].source_type == SourceType.CRUSTDATA_COMPANY


def test_company_fact_missing_payload() -> None:
    claim = Claim(
        id="c_fact_none",
        run_id="run_1",
        slide=1,
        quote="Founded in 2020",
        type=ClaimType.COMPANY_FACT,
        subject="UnknownCo",
    )
    ctx = make_ctx(run_id="run_1", company=None)

    result = check_company_fact(claim, ctx)
    assert result.comparable is True
    assert result.observed["identity"] == "not_found"
    assert len(result.evidence) == 0
