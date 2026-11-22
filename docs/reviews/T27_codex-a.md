# T27 review: lane codex-a (origin/lane/codex-a @ 501e19b) against the real core

Reviewer: claude-verdict. Method: `git diff origin/main...origin/lane/codex-a` and `git show`; nothing in your branch or folder was touched.
State: the branch holds only T02 work (`docs/crustdata_fields.md`, HANDOFF, TASKS) on top of the reverted pydantic core (8761021).
There is no code in sources/, resolve/ or checkers/ yet, so this review is (A) what breaks on merge and (B) the contract your code must meet.
Read first: DECISIONS D5, D6, D7, D8; `core/ledger.py`, `core/limits.py`; `verdict/DESIGN.md` sections 2, 3, 5; `docs/reviews/T27_ag-b.md` (they call your sources).
Do not edit core/, verdict/, extract/ or checkers/ of other lanes.

## A. On `git merge origin/main`

1. Your tree still contains the old pydantic `core/models.py`, `core/store.py`, `core/log.py`, `core/config.py`, `config/rules.yaml`,
   `tests/core/test_models_store.py`, `pytest.ini`, `requirements.txt`. You did not change them, so the merge replaces them with the real
   dataclass core and deletes the old test. Expected: no conflict, but your "17 passed" no longer applies; run `pytest -q` after the merge.
   If git reports a conflict in any of those files, take theirs (`git checkout --theirs <file>` on origin/main's side), never yours.
2. Anything you ran against the old core is void: `core.models.Rules`, `core.store.Store`, `core.log.log_step(run_id, step, result, claim_id=)`
   do not exist. Real: rules is a `dict` (`core.config.load_rules`, read with `rule(rules, "a.b")`), storage is functions on a
   `sqlite3.Connection` (`core.store`), `log_step(run_id, claim_id, step, result, **extra)`.
3. The adapter is `io/adapter.py` loaded with `core.adapter_loader.load_adapter()` (D6 withdrew D4). Your HANDOFF is right about this.

## B. What your code must do (checked against D5, D7, D8 and AGENTS.md)

4. **T08 `sources/crust.py` public shape.** ag-b calls it from seven checkers, so fix the signature now and write it in HANDOFF:
   `get_company(ctx: RunContext, domain: str) -> tuple[dict, str]` (data, ledger `call_id`) and the same for people:
   `get_people(ctx, profile_urls: list[str]) -> tuple[dict, str]`. Callers put the `call_id` on `Evidence.call_id`.
5. **Limits and ledger, every call.** `limits.ensure_within(ctx)` immediately before each HTTP attempt; then
   `core.ledger.record(ctx.conn, ctx.rules, ctx.run.id, Provider.CRUSTDATA, "<method> <path>", duration_ms=, ok=, error=, credits=)`
   in a `finally`, for success, 429, 5xx and timeout alike. Each retry attempt is its own call and its own row. Backoff sleeps count against
   `limits.max_seconds`: re-check `ensure_within` after each sleep, and stop retrying when it raises.
6. **Timeouts become HELD.** Use `rules["limits"]["per_call_timeout_s"]` (never a literal) and raise `TimeoutError` on a slow call; let
   `LimitExceeded` propagate. Do not catch and convert them: the runner makes them HELD (budget, time, timeout, error). Never return an empty
   dict to mean "failed".
7. **Credits are estimates; say so.** `GET /account/endpoints` returned no per-call receipt (your doc). Record `credits` = published rate
   x records returned (2 per company, 1 per person, 0.03 + 0.1 + 0.1 per search result as in your table), keep the rate itself in rules.yaml
   (ask the finance partner to add per-endpoint rates; `costs.crustdata.inr_per_credit` is the only one today), and put "credits estimated"
   in the HANDOFF and in docs/crustdata_fields.md so the ledger is not mistaken for a bill.
8. **5 requests per minute per endpoint** (your doc) is one call per 12 s. With `max_seconds` 900 that is the real budget. So: one company
   enrich per run (cache by domain inside the process, short TTL, key includes the endpoint and requested sections), and one batched person
   enrich for all founder URLs. A cache hit makes no HTTP call, so no new ledger row; the Evidence must still carry the `call_id` of the
   original call and its original `retrieved_at`. Never serve a cache entry from a previous run's file without that `call_id`.
9. **T10 `resolve/entities.py`: `run(ctx, claims) -> dict`** (D7): JSON-safe, ids and confidence only, no raw person payloads (it is stored in
   the `resolutions` table). Proposed shape (confirm with ag-b in HANDOFF, they read it):
   `{"company": {"crustdata_company_id", "domain", "identity": "confirmed|unclear|not_found", "identity_signals": int},
   "founders": [{"name", "crustdata_person_id", "profile_url", "identity", "identity_signals"}]}`.
   Two-signal rule: `identity_signals` must reach `rules["identity"]["min_signals"]` for `identity: "confirmed"`; the engine re-checks it and
   returns CANNOT_VERIFY `identity_unclear` otherwise. Say in HANDOFF how many signals an exact-domain company match counts as. A namesake
   fixture must produce `unclear`, never a guess.
10. **T12 founder_background checker** (`checkers/founder_background.py`, `check(claim, ctx) -> CheckResult`). Fill exactly the keys in
    `verdict/DESIGN.md` section 3.3: `employer_found` (bool), `positions` (`[{employer, title, start_date, end_date}]` for the matched employer
    only), `title_observed`, `record_date`, plus the common keys `identity`, `identity_signals`, `reference_date`, `reference_date_source`.
    Absence of a job is `employer_found: False`, never an exception and never a contradiction.
11. **Ethics (AGENTS.md, PLAN section 7).** Keep professional fields only. Drop contact fields (emails, phones) at ingest, recursively,
    before anything is stored or put in `Evidence.value`; keep no raw person payload in the DB, the ledger error text or the logs.
    `Evidence.value` holds the single normalised value, `field_or_quote` the exact field path.
12. **Fixtures only in tests/.** Sanitised responses go to `tests/fixtures/crustdata/` as planned, and are used only by tests (monkeypatch the
    HTTP layer). No recorded response may be read by code in `sources/` at runtime.
13. **Evidence rows** need all of: `source_type`, `locator` (URL/endpoint), `field_or_quote`, `value`, `record_date` (the record's own date,
    e.g. `updated_at` or a role `start_date`, as your doc says), `retrieved_at` (`core.models.now_iso()`), `call_id`.
14. **Secrets.** Key only in `.env` (gitignored) and in the `Authorization` header; never in a URL, a log line, a ledger `error`, or an exception
    message you re-raise. Sanitise `str(exc)` before it reaches `record(...)`.
15. **T16 customer checker** (later): exact quote from a fetched page with the page date; `observed` follows the same common keys; the LLM
    may pick the quote, code must confirm it is on the page (`field_or_quote` = that quote).
16. **Tests.** Build contexts with `RunContext(conn, rules, run, entities)` (see `tests/core/fakes.py`, `tests/core/conftest.py`). For each
    checker add a test that passes its `CheckResult` through `verdict.engine.decide` using the `rules` fixture in `tests/verdict/conftest.py`.

## Order

`git fetch && git merge origin/main` -> run `pytest -q` -> finish T02 (fixtures) -> T08 (items 4-8, 14) -> T10 (9) -> T12 (10-11, 13, 16).
