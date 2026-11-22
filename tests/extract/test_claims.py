"""Tests for extract/claims.py."""

import json
from pathlib import Path
import pytest
from reportlab.pdfgen import canvas

from core import store
from core.config import load_rules
from core.models import (
    Claim,
    ClaimState,
    ClaimType,
    Provider,
    Run,
    RunContext,
    RunInput,
    RunState,
    now_iso,
)
from extract.claims import (
    extract_claims,
    run,
    verify_claim_quote,
    verify_claim_quotes,
)


@pytest.fixture
def ctx(tmp_path: Path) -> RunContext:
    conn = store.connect(tmp_path / "test.db")
    rules = load_rules()
    deck_path = tmp_path / "sample_deck.pdf"
    c = canvas.Canvas(str(deck_path))
    c.drawString(100, 750, "SwiftRoute India. Team size: 65 members.")
    c.showPage()
    c.save()

    run_input = RunInput(
        deck_path=str(deck_path),
        domain="swiftroute.in",
        deck_date="2024-01-01",
        deck_date_source="input",
    )
    r = Run(
        id="test-run-1",
        input=run_input,
        state=RunState.CREATED,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    store.insert_run(conn, r)
    ctx_obj = RunContext(conn=conn, rules=rules, run=r)
    yield ctx_obj
    conn.close()


def test_verify_claim_quote_exact_and_normalized() -> None:
    slide_text = "Acme Corp raised $5M in Series A.\nWe have 42 employees across 2 offices."

    # Exact match
    assert verify_claim_quote("raised $5M in Series A", slide_text) is True

    # Whitespace normalized across line breaks
    assert verify_claim_quote("42 employees across 2 offices", slide_text) is True

    # Invented quote not on slide
    assert verify_claim_quote("We raised $10M from Sequoia", slide_text) is False
    assert verify_claim_quote("", slide_text) is False


def test_verify_claim_quotes_drops_invented_quote() -> None:
    slides = {
        1: "Welcome to SwiftRoute Logistics. Founded in 2021 by Jane Doe.",
        2: "Key Metrics: 50 full-time employees. Seed funding: $1.5M.",
    }

    claim_valid = Claim(
        id="c1",
        run_id="run_1",
        slide=2,
        quote="50 full-time employees",
        type=ClaimType.TEAM_SIZE,
        subject="SwiftRoute Logistics",
        metric="headcount",
        value=50,
        unit="employees",
    )

    claim_invented = Claim(
        id="c2",
        run_id="run_1",
        slide=2,
        quote="Projected $100M revenue by next year",  # Not on slide 2!
        type=ClaimType.TRACTION,
        subject="SwiftRoute Logistics",
        metric="revenue",
        value=100000000,
        unit="USD",
    )

    claim_wrong_slide = Claim(
        id="c3",
        run_id="run_1",
        slide=1,
        quote="Seed funding: $1.5M",  # On slide 2, NOT on slide 1
        type=ClaimType.FUNDING,
        subject="SwiftRoute Logistics",
        value=1500000,
    )

    claims = [claim_valid, claim_invented, claim_wrong_slide]
    verified = verify_claim_quotes(claims, slides=slides, run_id="run_1")

    assert len(verified) == 1
    assert verified[0].id == claim_valid.id
    assert verified[0].quote == "50 full-time employees"


def test_extract_claims_with_llm_records_ledger_and_filters_quotes(ctx: RunContext) -> None:
    slides = {
        1: "SwiftRoute India. Team size: 65 members.",
        2: "Raised $3M Seed Round in June 2023.",
    }

    # Simulated LLM response that includes 2 real claims and 1 invented quote
    simulated_llm_json = json.dumps([
        {
            "slide": 1,
            "quote": "Team size: 65 members",
            "type": "team_size",
            "subject": "SwiftRoute",
            "metric": "headcount",
            "value": 65,
            "unit": "members",
            "as_of": "2024",
        },
        {
            "slide": 2,
            "quote": "Raised $3M Seed Round",
            "type": "funding",
            "subject": "SwiftRoute",
            "metric": "seed_round",
            "value": 3000000,
            "unit": "USD",
            "as_of": "2023-06",
        },
        {
            "slide": 2,
            "quote": "Valued at $100M post-money",  # Invented!
            "type": "funding",
            "subject": "SwiftRoute",
            "metric": "valuation",
            "value": 100000000,
            "unit": "USD",
        },
    ])

    def mock_caller(prompt: str, model: str | None) -> tuple[str, str, int, int]:
        return simulated_llm_json, "mock-gemini-flash", 350, 120

    claims = extract_claims(
        slides=slides,
        ctx=ctx,
        llm_caller=mock_caller,
    )

    # 1. Verification: invented quote was rejected
    assert len(claims) == 2
    quotes = [c.quote for c in claims]
    assert "Team size: 65 members" in quotes
    assert "Raised $3M Seed Round" in quotes
    assert "Valued at $100M post-money" not in quotes

    # 2. Verification: ledger row was written to Store
    ledger_entries = store.list_ledger(ctx.conn, ctx.run.id)
    assert len(ledger_entries) == 1
    entry = ledger_entries[0]
    assert entry.run_id == ctx.run.id
    assert entry.provider == Provider.LLM
    assert entry.endpoint_or_model == "mock-gemini-flash"
    assert entry.tokens_in == 350
    assert entry.tokens_out == 120
    assert entry.cost_inr > 0
    assert entry.ok is True
    assert entry.error is None


def test_extract_claims_failed_call_still_writes_ledger(ctx: RunContext) -> None:
    slides = {1: "Some slide text"}

    def failing_caller(prompt: str, model: str | None) -> tuple[str, str, int, int]:
        raise ConnectionError("LLM API network timeout")

    with pytest.raises(RuntimeError, match="LLM extraction failed"):
        extract_claims(
            slides=slides,
            ctx=ctx,
            llm_caller=failing_caller,
        )

    # Hard rule: failed calls must write a ledger row
    ledger_entries = store.list_ledger(ctx.conn, ctx.run.id)
    assert len(ledger_entries) == 1
    entry = ledger_entries[0]
    assert entry.run_id == ctx.run.id
    assert entry.provider == Provider.LLM
    assert entry.ok is False
    assert "LLM API network timeout" in (entry.error or "")


def test_run_stage_extracts_claims(ctx: RunContext) -> None:
    simulated_llm_json = json.dumps([
        {
            "slide": 1,
            "quote": "Team size: 65 members",
            "type": "team_size",
            "subject": "SwiftRoute",
            "metric": "headcount",
            "value": 65,
            "unit": "members",
        }
    ])

    def mock_caller(prompt: str, model: str | None) -> tuple[str, str, int, int]:
        return simulated_llm_json, "mock-gemini-flash", 200, 50

    claims = run(ctx, llm_caller=mock_caller)
    assert len(claims) == 1
    assert claims[0].quote == "Team size: 65 members"
    assert claims[0].type == ClaimType.TEAM_SIZE
