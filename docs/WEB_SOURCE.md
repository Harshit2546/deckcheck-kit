# WEB_SOURCE.md: web search source for market_size and customer claims

Status: design agreed 2026-11-22 15:30 (DECISIONS D16). Tasks T30 to T33 build it.
Goal: slides like Deck A 6 (customer) and 7 (market size) get a real, dated, quoted
verdict instead of `HELD`. Every rule in AGENTS.md section 2 still applies.

## 1. Provider: Crustdata Web APIs

The data comes from the same Crustdata key and the same ledger as `get_company`. Facts below
were read from docs.crustdata.com on 2026-11-22.

| | Search | Fetch |
|---|---|---|
| Call | `POST https://api.crustdata.com/web/search/live` | `POST https://api.crustdata.com/web/enrich/live` |
| Headers | `authorization: Bearer <CRUSTDATA_API_KEY>`, `content-type: application/json`, `x-api-version: 2025-11-01` | same |
| Body | `query` (required, max 5,000 chars), `sources` (`web`, `news`, ...), `location` (ISO country, e.g. `IN`), `site` (domain), `start_date`/`end_date` (Unix **seconds**), `page` (1 to 15, about 10 results each) | `urls` (1 to 10, with `https://`), `human_mode` |
| Response | `{success, query, timestamp (ms), results[], metadata}`; each result has `source, title, url, snippet, position` | a top-level **array**, one item per URL: `{success, url, timestamp (s), title, content (HTML)}`. A failed URL has `success: false` and `url: null`. Order may differ from the request, so match by `url`. |
| Cost | 1 credit per page of results | 1 credit per URL fetched (from "1 per page"; not confirmed for a 10-URL call) |
| Rate | 10 requests per minute | 10 requests per minute |

The actual charge is in the `X-Credits-Used` response header; use it when present.

**The catch: search results carry no publish date.** The only times returned are the
search time and the fetch time, and neither is the record's own date. So the record date
must be read **from the fetched page's HTML by code** (section 3). A page with no
readable date gives no usable fact, and the claim becomes `CANNOT_VERIFY missing_record_date`.

## 2. Flow for one claim

```
claim -> checker builds query -> web.search (1 call, end_date = reference date)
      -> keep the top tolerances/web.results_to_fetch URLs -> web.fetch (1 call)
      -> per page: pages.page_text + pages.published_date (code)
      -> skip a page with no date, or a date after the reference date
      -> quotes.pick_quote (LLM returns ONE exact sentence; code checks it is on the page)
      -> quotes.parse_amount (code reads the number and currency from the quote)
      -> Evidence(source_type=web_page, locator=url, field_or_quote=quote,
                  value=number or name, record_date=published date, call_id=fetch call id)
      -> verdict/engine.py decides (T33)
```

The LLM only picks a sentence. Code checks that the sentence is on the page, reads the number,
reads the date and decides the label. With the default of 3 URLs, a claim costs 1 search
credit plus 3 fetch credits, plus one LLM call per page.

## 3. Contracts (D16; change only through a new DECISIONS entry)

### sources/web.py (T30)

```python
def search(ctx: RunContext, query: str, *, sources: list[str] | None = None, site: str | None = None,
           location: str | None = None, end_date: str | None = None
           ) -> tuple[list[dict[str, Any]], str | None]:
    """Results [{"title", "url", "snippet", "position", "source"}] and the ledger call_id.
    end_date is 'YYYY-MM-DD' and is sent as the Unix seconds at the END of that day (UTC).
    sources defaults to rules web.sources; location defaults to rules web.location."""

def fetch(ctx: RunContext, urls: list[str]) -> tuple[list[dict[str, Any]], str | None]:
    """Fetched pages [{"url", "title", "html", "fetched_at" (ISO UTC)}], successes only, at most
    10 URLs (more raises ValueError), and the ledger call_id."""
```

Both functions:
- call `limits.ensure_within(ctx)` first;
- write ONE ledger row per HTTP call, including failed ones, with `Provider.CRUSTDATA` and
  endpoint `POST /web/search/live` or `POST /web/enrich/live`; credits from `X-Credits-Used`,
  else 1 per search page or 1 per URL;
- raise `TimeoutError` after `limits.per_call_timeout_s`, which the runner turns into HELD timeout;
- retry only on HTTP 429, at most once, after `Retry-After`, the same as `sources/crust.py`;
- raise on any other error, so the runner makes the claim HELD error. They never return
  invented data;
- cache per run by (query and options) or by URL, so a resume or a second claim does not pay twice;
- read the key with the same loader `sources/crust.py` uses (env first, then `.env`), and never log it.

### sources/pages.py (T31): pure functions, no I/O

```python
def page_text(html: str) -> str:
    """Visible text: drop script/style/noscript, unescape entities, collapse whitespace."""

def published_date(html: str) -> tuple[str | None, str | None]:
    """('YYYY-MM-DD', where_found) or (None, None). First hit wins, in this order:
    JSON-LD "datePublished"; meta property="article:published_time";
    meta name in (date, pubdate, publish-date, dc.date, citation_publication_date);
    the first <time datetime=...>. where_found names it, e.g. 'meta[property=article:published_time]'."""
```

Use only the stdlib (`html.parser`, `json`, `re`); add no new package.

### extract/quotes.py (T31)

