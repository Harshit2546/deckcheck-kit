"""Checker for customer claims: dated, quoted web mentions of the customer with the company (D16).

Who calls it: core/runner.py (STAGES["check"]).
What it calls: sources.web (search, fetch), sources.pages (page_text, published_date),
extract.quotes (pick_quote), checkers._common (company_identity), core/models.py, core/log.py.
Flow and `observed` keys: docs/WEB_SOURCE.md sections 2 and 3. Source errors are not caught.
"""

from __future__ import annotations

import uuid
from typing import Any

from checkers import _common
from checkers.market_size import _domain, _reference_date, _top_urls
from core.log import log_step
from core.models import CheckResult, Claim, Evidence, RunContext, SourceType
from extract import quotes
from sources import pages, web


def _is_independent(page_domain: str, company_domain: str) -> bool:
    """True when the page is not on the deck company's domain or a subdomain of it."""
    if not company_domain:
        return False   # no company domain to compare with: never claim independence
    return not (page_domain == company_domain or page_domain.endswith("." + company_domain))


def check(claim: Claim, ctx: RunContext) -> CheckResult:
    """Search, fetch, date-filter and quote pages naming the customer together with the company."""
    ref_date, ref_source = _reference_date(claim, ctx)
    customer_name = str(claim.value).strip() if isinstance(claim.value, str) else ""
    company_name = (claim.subject or "").strip()
    observed: dict[str, Any] = {
        **_common.company_identity(ctx),
        "record_date": None,
        "reference_date": ref_date,
        "reference_date_source": ref_source,
        "customer_name": customer_name or None,
        "mentions": [],
        "undated_items_used": 0,
    }
    skipped = {"pages_without_date": 0, "pages_after_reference": 0}   # logged only (section 3)
    if not customer_name or not company_name:
        log_step(ctx.run.id, claim.id, "check.customer", "cannot_verify", reason="no_customer_or_company")
        return CheckResult(evidence=[], observed=observed, comparable=True, held_reason=None)

    company_domain = _domain("https://" + ctx.run.input.domain.strip().lower()) if ctx.run.input.domain else ""
    results, _search_call = web.search(ctx, f'"{customer_name}" "{company_name}"', end_date=ref_date)
    urls = _top_urls(results, int(ctx.rules["web"]["results_to_fetch"]))
    fetched, fetch_call = web.fetch(ctx, urls) if urls else ([], None)

    def accept(page: dict[str, Any], published: str | None) -> bool:
        """Quote check for one page; adds the mention if a verified quote names both parties."""
        quote, _llm_call = quotes.pick_quote(
            ctx, pages.page_text(page.get("html") or ""), f"Is {customer_name} a customer of {company_name}?",
            [customer_name, company_name])
        if not quote:
            return False
        ev = Evidence(
            id=uuid.uuid4().hex,
            claim_id=claim.id,
            source_type=SourceType.WEB_PAGE,
            locator=page["url"],
            field_or_quote=quote,
            value=customer_name,
            record_date=published,
            retrieved_at=page["fetched_at"],
            call_id=fetch_call,
        )
        evidence.append(ev)
        page_domain = _domain(page["url"])
        observed["mentions"].append({
            "url": page["url"], "domain": page_domain, "quote": quote, "published_date": published,
            "independent": _is_independent(page_domain, company_domain), "evidence_id": ev.id,
        })
        return True

    evidence: list[Evidence] = []
    undated: list[dict[str, Any]] = []
    for page in fetched:
        published, _where = pages.published_date(page.get("html") or "")
        if published is None:
            skipped["pages_without_date"] += 1
            undated.append(page)
            continue
        if ref_date is not None and published > ref_date:
            skipped["pages_after_reference"] += 1
            continue
        accept(page, published)
    # D17: undated pages only when no dated page gave a mention; never mixed with dated ones.
    if not observed["mentions"]:
        observed["undated_items_used"] = sum(accept(page, None) for page in undated)

    dates = [m["published_date"] for m in observed["mentions"] if m["published_date"]]
    observed["record_date"] = max(dates) if dates else None
    log_step(ctx.run.id, claim.id, "check.customer", "ok", urls=len(urls), pages=len(fetched),
             evidence_count=len(evidence), undated_items_used=observed["undated_items_used"], **skipped)
    return CheckResult(evidence=evidence, observed=observed, comparable=True, held_reason=None)
