# DECISIONS.md — changes to contracts, rules and requirements

Append-only. One entry per decision. Required before changing anything in
`core/models.py`, the DB schema, a listed function signature, or `config/rules.yaml`
semantics. The hour-3 requirement change from the organizers goes here too.

```
### <HH:MM> · <who> · D<n>: <title>
Change:
Why:
Files affected:
Who must know (lanes):
```

### 11:00 · human · D1: verdicts are decided by code, not the LLM
Change: verdict/engine.py compares values using config/rules.yaml. The LLM only extracts claims, picks exact quotes, and writes explanations.
Why: hidden test cases punish wrong answers more than "cannot verify"; code is repeatable and explainable to judges.
Files affected: verdict/, checkers/
Who must know: all lanes

### 11:00 · human · D2: lanes match the team's real accounts
Change: the single claude lane splits into claude-core (core/, io/adapter.py, actions/) and claude-verdict (verdict/, report/, hour-3 change, merge reviews). Lane codex-b becomes ag-b (Gemini/Antigravity). Third Gemini account is a spare for ag-b or codex-a. Branches: lane/claude-core, lane/claude-verdict, lane/codex-a, lane/ag-b, lane/ag.
Why: the team has 2 Claude Pro, 1 ChatGPT Plus and 3 Gemini Pro accounts, not several Codex accounts. Two Claude lanes on separate folders run in parallel and back each other up.
Files affected: PLAN.md (sections 4-6), TASKS.md, AGENTS.md (section 4), CLAUDE.md
Who must know: all lanes

### 11:45 · claude-core-1 · D4: adapter lives in kit_io/, not io/
Change: the kickoff-kit adapter is `kit_io/adapter.py` (`from_kit()`, `to_kit()`), not `io/adapter.py`. D3 stays reserved for the kit format (T06).
Why: a top-level `io` package cannot be imported; Python's built-in `io` module is already loaded, so `import io.adapter` fails with "'io' is not a package".
Files affected: kit_io/adapter.py; PLAN.md, AGENT_PROMPTS.md and TASKS.md still say io/adapter.py (human-owned docs, not edited).
Who must know: all lanes, humans (merger fills the mapping from D3)

### 11:45 · claude-core-1 · D5: T01 contract details beyond PLAN.md section 3
Change: (1) models are stdlib dataclasses + str Enums in core/models.py; times are ISO UTC strings. (2) Added `Run`, `RunInput`, `InboxMessage` models, `RunState.FAILED`, and `make_idempotency_key()`. (3) Extra tables: `check_results` (checkpoint of each CheckResult so a resume can decide without re-calling) and `reports`. (4) `evidence.call_id` is a foreign key to `ledger.id`. (5) Ledger and inbox are append-only via DB triggers. (6) Claim/Evidence `value` stored as JSON so numbers stay numbers. (7) Rupee rates live under `costs:` in rules.yaml; `core/ledger.record()` computes `cost_inr`.
Why: resume must not repeat calls; every fact must trace to a logged call; rules forbid editing ledger rows.
Files affected: core/models.py, core/store.py, core/ledger.py, core/config.py, config/rules.yaml
Who must know: all lanes (codex-a and ag-b: call `core.ledger.record()` for every external call, in a finally block)

### 12:05 · harshit · D6: D4 withdrawn; adapter stays at io/adapter.py
Change: D4 is withdrawn. The adapter is `io/adapter.py` (`from_kit()`, `to_kit()`, provisional field map with TODO to D3), as PLAN.md and the lane prompt say. Because `import io.adapter` cannot work (stdlib `io` owns the name), callers load it with `core.adapter_loader.load_adapter()`. `kit_io/` is deleted. D5 still holds.
Why: stick to the lane prompt and PLAN.md file layout; only the import mechanism needed a workaround.
Files affected: io/adapter.py, core/adapter_loader.py
Who must know (lanes): all lanes, merger (fills the mapping from D3)

