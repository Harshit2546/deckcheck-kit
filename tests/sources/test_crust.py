"""Exercise the company source with recorded responses and its real SQLite ledger.
Called by pytest. Uses Crustdata's published company example and the T02 account record.
Patches only the HTTPS boundary and the clock, so tests never spend credits.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from http.client import HTTPResponse
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from checkers._common import get_company
from core import limits, store
from core.config import load_rules
from core.models import HeldReason, Run, RunContext, RunInput
from sources import crust

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "crustdata"
Reply = tuple[object, float | None] | Exception
MakeContext = Callable[[str], RunContext]
Serve = Callable[..., list[tuple[float, str, dict[str, Any] | None, float]]]


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(crust, "monotonic", clock.monotonic)
    monkeypatch.setattr(crust, "sleep", clock.sleep)
    monkeypatch.setattr(crust, "_company_cache", {})
    monkeypatch.setattr(crust, "_account_cache", {})
    monkeypatch.setattr(crust, "_next_company_call", {})
    monkeypatch.setenv("CRUSTDATA_API_KEY", "test-credential")
    return clock


@pytest.fixture
def make_context(tmp_path: Path) -> Iterator[MakeContext]:
    conn = store.connect(tmp_path / "sources.db")

    def make(run_id: str) -> RunContext:
        run = Run(id=run_id, input=RunInput("deck.pdf", "retool.com"))
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
    def install(*company_replies: Reply) -> list[tuple[float, str, dict[str, Any] | None, float]]:
        replies = iter(company_replies)
        calls = []

        def send(key: str, path: str, body: dict[str, Any] | None,
                 deadline: float) -> tuple[object, float | None]:
            assert key == "test-credential"
            calls.append((clock.now, path, body, deadline))
            if body is None:
                assert path.startswith("/account/endpoints?")
                return _recorded("account_company_rates.json"), None
            reply = next(replies)
            if isinstance(reply, Exception):
                raise reply
            return reply

        monkeypatch.setattr(crust, "_send", send)
        return calls

    return install


def test_return_contract_cache_provenance_and_credit_estimate(
    make_context: MakeContext, serve: Serve, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = make_context("cache")
    calls = serve((_recorded("company_enrich_documented.json"), None))
    monkeypatch.setattr(crust, "now_iso", lambda: "2026-11-22T06:40:00+00:00")

    company, call_id = get_company(ctx, " Retool.com. ")
    assert company["basic_info"]["primary_domain"] == "retool.com"
    assert company["headcount"]["total"] == 416
    assert company["funding"]["last_fundraise_date"] == "2022-07-27"
    assert company["retrieved_at"] == "2026-11-22T06:40:00+00:00"
    assert calls[1][2]["domains"] == ["retool.com"]
    assert calls[1][2]["exact_match"] is True
    assert {"headcount", "funding", "competitors"} <= set(calls[1][2]["fields"])
    assert calls[1][3] - calls[1][0] == ctx.rules["limits"]["per_call_timeout_s"]
    company["headcount"]["total"] = -1

    clock.sleep(10)
    monkeypatch.setattr(crust, "now_iso", lambda: "2026-11-22T06:40:10+00:00")
    cached, cached_call_id = get_company(ctx, "retool.com")
    assert cached["headcount"]["total"] == 416
    assert cached["retrieved_at"] == "2026-11-22T06:40:00+00:00"
    assert cached_call_id == call_id
    assert len(calls) == 2

    rows = store.list_ledger(ctx.conn, ctx.run.id)
    assert len(rows) == 2
    assert {row.endpoint_or_model for row in rows} == {"GET /account/endpoints", "POST /company/enrich"}
    row = next(row for row in rows if row.id == call_id)
    assert row.credits == 2.0
    assert row.cost_inr == 2 * ctx.rules["costs"]["crustdata"]["inr_per_credit"]


def test_cache_is_run_scoped_and_expires(make_context: MakeContext, serve: Serve, clock: Clock) -> None:
    first = make_context("first")
    second = make_context("second")
    payload = _recorded("company_enrich_documented.json")
    calls = serve((payload, 1.5), (payload, None), (payload, None))

    _, first_id = crust.get_company(first, "retool.com")
    _, second_id = crust.get_company(second, "retool.com")
    assert first_id != second_id
    assert calls[2][0] - calls[1][0] == 12
    first_row = next(row for row in store.list_ledger(first.conn, first.run.id) if row.id == first_id)
    assert first_row.credits == 1.5

    clock.sleep(61)
    _, refreshed_id = crust.get_company(first, "retool.com")
    assert refreshed_id not in {first_id, second_id}
    assert len(calls) == 5


@pytest.mark.parametrize(("status", "retry_after", "wait"), [(429, "17", 17), (503, None, 12)])
def test_retry_is_paced_and_each_attempt_is_reported(
    make_context: MakeContext, serve: Serve, status: int, retry_after: str | None, wait: int
) -> None:
    ctx = make_context("retry")
    calls = serve(crust._HttpError(status, retry_after, None),
                  (_recorded("company_enrich_documented.json"), None))

    _, call_id = crust.get_company(ctx, "retool.com")

    assert calls[2][0] - calls[1][0] == wait
    rows = store.list_ledger(ctx.conn, ctx.run.id)
    assert len(rows) == 3
    assert sum(row.ok for row in rows) == 2
    assert [row.error for row in rows if not row.ok] == [f"http_{status}"]
    assert next(row for row in rows if row.id == call_id).ok


def test_timeout_raises_and_records_one_failed_attempt(
    make_context: MakeContext, serve: Serve
) -> None:
    ctx = make_context("timeout")
    calls = serve(TimeoutError("test-credential"))

    with pytest.raises(TimeoutError, match="Crustdata per-call timeout") as caught:
        crust.get_company(ctx, "retool.com")

    assert "test-credential" not in str(caught.value)
    assert len(calls) == 2
    row = next(row for row in store.list_ledger(ctx.conn, ctx.run.id) if row.endpoint_or_model == "POST /company/enrich")
    assert row.error == "timeout"
    assert not row.ok


def test_late_response_is_also_a_timeout(
    make_context: MakeContext, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = make_context("late")
    ctx.rules["limits"]["per_call_timeout_s"] = 0.5

    def send(key: str, path: str, body: dict[str, Any] | None, deadline: float) -> tuple[object, None]:
        if body is None:
            return _recorded("account_company_rates.json"), None
        clock.now = deadline + 0.01
        return _recorded("company_enrich_documented.json"), None

    monkeypatch.setattr(crust, "_send", send)
    with pytest.raises(TimeoutError):
        crust.get_company(ctx, "retool.com")
    row = next(row for row in store.list_ledger(ctx.conn, ctx.run.id) if row.endpoint_or_model == "POST /company/enrich")
    assert row.error == "timeout"
    assert row.duration_ms > 500


def test_limit_before_account_request(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("budget")
    ctx.rules["limits"]["max_credits"] = 0
    calls = serve()

    with pytest.raises(limits.LimitExceeded) as caught:
        crust.get_company(ctx, "retool.com")

    assert caught.value.reason is HeldReason.BUDGET
    assert not calls
    assert not store.list_ledger(ctx.conn, ctx.run.id)


def test_retry_rechecks_ledger_and_run_budget(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("retry-budget")
    ctx.rules["limits"]["max_credits"] = 2
    calls = serve(crust._HttpError(503, None, 2.0))

    with pytest.raises(limits.LimitExceeded) as caught:
        crust.get_company(ctx, "retool.com")

    assert caught.value.reason is HeldReason.BUDGET
    assert len(calls) == 2
    rows = store.list_ledger(ctx.conn, ctx.run.id)
    assert [row.error for row in rows if not row.ok] == ["http_503"]


def test_empty_match_is_a_valid_lookup_without_record_credits(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("empty")
    response = _recorded("company_enrich_documented.json")
    response[0]["matches"].clear()
    calls = serve((response, None))

    result, call_id = crust.get_company(ctx, "retool.com")
    assert result == {}
    assert len(calls) == 2
    row = next(row for row in store.list_ledger(ctx.conn, ctx.run.id) if row.endpoint_or_model == "POST /company/enrich")
    assert (row.id, row.ok, row.credits) == (call_id, True, 0.0)


def test_permission_and_bad_response_are_errors(make_context: MakeContext, serve: Serve) -> None:
    denied = make_context("denied")
    calls = serve(crust._HttpError(403, None, None), ({"unexpected": True}, None))

    with pytest.raises(RuntimeError, match="HTTP 403"):
        crust.get_company(denied, "retool.com")
    assert len(calls) == 2

    invalid = make_context("invalid")
    with pytest.raises(RuntimeError, match="ValueError"):
        crust.get_company(invalid, "retool.com")
    row = store.list_ledger(invalid.conn, invalid.run.id)[-1]
    assert row.error == "ValueError"
    assert not row.ok


def test_https_transport_sends_versioned_json_and_retains_receipt(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = (FIXTURES / "company_enrich_documented.json").read_bytes()
    headers = (f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\n"
               "Connection: close\r\nX-Credits-Charged: 2\r\n\r\n").encode()
    connection = Mock()
    connection.sock.makefile.return_value = BytesIO(headers + body)
    response = HTTPResponse(connection.sock)
    response.begin()
    connection.getresponse.return_value = response
    factory = Mock(return_value=connection)
    monkeypatch.setattr(crust, "HTTPSConnection", factory)

    payload, credits = crust._send("test-credential", "/company/enrich",
                                   {"domains": ["retool.com"]}, clock.now + 4)

    assert payload == _recorded("company_enrich_documented.json")
    assert credits == 2
    factory.assert_called_once_with("api.crustdata.com", timeout=4)
    method, path, request_body, request_headers = connection.request.call_args.args
    assert (method, path) == ("POST", "/company/enrich")
    assert json.loads(request_body) == {"domains": ["retool.com"]}
    assert request_headers["x-api-version"] == "2025-11-01"
    assert request_headers["Authorization"] == "Bearer test-credential"
    connection.close.assert_called_once()


def test_retry_wait_cannot_exhaust_the_run_time(make_context: MakeContext, serve: Serve) -> None:
    ctx = make_context("retry-time")
    ctx.rules["limits"]["max_seconds"] = 5
    calls = serve(crust._HttpError(429, "30", None))

    with pytest.raises(limits.LimitExceeded) as caught:
        crust.get_company(ctx, "retool.com")

    assert caught.value.reason is HeldReason.TIME
    assert len(calls) == 2
    assert [row.error for row in store.list_ledger(ctx.conn, ctx.run.id) if not row.ok] == ["http_429"]
