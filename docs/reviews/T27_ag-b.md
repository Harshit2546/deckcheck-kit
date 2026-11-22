# T27 review: lane ag-b (origin/lane/ag-b @ 64b2a9e) against the real core

Reviewer: claude-verdict. Method: copied your extract/, checkers/ and tests onto a scratch copy of
origin/main (4fdb24d) and ran them; nothing in your branch or folder was touched.
Your branch started from the reverted pydantic core (8761021). After `git merge origin/main` the core
becomes the real one: dataclasses, `core/log.py`, `core/ledger.py`, `core/limits.py`, `RunContext`.
Result today: `pytest tests/checkers tests/extract` fails at import (`CheckContext`, `Rules`, `Store` do not exist).
Read first: DECISIONS D5, D7, D8, `verdict/DESIGN.md` sections 2, 3, 5. Do not edit core/, verdict/ or sources/.

Good already (keep): quote-on-slide check (`extract/claims.py:52-89`), a ledger row written in `finally`
(`:270-302`), no `print()`, no mock data in the runtime path except item 12, no contact fields, checkers never choose a label.

## Fixes, in order

1. **Wrong context type.** `checkers/*.py:14` imports `CheckContext` (does not exist). Use
   `from core.models import RunContext` and `def check(claim: Claim, ctx: RunContext) -> CheckResult`.
   Replace `ctx.run_id` with `ctx.run.id` (all 25 uses), `ctx.company_domain` (`team_size.py:24` and the same line in
   funding, hiring, team_growth, traction) with `ctx.run.input.domain`. Delete `ctx.company` (`:21-22`): `ctx.entities`
   holds ids and confidence only (D7), so fetch company data through sources.

2. **`log_step` argument order.** Real signature: `log_step(run_id, claim_id, step, result, **extra)`.
   Your 28 calls pass `(run_id, step, result, claim_id=...)`, which raises `TypeError: multiple values for argument 'claim_id'`
   (e.g. `team_size.py:50-56`, `extract/claims.py:78,269`, `extract/pdf.py:32,61,84`). Change every call to
   `log_step(ctx.run.id, claim.id, "check.team_size", "ok", ...)`; use `None` for claim_id where there is none, and
   `log_error(...)` for failures.

3. **Evidence is missing required fields.** All 13 `Evidence(...)` calls (e.g. `team_size.py:118-126`) omit
   `retrieved_at` and `call_id`, which the real dataclass requires (`TypeError`). Add `retrieved_at=now_iso()`
   (from `core.models`) and `call_id=<id of the ledger row of the call that returned the data>`. Every fact needs
   source, exact field, record date and retrieved_at; today none carries `retrieved_at`.

4. **Sources call and ledger.** `team_size.py:28-38` (same block in funding, hiring, team_growth, traction) calls
   `sources.crust.get_company(domain, run_id=...)`. D7 says: `limits.ensure_within(ctx)` before every external call
   and `core.ledger.record(ctx.conn, ctx.rules, ctx.run.id, Provider.CRUSTDATA, endpoint, duration_ms=, ok=, credits=, call_id=)`
   in a `finally`. That lives in sources/ (codex-a). Agree one signature with codex-a in HANDOFF, suggested:
   `get_company(ctx, domain) -> tuple[dict, str]` returning the data and the ledger `call_id`. Put that `call_id` on the Evidence.
   `market_size.py:30-32` (`sources.web.search_market_data`) the same.

5. **Do not swallow errors.** `team_size.py:33-38` (and the 4 copies): `except ImportError: return None, None` hides a
   missing module as "no data", and `except Exception` guesses `"timeout"` from the message. The runner already turns
   `LimitExceeded` (budget/time), `TimeoutError` and any exception into HELD with the right reason (D7). Delete both
   `except` blocks; let exceptions propagate. A missing source module must fail loudly, not become CANNOT_VERIFY.