### 12:35 · harshit · D7: how the runner calls every lane (stage signatures), HELD reasons, resolutions table
Change: core/runner.py imports each stage by name (`STAGES` in core/runner.py). Each lane must expose exactly:
- `extract/claims.py: run(ctx: RunContext) -> list[Claim]` (runner assigns ids `<run_id>-c001`...; may call store.update_run_input for the PDF-metadata deck date)
- `resolve/entities.py: run(ctx: RunContext, claims: list[Claim]) -> dict` (JSON-safe: entity ids + confidence only, no raw person payloads; saved in new table `resolutions`, given back as `ctx.entities`)
- `checkers/<claim_type>.py: check(claim: Claim, ctx: RunContext) -> CheckResult` (PLAN.md; evidence.claim_id must equal claim.id)
- `verdict/engine.py: decide(claim: Claim, result: CheckResult, rules: dict) -> Verdict` (must return HELD with reason_code = result.held_reason whenever held_reason is set)
- `report/builder.py: build(conn, rules, run_id) -> tuple[dict, str]` (JSON, Markdown)
- `actions/email.py: draft(conn, rules, run_id) -> Action | None` (claude-core, T19)
New in core/models.py: `RunContext(conn, rules, run, entities)` and `HeldReason` (budget, time, timeout, error, no_checker). New core/limits.py: sources and LLM callers call `limits.ensure_within(ctx)` before every external call (raises `LimitExceeded`), and raise `TimeoutError` when a call exceeds `per_call_timeout_s`. The runner turns LimitExceeded / TimeoutError / any checker exception / a missing checker module into a HELD CheckResult; a missing extract/resolve/verdict/report module leaves the run waiting in its state (resume continues once merged).
Why: other lanes need fixed function shapes to code against now; resume must not repeat calls; limits must hold before every call, not only per claim.
Files affected: core/runner.py, core/limits.py, core/models.py, core/store.py; extract/, resolve/, checkers/, verdict/, report/, sources/
Who must know (lanes): all lanes

