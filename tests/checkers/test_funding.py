"""Tests for checkers/funding.py using recorded Crustdata fixtures."""

import pytest

from checkers.funding import check
from core.models import Claim, ClaimType, SourceType, VerdictLabel
from verdict.engine import decide


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
                        "currency": "USD",
                        "total_investment_usd": 7000000,
                        "last_round_amount_usd": 5000000,
                        "last_round_type": "Series A",
                        "last_fundraise_date": "2023-11-20T00:00:00Z",
                        "funding_rounds": [
                            {
                                "round_type": "Seed",
                                "amount_usd": 2000000,
                                "date": "2022-04-10",
                                "investors": ["Venture Partners"],
                            },
                            {
                                "round_type": "Series A",
                                "amount_usd": 5000000,
                                "date": "2023-11-20",
                                "investors": ["Accel"],
                            },
                        ],
                    },
                    "updated_at": "2024-01-10T00:00:00Z",
                },
            }
        ]
    }


def test_funding_check_specific_seed_round(make_ctx, monkeypatch, crustdata_funding_fixture: dict) -> None:
    ctx = make_ctx(domain="cargopulse.com", deck_date="2024-01-10")
    monkeypatch.setattr("checkers.funding.get_company", lambda c, dom: (crustdata_funding_fixture, "call_fund_1"))

    claim = Claim(
        id="claim_fund_1",
        run_id=ctx.run.id,
        slide=3,
        quote="Raised $2M in Seed round in 2022",
        type=ClaimType.FUNDING,
        subject="CargoPulse India",
        metric="round_amount",
        value=2000000,
        unit="USD",
        as_of="2022-04-10",
    )

    result = check(claim, ctx)

    assert result.comparable is True
    assert result.held_reason is None
    assert result.observed["identity"] == "confirmed"
    assert result.observed["identity_signals"] == 2
    assert result.observed["currency"] == "USD"
    assert result.observed["total_raised"] == 2000000.0
    assert result.observed["matched_round"] is not None
    assert result.observed["matched_round"]["amount"] == 2000000.0
    assert result.observed["matched_round"]["stage"] == "Seed"
    assert result.observed["excluded_later_rounds"] == 1
    assert result.observed["undated_rounds"] == 0
    assert "Venture Partners" in result.observed["investors_found"]

    # Strict contract: no obsolete keys
    assert "amount" not in result.observed
    assert "round_type" not in result.observed
    assert "date" not in result.observed
    assert "as_of" not in result.observed

    assert len(result.evidence) >= 1
    ev = result.evidence[0]
    assert ev.source_type == SourceType.CRUSTDATA_COMPANY
    assert ev.value == 2000000.0
    assert ev.call_id == "call_fund_1"
    assert ev.retrieved_at is not None

    verdict = decide(claim, result, ctx.rules)
    assert verdict.label == VerdictLabel.SUPPORTED
    assert verdict.reason_code == "within_tolerance"


def test_funding_check_series_a_round(make_ctx, monkeypatch, crustdata_funding_fixture: dict) -> None:
    ctx = make_ctx(domain="cargopulse.com", deck_date="2024-01-10")
    monkeypatch.setattr("checkers.funding.get_company", lambda c, dom: (crustdata_funding_fixture, "call_fund_2"))

    claim = Claim(
        id="claim_fund_2",
        run_id=ctx.run.id,
        slide=4,
        quote="Closed $5M Series A round",
        type=ClaimType.FUNDING,
        subject="CargoPulse India",
        metric="round_amount",
        value=5000000,
        unit="USD",
    )

    result = check(claim, ctx)

    assert result.comparable is True
    assert result.observed["matched_round"] is not None
    assert result.observed["matched_round"]["amount"] == 5000000.0
    assert result.observed["matched_round"]["stage"] == "Series A"

    verdict = decide(claim, result, ctx.rules)
    assert verdict.label == VerdictLabel.SUPPORTED
    assert verdict.reason_code == "within_tolerance"


def test_funding_check_total_funding(make_ctx, monkeypatch, crustdata_funding_fixture: dict) -> None:
    ctx = make_ctx(domain="cargopulse.com", deck_date="2024-01-10")
    monkeypatch.setattr("checkers.funding.get_company", lambda c, dom: (crustdata_funding_fixture, "call_fund_3"))

    claim = Claim(
        id="claim_fund_3",
        run_id=ctx.run.id,
        slide=4,
        quote="Total raised: $7M to date",
        type=ClaimType.FUNDING,
        subject="CargoPulse India",
        metric="total_raised",
        value=7000000,
        unit="USD",
    )

    result = check(claim, ctx)

    assert result.comparable is True
    assert result.observed["total_raised"] == 7000000.0

    verdict = decide(claim, result, ctx.rules)
    assert verdict.label == VerdictLabel.SUPPORTED
    assert verdict.reason_code == "within_tolerance"


def test_funding_check_investor(make_ctx, monkeypatch, crustdata_funding_fixture: dict) -> None:
    ctx = make_ctx(domain="cargopulse.com", deck_date="2024-01-10")
    monkeypatch.setattr("checkers.funding.get_company", lambda c, dom: (crustdata_funding_fixture, "call_fund_4"))

    claim = Claim(
        id="claim_fund_inv",
        run_id=ctx.run.id,
        slide=4,
        quote="Backed by Venture Partners",
        type=ClaimType.FUNDING,
        subject="CargoPulse India",
        metric="investor",
        value="Venture Partners",
    )

    result = check(claim, ctx)
    assert "Venture Partners" in result.observed["investors_found"]

    verdict = decide(claim, result, ctx.rules)
    assert verdict.label == VerdictLabel.SUPPORTED
    assert verdict.reason_code == "investor_listed"


def test_funding_check_contradicted(make_ctx, monkeypatch, crustdata_funding_fixture: dict) -> None:
    ctx = make_ctx(domain="cargopulse.com", deck_date="2024-01-10")
    monkeypatch.setattr("checkers.funding.get_company", lambda c, dom: (crustdata_funding_fixture, "call_fund_5"))

    claim = Claim(
        id="claim_fund_contra",
        run_id=ctx.run.id,
        slide=4,
        quote="Closed $10M Series A round",
        type=ClaimType.FUNDING,
        subject="CargoPulse India",
        metric="round_amount",
        value=10000000,
        unit="USD",
    )

    result = check(claim, ctx)
    verdict = decide(claim, result, ctx.rules)
    assert verdict.label == VerdictLabel.CONTRADICTED
    assert verdict.reason_code == "outside_tolerance"


def test_funding_check_missing_company(make_ctx, monkeypatch) -> None:
    ctx = make_ctx(domain="nofunding.com")
    monkeypatch.setattr("checkers.funding.get_company", lambda c, dom: ({}, None))

    claim = Claim(
        id="claim_fund_none",
        run_id=ctx.run.id,
        slide=2,
        quote="Raised $1M",
        type=ClaimType.FUNDING,
        subject="NoFundingCo",
        metric="total_raised",
        value=1000000,
        unit="USD",
    )

    result = check(claim, ctx)
    assert result.comparable is True
    assert result.held_reason is None
    assert result.observed["identity"] == "not_found"
    assert len(result.evidence) == 0

    verdict = decide(claim, result, ctx.rules)
    assert verdict.label == VerdictLabel.CANNOT_VERIFY
    assert verdict.reason_code == "no_evidence"