```python
def pick_quote(ctx: RunContext, page_text: str, question: str, must_contain: list[str]
               ) -> tuple[str | None, str | None]:
    """Ask the LLM for ONE sentence copied exactly from page_text that answers `question`.
    Returns (quote, ledger call_id). quote is None unless code finds it verbatim in page_text
    (after whitespace normalisation) and it contains every must_contain string (case-insensitive).
    page_text is cut to rules web.max_page_chars. One ledger row per call (reuse the provider
    choice in extract/claims.py)."""

def parse_amount(quote: str) -> tuple[float | None, str | None]:
    """(value in major units, ISO currency) read by code from the quote: '$9 billion' -> (9e9, 'USD'),
    'USD 9.2 bn', 'Rs 75,000 crore' / '₹75,000 crore' -> (7.5e11, 'INR'), 'lakh' = 1e5, 'crore' = 1e7.
    (None, None) if the quote has no single clear amount."""
```

### checkers (T32): what `observed` must hold

**market_size** (`checkers/market_size.py`, rewritten). The query is the claim's subject plus
"market size", with `end_date` = reference date.

| key | meaning |
|---|---|
| `identity` | `"not_applicable"`: a market is not a company or person (the engine skips the two-signal check for market_size only, T33) |
| `identity_signals` | `0` |
| `record_date` | the newest `published_date` among the estimates used |
| `reference_date`, `reference_date_source` | as for every checker |
| `estimates` | `[{"value", "currency", "url", "domain", "quote", "published_date", "evidence_id"}]`, one per page with a dated, verified quote and an amount |
| `pages_without_date` | count of fetched pages skipped for having no date |
| `pages_after_reference` | count of pages skipped for being dated after the reference date |

**customer** (new `checkers/customer.py`). The query is `"<customer name>" "<company name>"`,
with `end_date` = reference date. `must_contain` = [customer name, company name].

| key | meaning |
|---|---|
| `identity`, `identity_signals` | from `_common.company_identity(ctx)` (the deck company) |
| `record_date` | the newest `published_date` among the mentions used |
| `customer_name` | the name as the claim states it |
| `mentions` | `[{"url", "domain", "quote", "published_date", "independent", "evidence_id"}]` |
| `independent` | code sets it: True when the page's domain is NOT the deck company's domain (or a subdomain of it) |

Each estimate or mention has one Evidence row: `source_type=web_page`, `locator=url`,
`field_or_quote=quote`, `record_date=published_date`, `call_id=` the fetch call id.
No page dated, or nothing verified: return no evidence, and the engine says `no_evidence`.

### verdict rules (T33): cautious, the pass mark allows no wrong SUPPORTED or CONTRADICTED

**market_size** (`tolerances.market_size`):
- Only estimates in the claim's currency count. If all of them are in another currency, the
  result is NOT_COMPARABLE `currency_mismatch`.
- At least one estimate within `tolerance_pct` of the claim gives SUPPORTED, at most medium
  confidence (third-party estimates).
- CONTRADICTED needs all three of these, and is then at most medium confidence:
  - at least `min_agreeing_sources` estimates from **different domains** all fall outside tolerance;
  - those estimates agree with each other within tolerance;
  - none of the estimates supports the claim.
- Anything else gives CANNOT_VERIFY `source_may_be_incomplete`.

**customer** (`tolerances.customer`):
- An independent mention gives SUPPORTED, medium confidence.
- Only self-published mentions give CANNOT_VERIFY `self_reported_only`.
- Never CONTRADICTED: not finding a customer is not evidence against the claim.

Both rules use `tolerances.<type>.max_record_age_days` (D14 pattern).

## 4. rules.yaml keys (added with D16, all PLACEHOLDER)

```yaml
web:
  sources: [news, web]
  location: IN
  results_to_fetch: 3
  max_page_chars: 12000
  human_mode: false
tolerances:
  market_size: {tolerance_pct: 50, min_agreeing_sources: 2, max_record_age_days: 1095}
  customer:    {require_exact_quote: true, max_record_age_days: 1095}
```

Web credits are Crustdata credits, so `costs.crustdata.inr_per_credit` prices them;
`costs.web.inr_per_call` stays 0.

## 5. Tasks (each in its own worktree and branch, files do not overlap)

| Task | Branch | Files it may touch | Depends on |
|---|---|---|---|
| T30 web client | `lane/web-client` | `sources/web.py`, `tests/sources/test_web.py`, `tests/fixtures/web/` | contract only |
| T31 pages + quotes | `lane/web-pages` | `sources/pages.py`, `extract/quotes.py`, `tests/sources/test_pages.py`, `tests/extract/test_quotes.py`, `tests/fixtures/pages/` | contract only |
| T32 checkers | `lane/web-checkers` | `checkers/market_size.py`, `checkers/customer.py`, `tests/checkers/test_market_size.py`, `tests/checkers/test_customer.py` | contract only; tests fake `sources.web`, `sources.pages`, `extract.quotes` with monkeypatch |
| T33 verdict rules | `lane/claude-verdict` | `verdict/market_size.py`, `verdict/customer.py`, `verdict/engine.py`, `verdict/common.py`, `verdict/DESIGN.md`, `tests/verdict/` | contract only |

Every task ends with: `python -m pytest -q` green; `python tests/eval/run_eval.py` no worse than
4 PASS, 2 FAIL, 1 SKIP; a HANDOFF.md entry; TASKS.md updated; the branch pushed. Only the
merger merges to main, in a throwaway worktree. Freeze is 18:00, so stop coding by 17:15.

After all four are merged: one live Deck A run (about 8 web credits) needs the user's OK. If
the eval answer key still expects CANNOT_VERIFY for slides 6 and 7, compare it with the live
result before changing anything.

## 6. Known limits

- Many pages have no machine-readable publish date. Those pages are skipped, which is honest
  but can leave a claim unverified.
- `human_mode` is off by default. Sites behind bot protection may fail to fetch, and a failed
  page is simply not used.
- An LLM call per page costs tokens. `results_to_fetch` limits that, and it is in rules.yaml.
