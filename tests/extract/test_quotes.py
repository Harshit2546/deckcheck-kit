"""Tests for extract/quotes.py: the LLM call is monkeypatched; no live calls."""

import json
from pathlib import Path
from typing import Any

import pytest

from core import store
from core.config import load_rules, rule
from core.models import Provider, Run, RunContext, RunInput, RunState, now_iso
from extract import quotes
from extract.quotes import parse_amount, pick_quote

PAGE = ("Industry report 2023. India's logistics market was valued at ₹75,000 crore in 2023, "
        "according to analysts.\n\nSwiftRoute   works with  Acme Foods across five cities.")


@pytest.fixture
def ctx(tmp_path: Path) -> Any:
    conn = store.connect(tmp_path / "test.db")
    run = Run(id="run-quotes-1",
              input=RunInput(deck_path=str(tmp_path / "deck.pdf"), domain="swiftroute.in",
                             deck_date="2024-01-01", deck_date_source="input"),
              state=RunState.CREATED, created_at=now_iso(), updated_at=now_iso())
    store.insert_run(conn, run)
    yield RunContext(conn=conn, rules=load_rules(), run=run)
    conn.close()


def _fake_llm(answer: str, seen: list[str] | None = None) -> Any:
    def call(prompt: str, model: str | None = None, timeout_s: float = 30.0) -> tuple[str, str, int, int]:
        if seen is not None:
            seen.append(prompt)
        return answer, "fake-llm", 400, 30
    return call


def test_verbatim_quote_accepted_and_ledger_row_written(ctx: RunContext, monkeypatch: Any) -> None:
    answer = json.dumps({"quote": "India's logistics market was valued at ₹75,000 crore in 2023, "
                                  "according to analysts."})
    monkeypatch.setattr(quotes, "_default_llm_call", _fake_llm(answer))
    quote, call_id = pick_quote(ctx, PAGE, "How big is the market?", ["logistics"])
    assert quote is not None and quote.startswith("India's logistics market")
    rows = store.list_ledger(ctx.conn, ctx.run.id)
    assert len(rows) == 1
    assert rows[0].id == call_id
    assert rows[0].provider == Provider.LLM
    assert rows[0].endpoint_or_model == "fake-llm"
    assert (rows[0].tokens_in, rows[0].tokens_out, rows[0].ok) == (400, 30, True)


def test_whitespace_normalised_and_must_contain_case_insensitive(ctx: RunContext, monkeypatch: Any) -> None:
    answer = json.dumps({"quote": "SwiftRoute works with Acme Foods across five cities."})
    monkeypatch.setattr(quotes, "_default_llm_call", _fake_llm(answer))
    quote, _ = pick_quote(ctx, PAGE, "Is Acme Foods a customer?", ["acme foods", "SWIFTROUTE"])
    assert quote == "SwiftRoute works with Acme Foods across five cities."


def test_hallucinated_quote_rejected_but_ledger_row_kept(ctx: RunContext, monkeypatch: Any) -> None:
    answer = json.dumps({"quote": "India's logistics market was valued at ₹90,000 crore in 2023."})
    monkeypatch.setattr(quotes, "_default_llm_call", _fake_llm(answer))
    quote, call_id = pick_quote(ctx, PAGE, "How big is the market?", [])
    assert quote is None
    assert call_id is not None
    assert [r.id for r in store.list_ledger(ctx.conn, ctx.run.id)] == [call_id]


def test_verbatim_check_is_case_sensitive(ctx: RunContext, monkeypatch: Any) -> None:
    answer = json.dumps({"quote": "swiftroute works with acme foods across five cities."})
    monkeypatch.setattr(quotes, "_default_llm_call", _fake_llm(answer))
    assert pick_quote(ctx, PAGE, "customer?", [])[0] is None


def test_quote_missing_must_contain_rejected(ctx: RunContext, monkeypatch: Any) -> None:
    answer = json.dumps({"quote": "SwiftRoute works with Acme Foods across five cities."})
    monkeypatch.setattr(quotes, "_default_llm_call", _fake_llm(answer))
    quote, call_id = pick_quote(ctx, PAGE, "Is Acme Foods a customer?", ["Acme Foods", "Zomato"])
    assert quote is None
    assert call_id is not None


