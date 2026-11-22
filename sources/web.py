"""Search the web and fetch pages through Crustdata's Web APIs (D16, docs/WEB_SOURCE.md).
Called by the market_size and customer checkers; search() finds pages, fetch() gets their HTML.
Uses core limits and ledger (one row per HTTP call), rules.yaml `web.*`, and the key loader
from sources/crust.py. Retries once on HTTP 429 only; any other error or timeout is raised.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
from http.client import HTTPException, HTTPSConnection
from threading import Lock
from time import monotonic, sleep
from typing import Any

from core import ledger, limits
from core.config import rule
from core.log import log_step
from core.models import HeldReason, Provider, RunContext, now_iso
from sources.crust import _api_key, _nonnegative_number, _retry_delay

_HOST = "api.crustdata.com"
_VERSION = "2025-11-01"
SEARCH_PATH = "/web/search/live"
FETCH_PATH = "/web/enrich/live"
MAX_FETCH_URLS = 10
MAX_QUERY_CHARS = 5000
_CREDIT_HEADER = "x-credits-used"
_DAY_SECONDS = 86400

_lock = Lock()
_search_cache: dict[tuple[str, str, str, str], tuple[list[dict[str, Any]], str]] = {}
_fetch_cache: dict[tuple[str, str, str, tuple[str, ...]], tuple[list[dict[str, Any]], str]] = {}


class _HttpError(RuntimeError):
    def __init__(self, status: int, retry_after: str | None, credits: float | None) -> None:
        super().__init__(f"Crustdata web HTTP {status}")
        self.status = status
        self.retry_after = retry_after
        self.credits = credits


def _remaining(deadline: float) -> float:
    seconds = deadline - monotonic()
    if seconds <= 0:
        raise TimeoutError("Crustdata web per-call timeout")
    return seconds


def _send(key: str, path: str, body: dict[str, Any],
          deadline: float) -> tuple[object, float | None]:
    """POST JSON to the fixed provider host; return (parsed JSON, X-Credits-Used or None)."""
    headers = {"authorization": f"Bearer {key}", "content-type": "application/json",
               "accept": "application/json", "x-api-version": _VERSION}
    connection = HTTPSConnection(_HOST, timeout=_remaining(deadline))
    try:
        connection.connect()
        sock = connection.sock
        if sock is None:
            raise HTTPException("Crustdata web connection has no socket")
        sock.settimeout(_remaining(deadline))
        connection.request("POST", path, json.dumps(body), headers)
        sock.settimeout(_remaining(deadline))
        response = connection.getresponse()
        credits = _nonnegative_number(response.getheader(_CREDIT_HEADER))
        _remaining(deadline)
        if not 200 <= response.status < 300:
            raise _HttpError(response.status, response.getheader("Retry-After"), credits)
        chunks = bytearray()
        while not response.isclosed():
            sock.settimeout(_remaining(deadline))
            chunk = response.read1(64 * 1024)
            if not chunk:
                break
            chunks.extend(chunk)
        return json.loads(chunks), credits
    finally:
        connection.close()


def _wait(ctx: RunContext, seconds: float) -> None:
    if seconds <= 0:
        return
    remaining = float(rule(ctx.rules, "limits.max_seconds")) - limits.elapsed_seconds(ctx.run.started_at)
    if seconds >= remaining:
        raise limits.LimitExceeded(HeldReason.TIME, "Crustdata web wait would exceed run time limit")
    sleep(seconds)


def _timeout_s(ctx: RunContext, path: str) -> float:
    """Fetch uses web.fetch_timeout_s (pages are slow); search and old configs use the per-call limit."""
    if path == FETCH_PATH:
        web_rules = ctx.rules.get("web")
        seconds = web_rules.get("fetch_timeout_s") if isinstance(web_rules, dict) else None
        if seconds is not None:
            return float(seconds)
    return float(rule(ctx.rules, "limits.per_call_timeout_s"))


def _attempt(ctx: RunContext, key: str, path: str, body: dict[str, Any],
             default_credits: float, parse: Any) -> tuple[Any, str]:
    """One HTTP call and its one ledger row (written in `finally`, so failures count too)."""
    timeout = _timeout_s(ctx, path)
    call_id = ledger.new_call_id()
    endpoint = f"POST {path}"
    credits = 0.0
    started = monotonic()
    error: str | None = "request_interrupted"
    try:
        payload, reported = _send(key, path, body, started + timeout)
        credits = reported if reported is not None else default_credits
        result = parse(payload)
        _remaining(started + timeout)
        error = None
        return result, call_id
    except _HttpError as exc:
        error = f"http_{exc.status}"
        credits = exc.credits if exc.credits is not None else credits
        raise
    except TimeoutError:
        error = "timeout"
        raise TimeoutError("Crustdata web per-call timeout") from None
    except (OSError, HTTPException, ValueError) as exc:
        error = type(exc).__name__
        raise RuntimeError(f"{endpoint} failed ({error})") from None
    finally:
        ledger.record(ctx.conn, ctx.rules, ctx.run.id, Provider.CRUSTDATA, endpoint,
                      duration_ms=round((monotonic() - started) * 1000),
                      ok=error is None, error=error, credits=credits, call_id=call_id)
        log_step(ctx.run.id, None, "source.crustdata_web", error or "ok",
                 endpoint=endpoint, call_id=call_id)


def _request(ctx: RunContext, path: str, body: dict[str, Any], default_credits: float,
             parse: Any) -> tuple[Any, str]:
    """Check limits, call, and retry at most once, only after an HTTP 429."""
    key = _api_key()
    for attempt in range(2):
        limits.ensure_within(ctx)
        try:
            return _attempt(ctx, key, path, body, default_credits, parse)
        except _HttpError as exc:
            if attempt or exc.status != 429:
                raise
            _wait(ctx, _retry_delay(exc.retry_after))
    raise AssertionError("Unreachable Crustdata web retry state")


def end_of_day_unix(day: str) -> int:
    """'YYYY-MM-DD' -> Unix seconds of 23:59:59 UTC on that day. Bad input raises ValueError."""
    parsed = date.fromisoformat(day.strip())
    midnight = datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc)
    return int(midnight.timestamp()) + _DAY_SECONDS - 1


def _parse_search(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("success") is False:
        raise ValueError("Unexpected Crustdata web search response")
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("Crustdata web search response has no results list")
    kept = []
    for item in results:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str) or not item["url"]:
            continue
        kept.append({"title": item.get("title"), "url": item["url"], "snippet": item.get("snippet"),
                     "position": item.get("position"), "source": item.get("source")})
    return kept


def _fetched_at(timestamp: object) -> str:
    seconds = _nonnegative_number(timestamp)
    if seconds is None:
        return now_iso()
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def _url_key(url: str) -> str:
    return url.strip().rstrip("/")


def _fetch_parser(urls: list[str]) -> Any:
    def parse(payload: object) -> list[dict[str, Any]]:
        if not isinstance(payload, list):
            raise ValueError("Unexpected Crustdata web fetch response")
        by_url: dict[str, dict[str, Any]] = {}
        for item in payload:
            if (not isinstance(item, dict) or item.get("success") is not True
                    or not isinstance(item.get("url"), str) or not isinstance(item.get("content"), str)):
                continue  # failed URL (success false, url null) or unusable item
            by_url.setdefault(_url_key(item["url"]), item)
        pages = []
        for url in urls:
            item = by_url.get(_url_key(url))
            if item is not None:
                pages.append({"url": url, "title": item.get("title"), "html": item["content"],
                              "fetched_at": _fetched_at(item.get("timestamp"))})
        return pages
    return parse


def search(ctx: RunContext, query: str, *, sources: list[str] | None = None, site: str | None = None,
           location: str | None = None, end_date: str | None = None
           ) -> tuple[list[dict[str, Any]], str | None]:
    """Results [{"title", "url", "snippet", "position", "source"}] and the ledger call_id.
    end_date is 'YYYY-MM-DD' and is sent as the Unix seconds at the END of that day (UTC).
    sources defaults to rules web.sources; location defaults to rules web.location."""
    limits.ensure_within(ctx)
    query = query.strip()
    if not query or len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"Web search query must be 1 to {MAX_QUERY_CHARS} characters")
    body: dict[str, Any] = {
        "query": query,
        "sources": list(sources if sources is not None else rule(ctx.rules, "web.sources")),
        "location": location if location is not None else rule(ctx.rules, "web.location"),
    }
    if site:
        body["site"] = site.strip().lower()
    if end_date:
        body["end_date"] = end_of_day_unix(end_date)
    key_id = sha256(_api_key().encode()).hexdigest()
    cache_key = (ctx.run.id, ctx.run.created_at, key_id, json.dumps(body, sort_keys=True))
    with _lock:
        cached = _search_cache.get(cache_key)
        if cached is not None:
            log_step(ctx.run.id, None, "source.crustdata_web", "cache_hit", call_id=cached[1])
            return deepcopy(cached[0]), cached[1]
        results, call_id = _request(ctx, SEARCH_PATH, body, 1.0, _parse_search)
        _search_cache[cache_key] = (results, call_id)
        return deepcopy(results), call_id


def fetch(ctx: RunContext, urls: list[str]) -> tuple[list[dict[str, Any]], str | None]:
    """Fetched pages [{"url", "title", "html", "fetched_at" (ISO UTC)}], successes only, at most
    10 URLs (more raises ValueError), and the ledger call_id."""
    if len(urls) > MAX_FETCH_URLS:
        raise ValueError(f"Web fetch takes at most {MAX_FETCH_URLS} URLs, got {len(urls)}")
    wanted = list(dict.fromkeys(url.strip() for url in urls if url and url.strip()))
    skipped = [url for url in wanted if not url.startswith("https://")]
    if skipped:  # the API takes https URLs only; drop the others instead of failing the claim
        log_step(ctx.run.id, None, "source.crustdata_web", "skip_non_https", count=len(skipped))
        wanted = [url for url in wanted if url.startswith("https://")]
    if not wanted:
        return [], None
    limits.ensure_within(ctx)
    body = {"urls": wanted, "human_mode": bool(rule(ctx.rules, "web.human_mode"))}
    key_id = sha256(_api_key().encode()).hexdigest()
    cache_key = (ctx.run.id, ctx.run.created_at, key_id, tuple(sorted(wanted)))
    with _lock:
        cached = _fetch_cache.get(cache_key)
        if cached is not None:
            log_step(ctx.run.id, None, "source.crustdata_web", "cache_hit", call_id=cached[1])
            pages = {page["url"]: page for page in cached[0]}
            return [deepcopy(pages[url]) for url in wanted if url in pages], cached[1]
        pages, call_id = _request(ctx, FETCH_PATH, body, float(len(wanted)), _fetch_parser(wanted))
        _fetch_cache[cache_key] = (pages, call_id)
        return deepcopy(pages), call_id