6. **`observed` keys do not match what the engine reads** (D8, DESIGN.md sections 2 and 3). Add to every checker:
   `identity` (`"confirmed"`), `identity_signals` (int; company matched by exact domain: agree the count with codex-a, it must be
   at least `identity.min_signals` in rules.yaml), `record_date` (replaces `as_of`: `team_size.py:145` and each
   checker's `observed["as_of"]`), `reference_date` (= `claim.as_of` if it is an ISO date, else `ctx.run.input.deck_date`),
   `reference_date_source` (= `ctx.run.input.deck_date_source`).
   Per type:
   - team_size: keep `headcount` (`:128`); replace `range` (`:142`, a string like "51-200") with
     `headcount_range: [51, 200]` (numbers; omit for open bands such as "10001+").
   - funding: `currency` ("USD", your fields are `*_usd`), `total_raised` summed over rounds dated on or before the
     reference date only, `excluded_later_rounds`, `undated_rounds`, `matched_round` (`{stage, amount, currency, date,
     investors}` or `None`), `investors_found` (list of names), `record_date`. Drop `amount`, `date`, `round_type`, `rounds`.
   - team_growth, hiring, traction, market_size, competition: no verdict rule exists yet; keep your keys, add the common ones above.

7. **`comparable` means something specific.** Your checkers set `comparable=False` when nothing was found
   (`team_size.py:72-77`, `:147`). `comparable=False` means NOT_COMPARABLE and needs `observed["not_comparable_reason"]`
   (for example `metric_mismatch`). No data found: `comparable=True`, no evidence, empty `observed`
   (the engine returns CANNOT_VERIFY `no_evidence`). Never put a held reason in `observed={}` yourself; raise instead (item 5).

8. **Funding falls back to the wrong round.** `funding.py:166-171`: when no round name matches, it compares the deck
   with the LAST round (or the total). That can produce a false CONTRADICTED. Set `matched_round=None` instead; the engine
   then says CANNOT_VERIFY `round_not_found`. Choose the rule from `claim.metric` (`total_raised`, `round_amount`, `investor`),
   not from keywords in the quote (`:141-146`). Match rounds by stage name and, when the claim has `as_of`, by date.

9. **extract/claims.py does not fit the real core.** `:19-29` imports `Rules` and `Store` (neither exists: rules is a dict,
   storage is functions taking a `sqlite3.Connection`). D7 requires `run(ctx: RunContext) -> list[Claim]` and there is none.
   Add it: slides from `extract_pdf_slides(ctx.run.input.deck_path, ctx.run.id)`; `limits.ensure_within(ctx)` before the LLM call;
   in `finally`: `core.ledger.record(ctx.conn, ctx.rules, ctx.run.id, Provider.LLM, model_name, duration_ms=, ok=, error=,
   tokens_in=, tokens_out=)`; remove `store.add_ledger` (`:291`) and your own `LedgerEntry` (`:276-288`). Keep `extract_claims`
   only if tests use it as an inner helper. The runner assigns the claim ids (`<run_id>-c001`), your uuid ids are replaced; fine.

10. **Hard-coded money and limits.** `claims.py:241-242` fallback prices 0.25 / 1.25 and `:235-239` (`except Exception: rules = None`)
    break "rates live in rules.yaml": delete; `core.ledger` computes `cost_inr` from `costs.llm`. `:171`, `:187` hard-coded model names
    and `:177`, `:195` `timeout=30`: take the timeout from `rules["limits"]["per_call_timeout_s"]`
    and turn `requests.Timeout` into `TimeoutError` (the runner makes it HELD).

11. **API key leak.** `claims.py:172` puts the Gemini key in the URL (`?key=...`). `requests` exceptions include the URL, and
    `:268` copies `str(exc)` into the ledger row and the log. Send the key in the `x-goog-api-key` header, and never log or store
    `str(exc)` without removing any URL. Check `git log -p` of your branch shows no key, ever.

12. **Test back door in the runtime path.** `competition.py:49-50` and `market_size.py:25` read `ctx.extras["competitors"]`,
    `ctx.extras["market_data"]`. `RunContext` has no `extras`; data supplied through the context is mock data in the runtime
    path. Remove it; tests should monkeypatch `sources.web`.

13. **Prompt vocabulary does not match the claim contract** (`claims.py:36-49`). Change the prompt so that for team_size, funding
    and founder_background claims: `metric` is one of `headcount`, `total_raised`, `round_amount`, `investor`, `past_employer`, `title`,
    `tenure_years`; `value` is an absolute number in major units (5000000, never "5M", "Cr", "k" or "150%"); `unit` is `people` or an ISO
    currency code (`USD`, `INR`), not "employees"; `as_of` is `YYYY-MM-DD` when the slide gives a date, else null.
    Also: `:121-122` an unknown `type` silently becomes `company_fact`: drop the claim and log it. `:128` `int(item.get("slide", 1))` can raise
    or point at the wrong slide: skip the claim when slide is missing or not an integer.

14. **Deck date from PDF metadata is missing** (PLAN section 1: fallback, flagged). In `run(ctx)`: if `ctx.run.input.deck_date` is None, read
    the PDF `CreationDate` and call `store.update_run_input(ctx.conn, ctx.run.id, date, "pdf_metadata")`, else `(None, "missing")`.

15. **Dependencies.** `pypdf` and `requests` are not in requirements.txt (claude-core owns it). Write a HANDOFF line asking for both.

16. **Tests.** `tests/checkers/*` and `tests/extract/*` build `CheckContext`/`Store`. Rebuild them on `RunContext` (see `tests/core/fakes.py` and
    `tests/core/conftest.py` for the `conn` and `rules` fixtures). Add one test per checker that feeds its `CheckResult` to
    `verdict.engine.decide` (use the `rules` fixture in `tests/verdict/conftest.py`, it adds the D8 `verdict:` block) and asserts the
    label is not `CANNOT_VERIFY` with reason `identity_unclear`, `missing_record_date` or `no_reference_date`.

## Merge order that works

`git fetch && git merge origin/main`, fix 1-3 and 16 first (imports and tests collect), then 4-8, then 9-15. Run `pytest -q` before asking for a merge.
