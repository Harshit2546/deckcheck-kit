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

# Words of the claim subject that say nothing about WHICH market it is (INCIDENTS B10).
_STOP_WORDS = {"india", "indian", "global", "the", "of", "and", "market", "size", "industry", "sector"}

# A year in a forecast phrase: "by 2030", "in 2030", "2030E", "projected to reach ... 2030".
_FORECAST_YEAR = re.compile(
    r"\b(?:by|in)\s+(20\d{2})\b"
    r"|\b(20\d{2})E\b"
    r"|\b(?:projected|expected|forecast(?:ed)?)\b[^.]*?\b(20\d{2})\b",
    re.IGNORECASE,
)


def _required_terms(subject: str) -> list[str]:
    """Lower-case subject words minus stop words; each must appear in the quote (B10)."""
    words = re.findall(r"[a-z0-9]+", subject.lower())
    return [w for w in dict.fromkeys(words) if w not in _STOP_WORDS]


def _is_forecast(quote: str, reference_year: int) -> bool:
    """True when the quote projects to a year after the reference year."""
    for m in _FORECAST_YEAR.finditer(quote):
        year = next(g for g in m.groups() if g)
        if int(year) > reference_year:
            return True
    return False


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
        "forecast_quotes_skipped": 0,
        "undated_items_used": 0,
    }
    subject = (claim.subject or claim.quote).strip()
    terms = _required_terms(claim.subject or "")
    results, _search_call = web.search(ctx, f"{subject} market size", end_date=ref_date)
    urls = _top_urls(results, int(ctx.rules["web"]["results_to_fetch"]))
    fetched, fetch_call = web.fetch(ctx, urls) if urls else ([], None)

    def accept(page: dict[str, Any], published: str | None) -> bool:
        """Quote, relevance, forecast and amount checks for one page; adds the estimate if it passes."""
        text = pages.page_text(page.get("html") or "")
        quote, _llm_call = quotes.pick_quote(
            ctx, text, f"What is the size of the {subject} market?", terms)
        if not quote or any(t not in quote.casefold() for t in terms):
            return False   # no quote, or a quote about another market (B10)
        if _is_forecast(quote, int((ref_date or published or page["fetched_at"])[:4])):
            observed["forecast_quotes_skipped"] += 1
            return False
        value, currency = quotes.parse_amount(quote)
        if value is None:
            return False
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
        return True

    evidence: list[Evidence] = []
    undated: list[dict[str, Any]] = []
    for page in fetched:
        published, _where = pages.published_date(page.get("html") or "")
        if published is None:
            observed["pages_without_date"] += 1
            undated.append(page)
            continue
        if ref_date is not None and published > ref_date:
            observed["pages_after_reference"] += 1
            continue
        accept(page, published)
    # D17: undated pages only when no dated page gave an estimate; never mixed with dated ones.
    if not observed["estimates"]:
        observed["undated_items_used"] = sum(accept(page, None) for page in undated)

    dates = [e["published_date"] for e in observed["estimates"] if e["published_date"]]
    observed["record_date"] = max(dates) if dates else None
    log_step(ctx.run.id, claim.id, "check.market_size", "ok", urls=len(urls), pages=len(fetched),
             evidence_count=len(evidence), pages_without_date=observed["pages_without_date"],
             pages_after_reference=observed["pages_after_reference"],
             forecast_quotes_skipped=observed["forecast_quotes_skipped"],
             undated_items_used=observed["undated_items_used"])
    return CheckResult(evidence=evidence, observed=observed, comparable=True, held_reason=None)
