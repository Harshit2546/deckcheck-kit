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