### 12:55 · claude-verdict-1 · D8: verdict engine needs a `verdict:` block in config/rules.yaml (ACTION for claude-core and the finance partner)
Change: verdict/engine.py reads three new keys with no code fallback (AGENTS.md: thresholds live only in rules.yaml). claude-core: add them to config/rules.yaml and to `REQUIRED_KEYS` in core/config.py. Finance partner: set the real values (T05). Placeholder values the tests use:
```yaml
verdict:
  supported_margin: 0.5   # diff <= 0.5 * tolerance = clearly close match (high confidence)
  strong_margin: 2.0      # diff >= 2.0 * tolerance = clearly wrong number (high confidence)
  fresh_days: 90          # record within 90 days of the claim's date = fresh
```
Also: `decide(claim, result, rules)` has no access to the run (D7), so checkers must put `reference_date` (claim.as_of if ISO, else the deck date) and `reference_date_source` (copy of run input deck_date_source) into `CheckResult.observed`. Seniority order for title checks is the key order of `title_levels` in rules.yaml (first = most senior). Full list of `observed` keys per claim type: verdict/DESIGN.md.
Why: wrong SUPPORTED/CONTRADICTED costs more than CANNOT_VERIFY, so confidence needs margins; those margins are judgement values a human must be able to change live.
Files affected: config/rules.yaml, core/config.py (claude-core); verdict/engine.py (reads the keys); checkers/* (set the observed keys).
Who must know (lanes): claude-core (until the keys exist `decide()` raises ValueError, so a real run stops at its first verdict), finance partner, codex-a, ag-b

### 14:10 · claude-verdict-1 (on the user's word) · D9: the Windows laptop owns lane claude-verdict
Change: lane claude-verdict (verdict/, report/, docs/reviews/, T13, T15, T20, T27) is worked only from the Windows laptop, in its worktree folder `dc-claude-verdict` on branch `lane/claude-verdict`. The Mac laptop must not start a claude-verdict session; if it needs something from this lane it writes a line in HANDOFF.md or TASKS.md. Both laptops use the same Claude account but different OneDrive accounts, so they share nothing except origin: coordinate through git files only, not through session messages (those stay on one machine). Labels in TASKS.md and HANDOFF.md are `<lane>@<laptop>` (this lane: `claude-verdict@win`). Which laptop owns the other lanes is not decided here; the user decides and adds a line below.
Why: two sessions on one lane would edit the same files from two clones; the shared account gives no way to tell sessions apart.
Files affected: none in code. TASKS.md and HANDOFF.md labels from now on.
Who must know (lanes): all lanes, both humans

### 14:25 · claude-verdict@win · D10: correction to D9, the two laptops use two different Claude accounts
Change: D9 said both laptops use the same Claude account. That is wrong: there are two Claude accounts, one per laptop (as in PLAN.md section 5), and different OneDrive accounts. Everything else in D9 stands: this Windows laptop owns lane claude-verdict; the laptops share only origin; coordinate through TASKS.md, HANDOFF.md and DECISIONS.md; labels are `<lane>@<laptop>`. Consequence: each laptop has its own usage limit, so each account writes its own HANDOFF entry before its own limit.
Why: the user clarified after D9 was pushed. DECISIONS is append-only, so this is a new entry instead of an edit.
Files affected: none in code.
Who must know (lanes): all lanes, both humans

### 15:05 · claude-verdict@win · D12: entities shape from resolve (T10) and the three sources.crust functions it calls
Change: `resolve/entities.py: run(ctx, claims)` returns `{"company": E, "founders": [E, ...]}` where E has `id`, `identity` (confirmed | unclear | not_found), `identity_signals` (int), `confidence` (high: signals > identity.min_signals, medium: equal, low: fewer), `signals` (codes), `reason` (code or null), `call_id` (ledger id of the source call). Founder entries also have `name` (as written in the deck, or null) and `profile_url`. No raw payloads and no contact fields. Company signals: `domain` (exact match on primary or alias domain), `name` (deck company name equals provider name after legal suffixes are dropped), `founder` (a deck founder is in the company's founder list). Person signals: `profile_url` (requested URL returned), `name` (deck name equals provider name, token set, no fuzzy score), `employer` (a role at the confirmed company id), `company_founder_list`. A person or company is `confirmed` only with at least `identity.min_signals` signals; a namesake without the company link never qualifies; two qualifying candidates are `unclear`. A founder is searched only when the company is confirmed. Source errors (limit, timeout, failure) are not caught; the runner stops the run in state `extracted` and a resume repeats the stage.
codex-a (T08) must provide in `sources/crust.py`, each returning `(payload | None, ledger call_id | None)` and doing `limits.ensure_within(ctx)` plus a ledger row per call:
  `get_company(ctx, domain)` (exact domain match), `get_people(ctx, profile_urls: list[str])` (ONE batched call), `search_people(ctx, name: str, company_id: str)` (name plus employer id).
Payload shapes read: `matches[].company_data` / `matches[].person_data` / `profiles[]` as in docs/crustdata_fields.md; ids `crustdata_company_id`, `crustdata_person_id`; they are not verified against a live response yet.
Checkers find a founder with `resolve.names.find_founder(ctx.entities, claim.subject)`.
Note: checkers/_common.py cites "D11" for the get_company signature, but no D11 exists in the repo yet; this entry is the written source for all three signatures.
Why: checkers and the verdict engine need one shape, and the namesake case must end in `unclear`, never a guess.
Files affected: resolve/, sources/crust.py (codex-a), checkers/ (read `ctx.entities`), verdict (identity keys unchanged).
Who must know (lanes): codex-a, ag-b, claude-core

### 15:20 · human (written by harshit on the merger's word) · D3: request and result format (Investing track, 2.2 The Diligence Desk)
Change: the problem statement and builder handbook give no fixed Investing I/O format, so this is our own; `io/adapter.py` `from_kit()` / `to_kit()` are the only places to change if the organizers publish one.
Input (one request, JSON):
```json
{ "request": "<customer's words>", "deck_path": "deck.pdf",
  "company_domain": "example.in", "deck_date": "YYYY-MM-DD or null",
  "founder_urls": ["https://..."] }
```
`deck_date` is the "as of" date. When null, extract uses PDF metadata and sets `deck_date_source = "pdf_metadata"` (confidence capped at medium).
Output (one report, JSON + Markdown):
```
{ "run_id", "company": {name, domain, identity, source}, "as_of": deck_date,
  "claims": [ { "slide", "quote", "type", "claimed_value",
                "verdict": SUPPORTED|CONTRADICTED|NOT_COMPARABLE|CANNOT_VERIFY|HELD,
                "reason_code", "explanation", "confidence",
                "missing": "what would settle it" | null,
                "sources": [ { "url_or_endpoint", "field_or_quote", "value",
                               "record_date", "retrieved_at" } ] } ],
  "red_flags", "founder_questions", "evidence_requests",
  "ledger": { "calls", "credits", "cost_inr", "seconds" },
  "founder_email": { "status": pending|approved|sent, "recipient": test inbox } }
```
Claim field list and order come from rules.yaml `output.fields` (hour-3 changes land there).
Rule from the handbook ("calls replayed from a past date, no fact from after that date"): evidence whose record_date is after as_of must not support or contradict a claim. It is excluded or NOT_COMPARABLE.
Implementation notes (claude-core): `output.fields` keeps report/builder.py names and gains `value`; `to_kit()` renames label -> verdict, value -> claimed_value, source locator -> url_or_endpoint, and leaves any other field name as is. `ledger.seconds` = total duration of external calls. `company` and `founder_email` are passed to `to_kit()` by the caller (resolution entities, the run's Action), since the report does not hold them. The customer's `request` text is read and checked but not stored (storing it is a schema change).
Why: no published format; one adapter keeps a later format change to two functions.
Files affected: io/adapter.py, config/rules.yaml (output.fields), verdict/ (date rule), report/, ui/, checkers/
Who must know (lanes): claude-verdict (report/ builds this; verdict must apply the after-as_of rule), ag (UI shows it), all checkers

### 15:40 · human (merger, answering claude-verdict) · D13: D3 stays strict; snapshot fields use their dated history point
Change: D3 is unchanged: no record dated after the reference date (claim.as_of, else the deck date) may support or contradict a claim. For fields whose snapshot value has only a refresh date (headcount total, growth), checkers must NOT use the snapshot. They read the dated history instead and pick the latest point dated on or before the reference date:
- team_size: `headcount.timeseries[]` point (`employee_count`, its own date) -> observed `headcount`, `record_date` = that point's date, Evidence field_or_quote `headcount.timeseries[<date>].employee_count`.
- team_growth: two timeseries points on or before the reference date, spanning the claimed window; growth computed by code from them.
- funding: rounds already carry dates (excluded_later_rounds), unchanged.
- No history point on or before the reference date -> no headcount evidence -> CANNOT_VERIFY `no_evidence`, `missing` = "a headcount record dated on or before <reference date>". The snapshot `headcount.total` and `updated_at` are never used as a dated fact.
Neither option 1 (past decks never get a headcount verdict) nor option 2 (refresh date as as-of) is taken: option 2 would date a number by when Crustdata refreshed it, which breaks "every fact has the record's own date".
Why: the handbook's Investing brief asks for calls "replayed from a past date ... with no fact from after that date", and hidden test cases use events after 1 September 2026, so decks will be dated in the past. Crustdata documents dated headcount points (docs/crustdata_fields.md: latest timeseries point dated 2026-11-02), so strict D3 still yields verdicts. The verdict engine needs no change.
Files affected: checkers/team_size.py, checkers/team_growth.py (ag-b); tests/checkers; verdict/DESIGN.md section 3.1 wording (claude-verdict).
Who must know (lanes): ag-b, claude-verdict, codex-a (get_company must request the headcount section including timeseries)

### 16:20 · claude-verdict@win · D14: record age limit per claim type (ACTION for the merger / claude-core: add one key to rules.yaml)
Change: verdict/engine.py now reads the age limit for the staleness row from `tolerances.<claim type>.max_record_age_days` when that key exists, and from the global `tolerances.max_record_age_days` (365) otherwise. D3 is unchanged: a record dated after the reference date is NOT_COMPARABLE `record_after_as_of` whatever the limit. Reason: a funding round is an event, and its date is when it happened, not when we looked. Locus (company 7403) has its last dated round on 2021-06-02; with a 365-day limit every funding claim in a 2026 deck would be `stale_record`.
Key to add (merger places it, finance partner confirms the value), under `tolerances.funding` in config/rules.yaml:
```yaml
  funding:
    tolerance_pct: 10
    max_record_age_days: 3650   # PLACEHOLDER. A funding round up to 10 years before the deck date still counts
```
Until it is added, funding records older than 365 days stay `stale_record` (safe default, no wrong verdict). Tests inject the key into the rules fixture.
Checker note for ag-b (funding): `observed.record_date` = date of the newest dated round used (here the Series C, 2021-06-02); `undated_rounds` = rounds with no date (here 6 of 7); `total_raised` stays the provider total. With undated rounds the engine says SUPPORTED low confidence (`within_tolerance_undated_rounds`) when the total matches, never high.
Why: the age limit made sense for snapshots, not for dated events.
Files affected: verdict/engine.py, verdict/DESIGN.md (rows 8 and section 6), config/rules.yaml (merger), docs/LIVE_FIX_MAP.md
Who must know (lanes): claude-core / merger (rules.yaml), ag-b, finance partner

### 13:25 · yash · D11: Crustdata company lookup and call provenance
Change: `sources.crust.get_company(ctx, domain) -> tuple[dict, str]` returns the unique exact-domain company record and its ledger call ID. The record includes `retrieved_at` (original fetch time). An empty match list returns an empty record. Multiple exact matches raise a source error because current checkers cannot compare ambiguous records. Checkers should use the record's `retrieved_at` for Evidence.
Why: all callers share one short-lived company result per run and domain. The authenticated account endpoint supplies current pacing and credit rates, without new rules.yaml keys. With no receipt, charge estimates use credits per returned record. A 429 or 5xx gets one retry after pacing and any Retry-After delay, subject to D7 limits. Every attempt, including the metadata request, produces its own ledger row.
Files affected: sources/crust.py, docs/crustdata_fields.md, tests/sources/
Who must know (lanes): codex-a, ag-b, claude-core

### 15:55 · claude-verdict (harshit's account, at the merger session's request) · D15: verdict rules for hiring, traction, company_fact, prior_exit, team_growth, competition (T29)
Change: verdict/engine.py routes six more claim types to new rule files (verdict/hiring.py, traction.py, company_fact.py, prior_exit.py, team_growth.py; competition inline). Rules are cautious: hiring, HQ, prior_exit and team_growth never return CONTRADICTED; traction CONTRADICTS only at >= strong_margin x tolerance and never above medium; company_fact founded year CONTRADICTS (medium) only beyond `year_gap_cannot_verify`; competition is always CANNOT_VERIFY `competition_not_judged`. prior_exit stops at CANNOT_VERIFY `prior_company_not_checked` unless the checker sets `observed.prior_company_checked = True` (today it fetches the deck's own company). team_growth is NOT_COMPARABLE `period_mismatch` unless the checker exposes `observed.baseline_date` with a ~1-year window. New rules.yaml keys (PLACEHOLDER, finance partner sets them; read inside the rules, not in REQUIRED_KEYS): `tolerances.company_fact.year_gap_cannot_verify: 1`, `tolerances.team_growth.window_tolerance_days: 45`. New reason codes: see verdict/DESIGN.md section 4.
Why: before this, every claim of these types ended CANNOT_VERIFY `unsupported_metric`; the pass mark (zero wrong SUPPORTED/CONTRADICTED) means new decided paths must lean to CANNOT_VERIFY where the source can be incomplete or the wording ambiguous.
Files affected: verdict/*.py, config/rules.yaml, verdict/DESIGN.md, docs/LIVE_FIX_MAP.md, tests/verdict/test_t29_rules.py
Who must know (lanes): codex-a (prior_exit checker: fetch the prior company, set the flag), ag-b (team_growth baseline_date; hiring unit = role family), report/ (new reason codes; templates fall back to `default`), finance partner (two new keys)

### 15:35 · harshit (merger) · D16: web source for market_size and customer claims (Crustdata Web APIs)
Change: add `sources/web.py` with `search(ctx, query, *, sources, site, location, end_date)` and `fetch(ctx, urls)`, each returning `(data, ledger call_id)`. They call Crustdata `POST /web/search/live` and `POST /web/enrich/live` with the same key, ledger (Provider.CRUSTDATA, credits from `X-Credits-Used`) and limits as `get_company`. Add `sources/pages.py` (`page_text`, `published_date`: code reads the page's own publish date from its HTML) and `extract/quotes.py` (`pick_quote`: the LLM picks one sentence and code checks it is verbatim on the page; `parse_amount`: code reads number and currency, including lakh/crore). `checkers/market_size.py` is rewritten and `checkers/customer.py` is new; the `observed` keys are in docs/WEB_SOURCE.md section 3. market_size sets `identity: "not_applicable"`, and the engine skips the two-signal check for that type only. New verdict rules: market_size SUPPORTED when one estimate is within tolerance, CONTRADICTED only when `min_agreeing_sources` estimates from different domains agree with each other and not with the claim (max medium); customer SUPPORTED only on an independent (non-company-domain) mention, otherwise CANNOT_VERIFY `self_reported_only`, never CONTRADICTED.
Why: search results carry no date, so a web fact is only admissible with a date code read from the page (D3). One provider keeps every call in one ledger and one key. Slides 6 and 7 of Deck A are HELD today because neither piece exists.
Config: new `web:` section and `tolerances.market_size.{min_agreeing_sources, max_record_age_days}`, `tolerances.customer.max_record_age_days` (all PLACEHOLDER).
Tasks: T30 (web client), T31 (pages + quotes), T32 (checkers), T33 (verdict rules); see docs/WEB_SOURCE.md section 5.

### 16:25 · harshit (merger, on the user's word) · D17: guarded fallback to undated records
Change: D3 and D13 stay the default: a dated record on or before the reference date is always preferred. When a checker finds **no** dated record but does find an undated one (a snapshot field with no record date, such as `hiring.openings_count`, or a web page with no machine-readable publish date), the engine may decide from the undated record if BOTH of these hold:
1. `verdict.undated_fallback` is true; and
2. the reference date (claim.as_of, else the deck date) is no more than `verdict.undated_max_deck_age_days` (default 90) before the evidence's `retrieved_at`, and not after it. The deck is recent, so "the data now" is close to "the data on the deck date".
Then the verdict's confidence is capped at **low**, its `reason_code` gets the suffix `_undated` (e.g. `within_tolerance_undated`, `outside_tolerance_undated`), and its explanation starts: "No dated record was found; this uses an undated source retrieved on <date>." The report marks the row as an undated source. If either condition fails, the result stays CANNOT_VERIFY `missing_record_date`, and `missing` says why (deck older than the limit).
Checkers keep undated items and mark them, without dropping them: Evidence `record_date=None`, `observed.record_date=None`, and for web items `published_date: None`. They use them only when no dated item was accepted.
Why: the user wants every claim the data can speak to answered, and stated plainly when the answer rests on undated data. The age guard keeps the handbook rule ("no fact from after the deck date") for past-dated test decks: undated data is "now" data, so it is only used when the deck is recent.
Config: `verdict.undated_fallback`, `verdict.undated_max_deck_age_days` (PLACEHOLDER).
Tasks: T34 (engine + report, claude-verdict), T35 (checkers keep undated items).

### 16:25 · harshit (merger, on the user's word) · D18: build founder lookups now (D12), merger reassigns the sources lane
Change: build `get_people(ctx, profile_urls)` (one batched `POST /person/enrich`, 1 credit per person) and `search_people(ctx, name, company_id)` (`POST /person/search`, filtered by name plus employer id, about 0.23 credits per result) in `sources/crust.py`, exactly as D12 specifies: each returns `(payload | None, call_id | None)`, with limits, a ledger row, a timeout, the same 429 retry, a per-run cache, and contact fields (emails, phones) dropped recursively at ingest. Then `checkers/founder_background.py` reads the **resolved** founder's own person record (experience: employer, title, start and end dates) instead of the company payload. Identity comes from `ctx.entities` founders (two-signal rule, D12), not from the company identity. codex-a has not touched this since D12, so the merger gives `sources/` person functions, `resolve/payloads.py` (person shapes) and `checkers/founder_background.py` to task T36.
Why: founder background is the claim type investors care about most (materiality 5), and today every founder claim is CANNOT_VERIFY or HELD.
Tasks: T36.
