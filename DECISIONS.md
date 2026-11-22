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
