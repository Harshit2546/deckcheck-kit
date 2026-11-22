"""Checker for market_size claims: dated, quoted market estimates from web pages (D16).

Who calls it: core/runner.py (STAGES["check"]).
What it calls: sources.web (search, fetch), sources.pages (page_text, published_date),
extract.quotes (pick_quote, parse_amount), core/models.py, core/log.py.
Flow and `observed` keys: docs/WEB_SOURCE.md sections 2 and 3. Source errors are not caught.
"""

from __future__ import annotations

import re
import uuid
from typing import Any
from urllib.parse import urlparse

from core.log import log_step
from core.models import CheckResult, Claim, Evidence, RunContext, SourceType
from extract import quotes
from sources import pages, web

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _reference_date(claim: Claim, ctx: RunContext) -> tuple[str | None, str]:
    """(reference_date, reference_date_source): claim.as_of if ISO, else the deck date."""
    ref_date = None
    if claim.as_of and _ISO_DATE.match(claim.as_of.strip()):
        ref_date = claim.as_of.strip()
    elif ctx.run.input.deck_date:
        ref_date = ctx.run.input.deck_date.strip()[:10]
    return ref_date, ctx.run.input.deck_date_source or "input"


def _domain(url: str) -> str:
    """Lower-case host of a URL without a leading 'www.'."""
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _top_urls(results: list[dict[str, Any]], limit: int) -> list[str]:
    """First `limit` distinct result URLs, in search order."""
    urls: list[str] = []
    for item in results:
        url = item.get("url")
        if url and url not in urls:
            urls.append(url)
        if len(urls) == limit:
            break
    return urls


def check(claim: Claim, ctx: RunContext) -> CheckResult:
    """Search, fetch, date-filter and quote web pages for the claimed market's size."""
    ref_date, ref_source = _reference_date(claim, ctx)
    observed: dict[str, Any] = {
        # A market is not a company or person: the engine skips the two-signal check (D16).
        "identity": "not_applicable",
        "identity_signals": 0,
        "record_date": None,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
        "estimates": [],
        "pages_without_date": 0,
        "pages_after_reference": 0,
    }
    subject = (claim.subject or claim.quote).strip()
    results, _search_call = web.search(ctx, f"{subject} market size", end_date=ref_date)
    urls = _top_urls(results, int(ctx.rules["web"]["results_to_fetch"]))
    fetched, fetch_call = web.fetch(ctx, urls) if urls else ([], None)

    evidence: list[Evidence] = []
    for page in fetched:
        html = page.get("html") or ""
        published, _where = pages.published_date(html)
        if published is None:
            observed["pages_without_date"] += 1
            continue
        if ref_date is not None and published > ref_date:
            observed["pages_after_reference"] += 1
            continue
        text = pages.page_text(html)
        quote, _llm_call = quotes.pick_quote(
            ctx, text, f"What is the size of the {subject} market?", [])
        if not quote:
            continue
        value, currency = quotes.parse_amount(quote)
        if value is None:
            continue
        ev = Evidence(
            id=uuid.uuid4().hex,
            claim_id=claim.id,
            source_type=SourceType.WEB_PAGE,
            locator=page["url"],
            field_or_quote=quote,
            value=value,
            record_date=published,
            retrieved_at=page["fetched_at"],
            call_id=fetch_call,
        )
        evidence.append(ev)
        observed["estimates"].append({
            "value": value, "currency": currency, "url": page["url"], "domain": _domain(page["url"]),
            "quote": quote, "published_date": published, "evidence_id": ev.id,
        })

    if observed["estimates"]:
        observed["record_date"] = max(e["published_date"] for e in observed["estimates"])
    log_step(ctx.run.id, claim.id, "check.market_size", "ok", urls=len(urls), pages=len(fetched),
             evidence_count=len(evidence), pages_without_date=observed["pages_without_date"],
             pages_after_reference=observed["pages_after_reference"])
    return CheckResult(evidence=evidence, observed=observed, comparable=True, held_reason=None)