@pytest.mark.parametrize("answer", ['{"quote": null}', "not json at all", '{"other": 1}', '{"quote": "  "}'])
def test_no_usable_answer_gives_none(ctx: RunContext, monkeypatch: Any, answer: str) -> None:
    monkeypatch.setattr(quotes, "_default_llm_call", _fake_llm(answer))
    quote, call_id = pick_quote(ctx, PAGE, "q", [])
    assert quote is None
    assert store.list_ledger(ctx.conn, ctx.run.id)[0].ok is True
    assert call_id is not None


def test_fenced_json_answer_is_read(ctx: RunContext, monkeypatch: Any) -> None:
    answer = '```json\n{"quote": "Industry report 2023."}\n```'
    monkeypatch.setattr(quotes, "_default_llm_call", _fake_llm(answer))
    assert pick_quote(ctx, PAGE, "q", [])[0] == "Industry report 2023."


def test_page_text_cut_to_max_page_chars(ctx: RunContext, monkeypatch: Any) -> None:
    max_chars = int(rule(ctx.rules, "web.max_page_chars"))
    long_page = "A" * max_chars + "TAILMARKER"
    seen: list[str] = []
    monkeypatch.setattr(quotes, "_default_llm_call", _fake_llm('{"quote": null}', seen))
    pick_quote(ctx, long_page, "q", [])
    assert "A" * max_chars in seen[0]
    assert "TAILMARKER" not in seen[0]
    assert "json" in seen[0].lower()  # OpenAI json_object mode needs the word in the prompt


def test_failed_call_writes_ledger_row_and_reraises(ctx: RunContext, monkeypatch: Any) -> None:
    def boom(prompt: str, model: str | None = None, timeout_s: float = 30.0) -> tuple[str, str, int, int]:
        raise TimeoutError("LLM timed out")
    monkeypatch.setattr(quotes, "_default_llm_call", boom)
    with pytest.raises(TimeoutError):
        pick_quote(ctx, PAGE, "q", [])
    rows = store.list_ledger(ctx.conn, ctx.run.id)
    assert len(rows) == 1
    assert rows[0].ok is False
    assert "timed out" in (rows[0].error or "")


def test_empty_page_makes_no_call(ctx: RunContext, monkeypatch: Any) -> None:
    def never(*args: Any, **kwargs: Any) -> tuple[str, str, int, int]:
        raise AssertionError("must not call the LLM")
    monkeypatch.setattr(quotes, "_default_llm_call", never)
    assert pick_quote(ctx, "   ", "q", []) == (None, None)
    assert store.list_ledger(ctx.conn, ctx.run.id) == []


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        ("The market is worth $9 billion.", (9e9, "USD")),
        ("valued at USD 9.2 bn in 2023", (9.2e9, "USD")),
        ("a US$ 4.5 million round", (4.5e6, "USD")),
        ("9.2 billion USD by 2030", (9.2e9, "USD")),
        ("revenue of $120M", (1.2e8, "USD")),
        ("a $9B market", (9e9, "USD")),
        ("about $3.5 mn", (3.5e6, "USD")),
        ("₹75,000 crore market", (7.5e11, "INR")),
        ("Rs 75,000 crore market", (7.5e11, "INR")),
        ("Rs. 50 lakh seed", (5e6, "INR")),
        ("INR 1,00,000 crore", (1e12, "INR")),
        ("INR 1.5 lakh crore", (1.5e12, "INR")),
        ("₹2 billion", (2e9, "INR")),
        ("$9 billion in 2023, or $9 billion by most counts", (9e9, "USD")),
    ],
)
def test_parse_amount_reads_value_and_currency(quote: str, expected: tuple[float, str]) -> None:
    value, currency = parse_amount(quote)
    assert currency == expected[1]
    assert value == pytest.approx(expected[0])


@pytest.mark.parametrize(
    "quote",
    [
        "The market grew 12% in 2023.",                         # no amount
        "Over 9 billion parcels a year.",                       # number without a currency
        "From $5 billion in 2023 to $9 billion by 2030.",       # two different amounts
        "₹75,000 crore or $9 billion",                          # two currencies
        "A range of $5-7 billion.",                             # range
        "Rs 500 to 700 crore",                                  # range with 'to'
        "A$5 billion in Australia",                             # not USD
        "",
    ],
)
def test_parse_amount_no_single_clear_amount(quote: str) -> None:
    assert parse_amount(quote) == (None, None)
