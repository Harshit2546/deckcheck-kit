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
