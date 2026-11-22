"""Fetch a company (exact domain) and founders (profile URLs or name + employer id) from Crustdata.
Called by DeckCheck's resolver (resolve/entities.py) and the company and founder checkers.
Uses core run limits, the call ledger, and the provider's HTTPS API. Person payloads lose every
contact field (any key with "email", "phone" or "contact" in it) at ingest, before cache or caller.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from http.client import HTTPException, HTTPSConnection
from pathlib import Path
from threading import Lock
from time import monotonic, sleep
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from core import ledger, limits, store
from core.config import rule
from core.env import get_key
from core.tls import tls_context
from core.log import log_step
from core.models import HeldReason, Provider, RunContext, now_iso

_HOST = "api.crustdata.com"
_VERSION = "2025-11-01"
_COMPANY_PATH = "/company/enrich"
_ACCOUNT_PATH = "/account/endpoints"
_WEB_PATH = "/web/search/live"
_COMPANY_FIELDS = ("basic_info", "locations", "headcount", "funding", "revenue",
                   "hiring", "competitors")
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
_MINUTE = 60.0
_CREDIT_HEADERS = ("x-credits-charged", "x-crustdata-credits-charged", "x-request-credits")

_lock = Lock()
_company_cache: dict[tuple[str, str, str, str], tuple[float, dict[str, Any], str]] = {}
_account_cache: dict[str, tuple[float, float, float]] = {}  # expiry, rpm, credits per record
_next_company_call: dict[str, float] = {}
_PEOPLE_PATH = "/person/enrich"
_PEOPLE_SEARCH_PATH = "/person/search"
_PERSON_FIELDS = ("basic_profile", "social_handles", "experience", "education")
_SEARCH_CREDITS_PER_RESULT = 0.23  # docs: 0.03 base + 0.1 experience filter + 0.1 experience fields
_SEARCH_LIMIT = 10
_CONTACT_MARKERS = ("email", "phone", "contact")
_people_cache: dict[tuple[str, str, str, str], tuple[dict[str, Any], str]] = {}


class _HttpError(RuntimeError):
    def __init__(self, status: int, retry_after: str | None, credits: float | None) -> None:
        super().__init__(f"Crustdata HTTP {status}")
        self.status = status
        self.retry_after = retry_after
        self.credits = credits


def _api_key() -> str:
    key = get_key("CRUSTDATA_API_KEY", path=_ENV_FILE)
    if not key or any(char.isspace() for char in key):
        raise RuntimeError("Set CRUSTDATA_API_KEY in the ignored .env")
    return key


def _nonnegative_number(value: object) -> float | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _remaining(deadline: float) -> float:
    seconds = deadline - monotonic()
    if seconds <= 0:
        raise TimeoutError("Crustdata per-call timeout")
    return seconds


def _send(key: str, path: str, body: dict[str, Any] | None,
          deadline: float) -> tuple[object, float | None]:
    """Send to the fixed provider host, with no redirects or credential logging."""
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json",
               "x-api-version": _VERSION}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body)
    connection = HTTPSConnection(_HOST, timeout=_remaining(deadline), context=tls_context())
    try:
        connection.connect()
        sock = connection.sock
        if sock is None:
            raise HTTPException("Crustdata connection has no socket")
        sock.settimeout(_remaining(deadline))
        connection.request("POST" if body is not None else "GET", path, data, headers)
        sock.settimeout(_remaining(deadline))
        response = connection.getresponse()
        credits = next(
            (number for header in _CREDIT_HEADERS
             if (number := _nonnegative_number(response.getheader(header))) is not None),
            None,
        )
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


def _company_records(payload: object, domain: str) -> list[dict[str, Any]]:
    if (not isinstance(payload, list) or len(payload) != 1
            or not isinstance(payload[0], dict) or not isinstance(payload[0].get("matches"), list)):
        raise ValueError("Unexpected Crustdata company response")
    if payload[0].get("matched_on") != domain:
        raise ValueError("Crustdata company response did not match the requested domain")
    records = []
    for match in payload[0]["matches"]:
        if not isinstance(match, dict) or not isinstance(match.get("company_data"), dict):
            raise ValueError("Unexpected Crustdata company match")
        records.append(match["company_data"])
    return records


def _attempt(ctx: RunContext, key: str, path: str, body: dict[str, Any] | None,
             credits_per_record: float,
             parse: Callable[[object], tuple[Any, float]] | None = None) -> tuple[Any, str]:
    timeout = float(rule(ctx.rules, "limits.per_call_timeout_s"))
    call_id = ledger.new_call_id()
    endpoint = ("POST " if body is not None else "GET ") + path.split("?")[0]
    credits = 0.0
    started = monotonic()
    error = "request_interrupted"
    try:
        payload, reported_credits = _send(key, path, body, started + timeout)
        if reported_credits is not None:
            credits = reported_credits
        if parse is not None:
            payload, estimate = parse(payload)
            if reported_credits is None:
                credits = estimate
        elif body is not None:
            payload = _company_records(payload, body["domains"][0])
            if reported_credits is None:
                credits = len(payload) * credits_per_record
        _remaining(started + timeout)
        error = None
        return payload, call_id
    except _HttpError as exc:
        error = f"http_{exc.status}"
        credits = exc.credits if exc.credits is not None else credits
        raise
    except TimeoutError:
        error = "timeout"
        raise TimeoutError("Crustdata per-call timeout") from None
    except (OSError, HTTPException, ValueError) as exc:
        error = type(exc).__name__
        raise RuntimeError(f"{endpoint} failed ({error})") from None
    finally:
        ledger.record(ctx.conn, ctx.rules, ctx.run.id, Provider.CRUSTDATA, endpoint,
                      duration_ms=round((monotonic() - started) * 1000),
                      ok=error is None, error=error, credits=credits, call_id=call_id)
        log_step(ctx.run.id, None, "source.crustdata", error or "ok",
                 endpoint=endpoint, call_id=call_id)


def _retry_delay(value: str | None) -> float:
    seconds = _nonnegative_number(value)
    if seconds is not None:
        return seconds
    if value:
        try:
            return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            pass
    return 1.0


def _wait(ctx: RunContext, seconds: float) -> None:
    if seconds <= 0:
        return
    remaining = float(rule(ctx.rules, "limits.max_seconds")) - limits.elapsed_seconds(ctx.run.started_at)
    if seconds >= remaining:
        raise limits.LimitExceeded(HeldReason.TIME, "Crustdata wait would exceed run time limit")
    sleep(seconds)


def _ensure_can_afford(ctx: RunContext, credits: float) -> None:
    totals = store.ledger_totals(ctx.conn, ctx.run.id)
    rupees = ledger.cost_inr(ctx.rules, Provider.CRUSTDATA, _COMPANY_PATH, credits, 0, 0)
    if (totals["credits"] + credits > float(rule(ctx.rules, "limits.max_credits"))
            or totals["cost_inr"] + rupees > float(rule(ctx.rules, "limits.max_cost_inr"))):
        raise limits.LimitExceeded(HeldReason.BUDGET, "Crustdata company request would exceed run budget")


def _request(ctx: RunContext, key: str, key_id: str, path: str,
             body: dict[str, Any] | None = None, *, rpm: float = 0.0,
             credits_per_record: float = 0.0,
             parse: Callable[[object], tuple[Any, float]] | None = None) -> tuple[Any, str]:
    for attempt in range(2):
        if rpm:
            _wait(ctx, _next_company_call.get(key_id, 0.0) - monotonic())
        limits.ensure_within(ctx)
        if rpm:
            _ensure_can_afford(ctx, credits_per_record)
            _next_company_call[key_id] = monotonic() + _MINUTE / rpm
        try:
            return _attempt(ctx, key, path, body, credits_per_record, parse)
        except _HttpError as exc:
            if attempt or not (exc.status == 429 or 500 <= exc.status < 600):
                raise
            _wait(ctx, _retry_delay(exc.retry_after))
    raise AssertionError("Unreachable Crustdata retry state")


def _account_policy(ctx: RunContext, key: str, key_id: str) -> tuple[float, float]:
    if key_id in _account_cache:
        _, rpm, credits = _account_cache[key_id]
        return rpm, credits
    payload, _ = _request(ctx, key, key_id, f"{_ACCOUNT_PATH}?path={quote(_COMPANY_PATH, safe='')}")
    endpoints = payload.get("endpoints") if isinstance(payload, dict) else None
    if isinstance(endpoints, list):
        for endpoint in endpoints:
            if not isinstance(endpoint, dict) or endpoint.get("path") != _COMPANY_PATH:
                continue
            rpm = _nonnegative_number(endpoint.get("effective_rate_limit_rpm"))
            credits = _nonnegative_number(endpoint.get("base_credits"))
            if endpoint.get("status") == "enabled" and rpm and credits is not None:
                _account_cache[key_id] = (monotonic() + _MINUTE, rpm, credits)
                return rpm, credits
    raise RuntimeError("Crustdata company endpoint is unavailable or its quota is missing")


def _expire_cache(now: float) -> None:
    for key in [key for key, entry in _company_cache.items() if entry[0] <= now]:
        del _company_cache[key]
    for key in [key for key, entry in _account_cache.items() if entry[0] <= now]:
        del _account_cache[key]
    for key in [key for key, next_call in _next_company_call.items() if next_call <= now]:
        del _next_company_call[key]


def get_company(ctx: RunContext, domain: str) -> tuple[dict[str, Any], str]:
    """Return the exact company's payload and original ledger ID for this run."""
    limits.ensure_within(ctx)
    domain = domain.strip().lower().rstrip(".")
    if not domain:
        raise ValueError("A company domain is required")
    key = _api_key()
    key_id = sha256(key.encode()).hexdigest()
    cache_key = (ctx.run.id, ctx.run.created_at, key_id, domain)
    with _lock:
        _expire_cache(monotonic())
        cached = _company_cache.get(cache_key)
        if cached is not None:
            _, payload, call_id = cached
            log_step(ctx.run.id, None, "source.crustdata", "cache_hit", call_id=call_id)
            return deepcopy(payload), call_id
        rpm, credits = _account_policy(ctx, key, key_id)
        records, call_id = _request(
            ctx, key, key_id, _COMPANY_PATH,
            {"domains": [domain], "exact_match": True, "fields": list(_COMPANY_FIELDS)},
            rpm=rpm, credits_per_record=credits,
        )
        if len(records) > 1:
            raise RuntimeError("Crustdata returned multiple exact-domain company matches")
        payload = {**records[0], "retrieved_at": now_iso()} if records else {}
        _company_cache[cache_key] = (monotonic() + _MINUTE, payload, call_id)
        return deepcopy(payload), call_id


