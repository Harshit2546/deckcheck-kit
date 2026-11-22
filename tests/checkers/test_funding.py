"""Tests for checkers/funding.py using recorded Crustdata fixtures."""

import json
from pathlib import Path
import pytest

from checker_fakes import make_ctx
from checkers.funding import check
from core.config import load_rules
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


def test_funding_check_specific_seed_round(crustdata_funding_fixture: dict) -> None:
    claim = Claim(
        id="claim_fund_1",
        run_id="run_1",
        slide=3,
        quote="Raised $2M in Seed round in 2022",
        type=ClaimType.FUNDING,
        subject="CargoPulse India",
        metric="round_amount",
        value=2000000,
        unit="USD",
        as_of="2022-04-10",
    )

    ctx = make_ctx(
        run_id="run_1",
        company_domain="cargopulse.com",
        company=crustdata_funding_fixture,
        deck_date="2024-01-10",
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
    assert ev.call_id == "call-test"
    assert ev.retrieved_at is not None


def test_funding_check_last_round(crustdata_funding_fixture: dict) -> None:
    claim = Claim(
        id="claim_fund_2",
        run_id="run_1",
        slide=4,
        quote="Closed $5M Series A round",
        type=ClaimType.FUNDING,
        subject="CargoPulse India",
        metric="round_amount",
        value=5000000,
        unit="USD",
    )

    ctx = make_ctx(
        run_id="run_1",
        company_domain="cargopulse.com",
        company=crustdata_funding_fixture,
        deck_date="2024-01-10",
    )

    result = check(claim, ctx)

    assert result.comparable is True
    assert result.observed["matched_round"] is not None
    assert result.observed["matched_round"]["amount"] == 5000000.0
    assert result.observed["matched_round"]["stage"] == "Series A"
    assert "amount" not in result.observed
    assert "round_type" not in result.observed
    assert "date" not in result.observed


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

    ctx = make_ctx(
        run_id="run_1",
        company_domain="cargopulse.com",
        company=crustdata_funding_fixture,
        deck_date="2024-01-10",
    )

    result = check(claim, ctx)

    assert result.comparable is True
    assert result.observed["total_raised"] == 7000000.0
    assert "amount" not in result.observed


def test_funding_check_missing_company() -> None:
    claim = Claim(
        id="claim_fund_4",
        run_id="run_1",
        slide=2,
        quote="Raised $1M",
        type=ClaimType.FUNDING,
        subject="NoFundingCo",
        metric="total_raised",
        value=1000000,
        unit="USD",
    )

    ctx = make_ctx(
        run_id="run_1",
        company_domain="nofunding.com",
        company={},
    )

    result = check(claim, ctx)
    assert result.comparable is True
    assert result.held_reason is None
    assert result.observed["identity"] == "not_found"
    assert len(result.evidence) == 0


@pytest.fixture
def locus_company_fixture() -> dict:
    """Fixture loaded from tests/fixtures/crustdata/deck_a_locus_company.json."""
    fixture_path = Path(__file__).parents[1] / "fixtures" / "crustdata" / "deck_a_locus_company.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data[0] if isinstance(data, list) else data


def test_funding_locus_slide_3_series_c(locus_company_fixture: dict) -> None:
    """Slide 3 claim matches Series C milestone with 50M USD on 2021-06-02."""
    claim = Claim(
        id="claim_slide_3",
        run_id="run_deck_a",
        slide=3,
        quote="We raised a $50M Series C in June 2021.",
        type=ClaimType.FUNDING,
        subject="Locus",
        metric="round_amount",
        value=50000000,
        unit="USD",
    )
    ctx = make_ctx(
        run_id="run_deck_a",
        company_domain="locus.sh",
        company=locus_company_fixture,
        deck_date="2026-11-15",
    )
    res = check(claim, ctx)
    assert res.comparable is True
    assert res.held_reason is None
    assert res.observed["identity"] == "confirmed"
    assert res.observed["currency"] == "USD"
    assert res.observed["record_date"] == "2021-06-02"

    matched = res.observed["matched_round"]
    assert matched is not None
    assert matched["stage"] == "series_c"
    assert matched["amount"] == 50000000.0
    assert matched["date"] == "2021-06-02"
    assert matched["currency"] == "USD"
    assert "GIC" in matched["investors"]
    assert "Alpha Wave Global" in matched["investors"]

    assert len(res.evidence) >= 1
    ev = res.evidence[0]
    assert ev.field_or_quote == "funding.milestones[2021-06-02].amount_usd"
    assert ev.record_date == "2021-06-02"
    assert ev.value == 50000000.0

    rules = load_rules()
    rules.setdefault("tolerances", {}).setdefault("funding", {})["max_record_age_days"] = 3650
    verdict = decide(claim, res, rules)
    assert verdict.label == VerdictLabel.SUPPORTED
    assert verdict.reason_code == "within_tolerance"


def test_funding_locus_slide_4_total_funding(locus_company_fixture: dict) -> None:
    """Slide 4 claim computes total_raised 78,750,000 USD and 3 undated rounds."""
    claim = Claim(
        id="claim_slide_4",
        run_id="run_deck_a",
        slide=4,
        quote="Total funding to date: $78.75M.",
        type=ClaimType.FUNDING,
        subject="Locus",
        metric="total_raised",
        value=78750000,
        unit="USD",
    )
    ctx = make_ctx(
        run_id="run_deck_a",
        company_domain="locus.sh",
        company=locus_company_fixture,
        deck_date="2026-11-15",
    )
    res = check(claim, ctx)
    assert res.comparable is True
    assert res.held_reason is None
    assert res.observed["identity"] == "confirmed"
    assert res.observed["currency"] == "USD"
    assert res.observed["total_raised"] == 78750000.0
    assert res.observed["undated_rounds"] == 3
    assert res.observed["record_date"] == "2021-06-02"
    assert res.observed["excluded_later_rounds"] == 0

    assert len(res.evidence) >= 1
    ev = res.evidence[0]
    assert ev.field_or_quote == "funding.milestones[2021-06-02].amount_usd"
    assert ev.record_date == "2021-06-02"

    rules = load_rules()
    rules.setdefault("tolerances", {}).setdefault("funding", {})["max_record_age_days"] = 3650
    verdict = decide(claim, res, rules)
    assert verdict.label == VerdictLabel.SUPPORTED
    assert verdict.reason_code == "within_tolerance_undated_rounds"
