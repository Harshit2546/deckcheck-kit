"""Exercise the Crustdata web search/fetch client with hand-built fixtures and its real SQLite ledger.
Called by pytest. Fixtures in tests/fixtures/web follow the response shapes in docs/WEB_SOURCE.md.
Patches only the HTTPS boundary (or `_send`) and the clock, so tests never spend credits.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from core import limits, log, store
from core.config import load_rules
from core.models import HeldReason, Run, RunContext, RunInput
from sources import web

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "web"
Reply = tuple[object, float | None] | Exception
MakeContext = Callable[[str], RunContext]
Calls = list[tuple[float, str, dict[str, Any], float]]
Serve = Callable[..., Calls]


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class _NoNetwork:
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("tests must not open a real HTTPS connection")


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Clock:
    clock = Clock()
    monkeypatch.setattr(log, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(web, "monotonic", clock.monotonic)
    monkeypatch.setattr(web, "sleep", clock.sleep)
    monkeypatch.setattr(web, "HTTPSConnection", _NoNetwork)
    monkeypatch.setattr(web, "_search_cache", {})
    monkeypatch.setattr(web, "_fetch_cache", {})
    monkeypatch.setenv("CRUSTDATA_API_KEY", "test-credential")
    return clock


@pytest.fixture
def make_context(tmp_path: Path) -> Iterator[MakeContext]:
    conn = store.connect(tmp_path / "web.db")

    def make(run_id: str) -> RunContext:
        run = Run(id=run_id, input=RunInput("deck.pdf", "example.com"))
        store.insert_run(conn, run)
        return RunContext(conn, load_rules(), run)

    try:
        yield make
    finally:
        conn.close()


def _recorded(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def serve(monkeypatch: pytest.MonkeyPatch, clock: Clock) -> Serve:
    def install(*replies: Reply) -> Calls:
        pending = iter(replies)
        calls: Calls = []

        def send(key: str, path: str, body: dict[str, Any],
                 deadline: float) -> tuple[object, float | None]:
            assert key == "test-credential"
            calls.append((clock.now, path, body, deadline))
            reply = next(pending)
            if isinstance(reply, Exception):
                raise reply
            return reply

        monkeypatch.setattr(web, "_send", send)
        return calls

    return install


class _FakeSocket:
    def settimeout(self, seconds: float) -> None:
        assert seconds > 0


class _FakeResponse:
    def __init__(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.status = status
        self._body = body
        self._headers = {name.lower(): value for name, value in headers.items()}

    def getheader(self, name: str) -> str | None:
        return self._headers.get(name.lower())

    def isclosed(self) -> bool:
        return not self._body

    def read1(self, size: int) -> bytes:
        chunk, self._body = self._body[:size], self._body[size:]
        return chunk


def _fake_connection(status: int, payload: object, headers: dict[str, str],
                     seen: list[dict[str, Any]]) -> type:
    class FakeConnection:
        def __init__(self, host: str, timeout: float) -> None:
            seen.append({"host": host, "timeout": timeout})
            self.sock: _FakeSocket | None = None

        def connect(self) -> None:
            self.sock = _FakeSocket()

        def request(self, method: str, path: str, body: str, headers_sent: dict[str, str]) -> None:
            seen[-1].update(method=method, path=path, body=json.loads(body), headers=headers_sent)

        def getresponse(self) -> _FakeResponse:
            return _FakeResponse(status, json.dumps(payload).encode(), headers)

        def close(self) -> None:
            seen[-1]["closed"] = True

    return FakeConnection


def test_search_request_body_headers_and_credit_header(
    make_context: MakeContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = make_context("search-http")
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(web, "HTTPSConnection", _fake_connection(
        200, _recorded("search_market_size.json"), {"X-Credits-Used": "2"}, seen))

    results, call_id = web.search(ctx, " India HR tech market size ", site="Example-News.in",
                                  end_date="2025-06-30")

    assert len(seen) == 1
    request = seen[0]
    assert request["host"] == "api.crustdata.com"
    assert request["method"] == "POST" and request["path"] == "/web/search/live"
    assert request["headers"]["authorization"] == "Bearer test-credential"
    assert request["headers"]["x-api-version"] == "2025-11-01"
    assert request["headers"]["content-type"] == "application/json"
    assert request["body"] == {"query": "India HR tech market size", "sources": ["news", "web"],
                               "location": "IN", "site": "example-news.in",
                               "end_date": 1751327999}
    assert request["closed"] is True
    assert [r["url"] for r in results] == ["https://example-news.in/hr-tech-market",
                                           "https://example-research.com/reports/hr-tech"]
    assert set(results[0]) == {"title", "url", "snippet", "position", "source"}
    row = store.list_ledger(ctx.conn, ctx.run.id)[0]
    assert row.id == call_id and row.ok
    assert row.endpoint_or_model == "POST /web/search/live"
    assert row.credits == 2.0
    assert row.cost_inr == 2 * ctx.rules["costs"]["crustdata"]["inr_per_credit"]


def test_search_options_override_rules_defaults(make_context: MakeContext, serve: Serve) -> None:
    calls = serve((_recorded("search_market_size.json"), None))
    web.search(make_context("opts"), "q", sources=["news"], location="US")
    assert calls[0][2] == {"query": "q", "sources": ["news"], "location": "US"}


def test_fetch_request_body_headers(make_context: MakeContext, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = make_context("fetch-http")
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(web, "HTTPSConnection", _fake_connection(
        200, _recorded("fetch_mixed.json"), {}, seen))
    urls = ["https://example-news.in/hr-tech-market", "https://example-research.com/reports/hr-tech",
            "https://blocked.example.net/page"]

    web.fetch(ctx, urls)

    assert seen[0]["path"] == "/web/enrich/live"
    assert seen[0]["headers"]["authorization"] == "Bearer test-credential"
    assert seen[0]["headers"]["x-api-version"] == "2025-11-01"
    assert seen[0]["body"] == {"urls": urls, "human_mode": False}
    row = store.list_ledger(ctx.conn, ctx.run.id)[0]
    assert row.endpoint_or_model == "POST /web/enrich/live"
    assert row.credits == 3.0  # no X-Credits-Used header: 1 per URL sent


@pytest.mark.parametrize(("day", "seconds"), [
    ("1970-01-01", 86399),
    ("2025-06-30", 1751327999),
    ("2024-02-29", 1709251199),
])
def test_end_date_is_end_of_day_utc(day: str, seconds: int) -> None:
    assert web.end_of_day_unix(day) == seconds


def test_bad_end_date_raises_before_any_call(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("bad-date")
    calls = serve()
    with pytest.raises(ValueError):
        web.search(ctx, "q", end_date="30/06/2025")
    assert calls == [] and store.list_ledger(ctx.conn, ctx.run.id) == []


def test_fetch_keeps_successes_matched_by_url_in_request_order(
    make_context: MakeContext, serve: Serve, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve((_recorded("fetch_mixed.json"), None))
    urls = ["https://example-news.in/hr-tech-market", "https://blocked.example.net/page",
            "https://example-research.com/reports/hr-tech"]

    pages, call_id = web.fetch(make_context("mixed"), urls)

    assert call_id is not None
    assert [page["url"] for page in pages] == [urls[0], urls[2]]  # failed + unrequested dropped
    assert set(pages[0]) == {"url", "title", "html", "fetched_at"}
    assert pages[0]["fetched_at"] == "2025-11-22T06:21:02+00:00"
    assert "USD 9.2 bn" in pages[1]["html"]


def test_fetch_skips_non_https_urls_and_keeps_the_rest(make_context: MakeContext,
                                                     serve: Serve) -> None:
    ctx = make_context("mixed-scheme")
    calls = serve((_recorded("fetch_mixed.json"), None))
    pages, _ = web.fetch(ctx, ["http://plain.example.com/a", "https://example-news.in/hr-tech-market"])
    assert calls[0][2]["urls"] == ["https://example-news.in/hr-tech-market"]
    assert [page["url"] for page in pages] == ["https://example-news.in/hr-tech-market"]
    assert store.list_ledger(ctx.conn, ctx.run.id)[0].credits == 1.0


def test_ledger_row_on_http_error_without_retry(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("http-500")
    calls = serve(web._HttpError(500, None, None))
    with pytest.raises(web._HttpError):
        web.search(ctx, "q")
    assert len(calls) == 1  # 5xx is not retried
    rows = store.list_ledger(ctx.conn, ctx.run.id)
    assert len(rows) == 1
    assert not rows[0].ok and rows[0].error == "http_500" and rows[0].credits == 0.0


def test_malformed_response_raises_and_is_ledgered(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("malformed")
    serve(({"success": False, "results": []}, None), ({"not": "a list"}, None))
    with pytest.raises(RuntimeError):
        web.search(ctx, "q")
    with pytest.raises(RuntimeError):
        web.fetch(ctx, ["https://example.com/a"])
    rows = store.list_ledger(ctx.conn, ctx.run.id)
    assert [(r.ok, r.error, r.credits) for r in rows] == [(False, "ValueError", 1.0),
                                                          (False, "ValueError", 1.0)]


def test_429_retries_once_after_retry_after(make_context: MakeContext, serve: Serve,
                                            clock: Clock) -> None:
    ctx = make_context("rate")
    calls = serve(web._HttpError(429, "3", None), (_recorded("search_market_size.json"), None))

    _, call_id = web.search(ctx, "q")

    assert len(calls) == 2 and calls[1][0] - calls[0][0] == 3
    rows = store.list_ledger(ctx.conn, ctx.run.id)
    assert len(rows) == 2
    assert {(r.ok, r.error) for r in rows} == {(False, "http_429"), (True, None)}
    assert next(r for r in rows if r.ok).id == call_id


def test_second_429_raises(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("rate-twice")
    serve(web._HttpError(429, "0", None), web._HttpError(429, "0", None))
    with pytest.raises(web._HttpError):
        web.fetch(ctx, ["https://example.com/a"])
    assert len(store.list_ledger(ctx.conn, ctx.run.id)) == 2


def test_timeout_raises_and_is_ledgered(make_context: MakeContext, serve: Serve,
                                        monkeypatch: pytest.MonkeyPatch, clock: Clock) -> None:
    ctx = make_context("timeout")
    calls = serve((_recorded("search_market_size.json"), None))

    def slow_send(key: str, path: str, body: dict[str, Any],
                  deadline: float) -> tuple[object, float | None]:
        calls.append((clock.now, path, body, deadline))
        clock.now = deadline + 1
        return {"success": True, "results": []}, None

    monkeypatch.setattr(web, "_send", slow_send)
    with pytest.raises(TimeoutError):
        web.search(ctx, "q")
    assert calls[0][3] - calls[0][0] == ctx.rules["limits"]["per_call_timeout_s"]
    rows = store.list_ledger(ctx.conn, ctx.run.id)
    assert len(rows) == 1 and rows[0].error == "timeout" and not rows[0].ok


def test_send_raises_timeout_when_deadline_passed(clock: Clock) -> None:
    with pytest.raises(TimeoutError):
        web._send("k", web.SEARCH_PATH, {"query": "q"}, clock.now)


def test_cache_is_per_run_and_returns_copies(make_context: MakeContext, serve: Serve) -> None:
    first, second = make_context("one"), make_context("two")
    fetched = _recorded("fetch_mixed.json")
    calls = serve((_recorded("search_market_size.json"), None), (fetched, None),
                  (_recorded("search_market_size.json"), None))
    urls = ["https://example-news.in/hr-tech-market", "https://example-research.com/reports/hr-tech"]

    results, search_id = web.search(first, "q", end_date="2025-06-30")
    results[0]["url"] = "mutated"
    pages, fetch_id = web.fetch(first, urls)
    again, again_id = web.search(first, "q", end_date="2025-06-30")
    reversed_pages, reversed_id = web.fetch(first, list(reversed(urls)))

    assert again_id == search_id and again[0]["url"] == "https://example-news.in/hr-tech-market"
    assert reversed_id == fetch_id
    assert [p["url"] for p in reversed_pages] == list(reversed(urls))
    assert len(calls) == 2 and len(store.list_ledger(first.conn, first.run.id)) == 2

    _, other_id = web.search(second, "q", end_date="2025-06-30")
    assert other_id != search_id and len(calls) == 3


def test_fetch_url_cap_and_empty_input(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("cap")
    calls = serve()
    with pytest.raises(ValueError):
        web.fetch(ctx, [f"https://example.com/{n}" for n in range(11)])
    assert web.fetch(ctx, ["http://example.com/insecure"]) == ([], None)
    assert web.fetch(ctx, []) == ([], None)
    assert calls == [] and store.list_ledger(ctx.conn, ctx.run.id) == []


def test_limit_hit_blocks_the_call(make_context: MakeContext, serve: Serve,
                                   monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = make_context("limit")
    calls = serve()

    def over(_: RunContext) -> None:
        raise limits.LimitExceeded(HeldReason.BUDGET, "test")

    monkeypatch.setattr(limits, "ensure_within", over)
    with pytest.raises(limits.LimitExceeded):
        web.fetch(ctx, ["https://example.com/a"])
    assert calls == [] and store.list_ledger(ctx.conn, ctx.run.id) == []


def test_fetch_uses_web_fetch_timeout(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("fetch-timeout")
    ctx.rules["web"]["fetch_timeout_s"] = 45
    calls = serve((_recorded("fetch_mixed.json"), None))
    web.fetch(ctx, ["https://example-news.in/hr-tech-market"])
    assert calls[0][3] - calls[0][0] == 45


def test_fetch_timeout_falls_back_to_per_call_limit(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("fetch-fallback")
    ctx.rules["web"].pop("fetch_timeout_s", None)
    calls = serve((_recorded("fetch_mixed.json"), None))
    web.fetch(ctx, ["https://example-news.in/hr-tech-market"])
    assert calls[0][3] - calls[0][0] == ctx.rules["limits"]["per_call_timeout_s"]


def test_search_keeps_per_call_timeout(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("search-timeout")
    ctx.rules["web"]["fetch_timeout_s"] = 45
    calls = serve((_recorded("search_market_size.json"), None))
    web.search(ctx, "q")
    assert calls[0][3] - calls[0][0] == ctx.rules["limits"]["per_call_timeout_s"] != 45


def test_slow_fetch_still_times_out_and_is_ledgered(make_context: MakeContext, serve: Serve,
                                                    monkeypatch: pytest.MonkeyPatch,
                                                    clock: Clock) -> None:
    ctx = make_context("fetch-slow")
    ctx.rules["web"]["fetch_timeout_s"] = 45

    def slow_send(key: str, path: str, body: dict[str, Any],
                  deadline: float) -> tuple[object, float | None]:
        clock.now = deadline + 1
        return [], None

    monkeypatch.setattr(web, "_send", slow_send)
    with pytest.raises(TimeoutError):
        web.fetch(ctx, ["https://example-news.in/hr-tech-market"])
    rows = store.list_ledger(ctx.conn, ctx.run.id)
    assert len(rows) == 1 and rows[0].error == "timeout" and rows[0].endpoint_or_model == "POST /web/enrich/live"