def drop_contact_fields(node: Any) -> Any:
    """Copy of `node` without any key naming an email, phone or contact (recursive)."""
    if isinstance(node, dict):
        return {k: drop_contact_fields(v) for k, v in node.items()
                if not any(marker in str(k).lower() for marker in _CONTACT_MARKERS)}
    if isinstance(node, list):
        return [drop_contact_fields(item) for item in node]
    return node


def _parse_people(sent: int) -> Callable[[object], tuple[dict[str, Any], float]]:
    """Enrich answers a top-level array [{matched_on, match_status, matches[{person_data}]}]."""
    def parse(payload: object) -> tuple[dict[str, Any], float]:
        items = payload if isinstance(payload, list) else [payload]
        matches = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("matches", []), list):
                raise ValueError("Unexpected Crustdata person response")
            matches += [m for m in item.get("matches", []) if isinstance(m, dict)]
        return drop_contact_fields({"matches": matches}), float(sent)
    return parse


def _parse_search(payload: object) -> tuple[dict[str, Any], float]:
    if not isinstance(payload, dict) or not isinstance(payload.get("profiles"), list):
        raise ValueError("Unexpected Crustdata person search response")
    profiles = [p for p in payload["profiles"] if isinstance(p, dict)]
    return drop_contact_fields({"profiles": profiles}), len(profiles) * _SEARCH_CREDITS_PER_RESULT


