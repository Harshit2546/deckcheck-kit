"""Tests for checkers/market_size.py with sources.web, sources.pages and extract.quotes faked.

Called by: pytest. Calls: checkers/market_size.py, checker_fakes.make_ctx.
The three modules are faked on the checker module (tests only), so these tests do not need
T30/T31 to be merged. Until they are, bare stand-ins are registered so the import works.
"""

from __future__ import annotations

import importlib
import sys
import types
from typing import Any

import pytest

for _name in ("sources.web", "sources.pages", "extract.quotes"):
    try:
        importlib.import_module(_name)
    except ModuleNotFoundError:
        sys.modules[_name] = types.ModuleType(_name)

from checker_fakes import make_ctx  # noqa: E402
from checkers import market_size  # noqa: E402
from core.models import Claim, ClaimType, SourceType  # noqa: E402

RULES = {"web": {"results_to_fetch": 3}}


def _claim(as_of: str | None = None, subject: str | None = "India logistics software") -> Claim:
    return Claim(id="c_market", run_id="run_1", slide=7,
                 quote="India's logistics software market is worth $9B.", type=ClaimType.MARKET_SIZE,
                 subject=subject, metric="market_size", value=9_000_000_000,
                 unit="USD", as_of=as_of)


def _install(monkeypatch: pytest.MonkeyPatch, pages_by_url: dict[str, dict[str, Any]],
             results: list[str] | None = None, calls: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fake web/pages/quotes. pages_by_url: url -> {"date", "quote", "amount"}."""
    calls = calls if calls is not None else {}
    urls = results if results is not None else list(pages_by_url)

    def search(ctx: Any, query: str, *, end_date: str | None = None, **kw: Any) -> Any:
        calls["search"] = {"query": query, "end_date": end_date}
        return [{"url": u, "title": u, "snippet": "", "position": i, "source": "web"}
                for i, u in enumerate(urls)], "call-search"

    def fetch(ctx: Any, fetch_urls: list[str]) -> Any:
        calls["fetch"] = list(fetch_urls)
        return [{"url": u, "title": u, "html": u, "fetched_at": "2026-11-22T10:00:00Z"}
                for u in fetch_urls if u in pages_by_url], "call-fetch"

    def published_date(html: str) -> Any:
        date = pages_by_url[html]["date"]
        return (date, "meta[property=article:published_time]") if date else (None, None)

    def pick_quote(ctx: Any, text: str, question: str, must_contain: list[str]) -> Any:
        return pages_by_url[text].get("quote"), "call-llm"

    def parse_amount(quote: str) -> Any:
        for spec in pages_by_url.values():
            if spec.get("quote") == quote:
                return spec.get("amount", (None, None))
        return None, None

    monkeypatch.setattr(market_size, "web", types.SimpleNamespace(search=search, fetch=fetch))
    monkeypatch.setattr(market_size, "pages", types.SimpleNamespace(
        page_text=lambda html: html, published_date=published_date))
    monkeypatch.setattr(market_size, "quotes", types.SimpleNamespace(
        pick_quote=pick_quote, parse_amount=parse_amount))
    return calls


def _ctx() -> Any:
    ctx = make_ctx(run_id="run_ms", company_domain="locus.sh", deck_date="2024-06-01")
    ctx.rules = RULES
    return ctx


def test_estimates_evidence_and_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, {
        "https://www.reports.example.com/a": {"date": "2024-01-10", "quote": "India's logistics software market is valued at $9 billion.",
                                              "amount": (9e9, "USD")},
        "https://news.example.org/b": {"date": None, "quote": "undated"},
        "https://late.example.net/c": {"date": "2025-02-01", "quote": "after"},
    })
    res = market_size.check(_claim(), _ctx())

    assert calls["search"] == {"query": "India logistics software market size", "end_date": "2024-06-01"}
    obs = res.observed
    assert obs["identity"] == "not_applicable" and obs["identity_signals"] == 0
    assert obs["pages_without_date"] == 1
    assert obs["pages_after_reference"] == 1
    assert obs["reference_date"] == "2024-06-01"
    assert obs["record_date"] == "2024-01-10"
    assert len(res.evidence) == 1
    ev = res.evidence[0]
    assert ev.source_type == SourceType.WEB_PAGE
    assert ev.locator == "https://www.reports.example.com/a"
    assert ev.field_or_quote == "India's logistics software market is valued at $9 billion."
    assert ev.value == 9e9
    assert ev.record_date == "2024-01-10"
    assert ev.call_id == "call-fetch"
    assert ev.retrieved_at == "2026-11-22T10:00:00Z"
    assert obs["estimates"] == [{
        "value": 9e9, "currency": "USD", "url": "https://www.reports.example.com/a",
        "domain": "reports.example.com", "quote": "India's logistics software market is valued at $9 billion.",
        "published_date": "2024-01-10", "evidence_id": ev.id,
    }]


def test_as_of_is_the_reference_date(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, {
        "https://a.example.com/x": {"date": "2024-01-10", "quote": "Logistics software spend is $1.", "amount": (1.0, "USD")},
    })
    res = market_size.check(_claim(as_of="2023-12-31"), _ctx())
    assert calls["search"]["end_date"] == "2023-12-31"
    assert res.observed["pages_after_reference"] == 1
    assert res.evidence == []


def test_quote_without_amount_or_unverified_gives_no_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {
        "https://a.example.com/x": {"date": "2024-01-10", "quote": "Logistics software is growing.", "amount": (None, None)},
        "https://b.example.com/y": {"date": "2024-01-10", "quote": None},
    })
    res = market_size.check(_claim(), _ctx())
    assert res.evidence == [] and res.observed["estimates"] == []
    assert res.observed["record_date"] is None


def test_only_top_n_distinct_urls_fetched(monkeypatch: pytest.MonkeyPatch) -> None:
    urls = [f"https://s{i}.example.com/" for i in range(5)]
    calls = _install(monkeypatch, {u: {"date": None} for u in urls}, results=[urls[0], urls[0], *urls[1:]])
    market_size.check(_claim(), _ctx())
    assert calls["fetch"] == urls[:3]


def test_no_results_skips_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, {})
    res = market_size.check(_claim(), _ctx())
    assert "fetch" not in calls
    assert res.evidence == [] and res.observed["estimates"] == []


def test_all_pages_undated_gives_no_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {"https://a.example.com/": {"date": None}, "https://b.example.com/": {"date": None}})
    res = market_size.check(_claim(), _ctx())
    assert res.evidence == []
    assert res.observed["pages_without_date"] == 2


@pytest.mark.parametrize("which", ["search", "fetch"])
def test_source_errors_propagate(monkeypatch: pytest.MonkeyPatch, which: str) -> None:
    _install(monkeypatch, {"https://a.example.com/": {"date": "2024-01-01"}})

    def boom(*a: Any, **kw: Any) -> Any:
        raise TimeoutError("per_call_timeout_s")

    monkeypatch.setattr(market_size.web, which, boom)
    with pytest.raises(TimeoutError):
        market_size.check(_claim(), _ctx())


HOUSEHOLD = ("India's home and household market is projected to reach USD 237 billion by 2030, "
             "growing at over 10% annually.")


def test_quote_about_another_market_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """INCIDENTS B10: the live run took this household-market quote for logistics software."""
    calls: dict[str, Any] = {}
    _install(monkeypatch, {"https://m.economictimes.com/x": {
        "date": "2024-09-18", "quote": HOUSEHOLD, "amount": (237e9, "USD")}}, calls=calls)
    ctx = make_ctx(run_id="run_ms", company_domain="locus.sh", deck_date="2024-12-01")
    ctx.rules = RULES
    res = market_size.check(_claim(), ctx)
    assert res.evidence == [] and res.observed["estimates"] == []


def test_required_terms_passed_to_pick_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    _install(monkeypatch, {"https://a.example.com/x": {
        "date": "2024-01-10", "quote": "India's logistics software market is valued at $9 billion.",
        "amount": (9e9, "USD")}})
    real = market_size.quotes.pick_quote
    monkeypatch.setattr(market_size.quotes, "pick_quote",
                        lambda ctx, text, q, must: (seen.append(must), real(ctx, text, q, must))[1])
    res = market_size.check(_claim(), _ctx())
    assert seen == [["logistics", "software"]]
    assert len(res.evidence) == 1 and res.evidence[0].value == 9e9


def test_forecast_quote_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {
        "https://a.example.com/x": {"date": "2024-01-10", "amount": (20e9, "USD"),
                                    "quote": "India's logistics software market will be $20 billion by 2030."},
        "https://b.example.com/y": {"date": "2024-01-10", "amount": (15e9, "USD"),
                                    "quote": "Logistics software revenue: $15 billion (2028E)."},
        "https://c.example.com/z": {"date": "2024-01-10", "amount": (8e9, "USD"),
                                    "quote": "India's logistics software market was $8 billion in 2023."},
    })
    res = market_size.check(_claim(), _ctx())
    assert res.observed["forecast_quotes_skipped"] == 2
    assert [e["value"] for e in res.observed["estimates"]] == [8e9]


@pytest.mark.parametrize("quote", [
    "The market is projected to reach $20 billion in 2027.",
    "Market expected to reach $20 billion over the next years, by 2029.",
])
def test_forecast_detection(quote: str) -> None:
    assert market_size._is_forecast(quote, 2024)


def test_past_year_is_not_a_forecast() -> None:
    assert not market_size._is_forecast("The market was $8 billion in 2023.", 2024)
    assert not market_size._is_forecast("It is expected to stay flat, as in 2024.", 2024)


def test_empty_subject_has_no_required_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    _install(monkeypatch, {"https://a.example.com/x": {
        "date": "2024-01-10", "quote": "The market is worth $9 billion.", "amount": (9e9, "USD")}})
    real = market_size.quotes.pick_quote
    monkeypatch.setattr(market_size.quotes, "pick_quote",
                        lambda ctx, text, q, must: (seen.append(must), real(ctx, text, q, must))[1])
    res = market_size.check(_claim(subject=""), _ctx())
    assert seen == [[]]
    assert len(res.evidence) == 1


def test_stop_words_only_subject_has_no_terms() -> None:
    assert market_size._required_terms("Global market size of the industry") == []
    assert market_size._required_terms("India Logistics software market") == ["logistics", "software"]
