"""Tests for checkers/customer.py with sources.web, sources.pages and extract.quotes faked.

Called by: pytest. Calls: checkers/customer.py, checker_fakes.make_ctx.
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
from checkers import customer  # noqa: E402
from core.models import Claim, ClaimType, SourceType  # noqa: E402

RULES = {"web": {"results_to_fetch": 3}}


def _claim(value: Any = "Acme Freight Corp") -> Claim:
    return Claim(id="c_cust", run_id="run_1", slide=6, quote="Trusted by Acme Freight Corp for all deliveries.",
                 type=ClaimType.CUSTOMER, subject="Locus", metric="customer", value=value)


def _ctx(identity: str = "confirmed", signals: int = 2) -> Any:
    ctx = make_ctx(run_id="run_cu", company_domain="www.Locus.sh", deck_date="2024-06-01",
                   identity=identity, identity_signals=signals)
    ctx.rules = RULES
    return ctx


def _install(monkeypatch: pytest.MonkeyPatch, pages_by_url: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Fake web/pages/quotes. pages_by_url: url -> {"date", "quote"}."""
    calls: dict[str, Any] = {}

    def search(ctx: Any, query: str, *, end_date: str | None = None, **kw: Any) -> Any:
        calls["search"] = {"query": query, "end_date": end_date}
        return [{"url": u, "title": u, "snippet": "", "position": i, "source": "news"}
                for i, u in enumerate(pages_by_url)], "call-search"

    def fetch(ctx: Any, urls: list[str]) -> Any:
        calls["fetch"] = list(urls)
        return [{"url": u, "title": u, "html": u, "fetched_at": "2026-11-22T10:00:00Z"} for u in urls], "call-fetch"

    def published_date(html: str) -> Any:
        date = pages_by_url[html]["date"]
        return (date, "jsonld:datePublished") if date else (None, None)

    def pick_quote(ctx: Any, text: str, question: str, must_contain: list[str]) -> Any:
        calls.setdefault("must_contain", []).append(must_contain)
        return pages_by_url[text].get("quote"), "call-llm"

    monkeypatch.setattr(customer, "web", types.SimpleNamespace(search=search, fetch=fetch))
    monkeypatch.setattr(customer, "pages", types.SimpleNamespace(
        page_text=lambda html: html, published_date=published_date))
    monkeypatch.setattr(customer, "quotes", types.SimpleNamespace(pick_quote=pick_quote))
    return calls


QUOTE = "Acme Freight Corp runs all deliveries on Locus."


def test_mentions_evidence_independence_and_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, {
        "https://www.locus.sh/case-studies/acme": {"date": "2024-02-01", "quote": QUOTE},
        "https://blog.locus.sh/acme": {"date": "2024-03-01", "quote": QUOTE},
        "https://news.notlocus.sh/acme": {"date": "2024-04-01", "quote": QUOTE},
    })
    res = customer.check(_claim(), _ctx())

    assert calls["search"] == {"query": '"Acme Freight Corp" "Locus"', "end_date": "2024-06-01"}
    assert calls["must_contain"][0] == ["Acme Freight Corp", "Locus"]
    obs = res.observed
    assert obs["identity"] == "confirmed" and obs["identity_signals"] == 2
    assert obs["customer_name"] == "Acme Freight Corp"
    assert obs["record_date"] == "2024-04-01"
    assert [(m["domain"], m["independent"]) for m in obs["mentions"]] == [
        ("locus.sh", False), ("blog.locus.sh", False), ("news.notlocus.sh", True)]
    assert set(obs) == {"identity", "identity_signals", "record_date", "reference_date",
                        "reference_date_source", "customer_name", "mentions"}
    m0 = obs["mentions"][0]
    assert set(m0) == {"url", "domain", "quote", "published_date", "independent", "evidence_id"}
    ev = res.evidence[0]
    assert ev.id == m0["evidence_id"]
    assert ev.source_type == SourceType.WEB_PAGE
    assert ev.locator == "https://www.locus.sh/case-studies/acme"
    assert ev.field_or_quote == QUOTE
    assert ev.value == "Acme Freight Corp"
    assert ev.record_date == "2024-02-01"
    assert ev.call_id == "call-fetch"


def test_undated_and_late_pages_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {
        "https://press.example.com/a": {"date": None, "quote": QUOTE},
        "https://press.example.com/b": {"date": "2024-06-02", "quote": QUOTE},
    })
    res = customer.check(_claim(), _ctx())
    assert res.evidence == [] and res.observed["mentions"] == []
    assert res.observed["record_date"] is None


def test_unverified_quote_gives_no_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {"https://press.example.com/a": {"date": "2024-01-01", "quote": None}})
    res = customer.check(_claim(), _ctx())
    assert res.evidence == []


def test_identity_comes_from_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {})
    res = customer.check(_claim(), _ctx(identity="unclear", signals=1))
    assert res.observed["identity"] == "unclear" and res.observed["identity_signals"] == 1
    assert res.evidence == []


def test_no_customer_name_makes_no_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, {})
    res = customer.check(_claim(value=None), _ctx())
    assert calls == {} and res.evidence == []


@pytest.mark.parametrize("which", ["search", "fetch"])
def test_source_errors_propagate(monkeypatch: pytest.MonkeyPatch, which: str) -> None:
    _install(monkeypatch, {"https://press.example.com/a": {"date": "2024-01-01", "quote": QUOTE}})

    def boom(*a: Any, **kw: Any) -> Any:
        raise RuntimeError("crustdata 500")

    monkeypatch.setattr(customer.web, which, boom)
    with pytest.raises(RuntimeError):
        customer.check(_claim(), _ctx())