def _people_call(ctx: RunContext, path: str, body: dict[str, Any], cache_part: str,
                 parse: Callable[[object], tuple[Any, float]]) -> tuple[dict[str, Any], str]:
    limits.ensure_within(ctx)
    key = _api_key()
    key_id = sha256(key.encode()).hexdigest()
    cache_key = (ctx.run.id, ctx.run.created_at, key_id, f"{path} {cache_part}")
    with _lock:
        cached = _people_cache.get(cache_key)
        if cached is not None:
            log_step(ctx.run.id, None, "source.crustdata", "cache_hit", call_id=cached[1])
            return deepcopy(cached[0]), cached[1]
        payload, call_id = _request(ctx, key, key_id, path, body, parse=parse)
        _people_cache[cache_key] = (payload, call_id)
        return deepcopy(payload), call_id


def get_people(ctx: RunContext, profile_urls: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    """ONE batched POST /person/enrich for the founders' profile URLs (D12, D18).
    Returns ({"matches": [{"confidence_score", "person_data"}]}, call_id), contact fields removed,
    or (None, None) when no URL is given. Cached per run by the set of URLs."""
    urls = list(dict.fromkeys(u.strip() for u in profile_urls if u and u.strip()))
    if not urls:
        return None, None
    body = {"professional_network_profile_urls": urls, "fields": list(_PERSON_FIELDS)}
    return _people_call(ctx, _PEOPLE_PATH, body, json.dumps(sorted(urls)), _parse_people(len(urls)))


def search_people(ctx: RunContext, name: str, company_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """POST /person/search for people with this exact name who worked at the employer id (D12, D18).
    Returns ({"profiles": [...]}, call_id), contact fields removed, or (None, None) without a name
    or id. Cached per run by (name, company id)."""
    name = " ".join((name or "").split())
    company_id = str(company_id or "").strip()
    if not name or not company_id:
        return None, None
    employer: object = int(company_id) if company_id.isdigit() else company_id
    body = {
        "filters": {"op": "and", "conditions": [
            {"field": "basic_profile.name", "type": "=", "value": name},
            {"field": "experience.employment_details.company_id", "type": "in", "value": [employer]},
        ]},
        "fields": ["crustdata_person_id", *_PERSON_FIELDS[:3]],
        "limit": _SEARCH_LIMIT,
    }
    return _people_call(ctx, _PEOPLE_SEARCH_PATH, body, json.dumps([name.lower(), company_id]),
                        _parse_search)
