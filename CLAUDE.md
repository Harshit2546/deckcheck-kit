# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Read `AGENTS.md` first and follow it exactly. It is the single rule file for every
account on this project (Claude, Codex, Antigravity). Then read `PLAN.md`, `TASKS.md`
and the last 3 entries of `HANDOFF.md`. This file only adds what Claude needs on top.

## Claude's lanes (two Claude Pro accounts, see PLAN.md section 5)

- **claude-core** (branch `lane/claude-core`): `core/`, `io/adapter.py`, `actions/`.
  Tasks T01, T07, T19 and the kill drills.
- **claude-verdict** (branch `lane/claude-verdict`): `verdict/`, `report/`. Tasks T13,
  T15, T20 (hour-3 change) and T27 (merge reviews).

Find your lane from the task you claimed or the last HANDOFF entry. Edit only your lane's
folders; the other Claude lane and the other lanes (`sources/`, `extract/`, `resolve/`,
`checkers/`, `ui/`) are read-only, read their HANDOFF entries instead. If the other Claude
account hit its limit, continue its lane from its HANDOFF entry. Claude budget is still
limited: hard reasoning work only (no UI, no boilerplate), and write the HANDOFF entry
before the limit hits.

## Workflow (details in AGENTS.md sections 1, 4, 5)

- Claim one `todo` task in `TASKS.md` and commit that alone (`[claude-core] tasks: claim
  T07`) before coding. Only a human merges to `main`.
- Commit format `[lane] module: what changed`, small and often. No force-push, no
  amending or rebasing pushed commits.
- Stop and write the `HANDOFF.md` entry (template in that file, append at the bottom),
  update `TASKS.md`, then commit `[lane] handoff: <task id> <line>` when the task is
  done, after ~45 minutes, or when context or usage is getting long.
- Unsure about the kickoff-kit format or a verdict rule: do not guess; put it under
  "Open questions" in the HANDOFF entry.

## Rules that are easy to violate while coding

- No hard-coded answers or mock data outside `tests/`. Every verdict comes from a live call
  in the same run; every Evidence row needs source, exact field/quote, record date and
  `retrieved_at`.
- The LLM never decides numbers, dates, comparisons or verdicts; it only extracts claims,
  picks exact quotes and writes explanations. `verdict/engine.py` decides.
- Every external call, including failed ones, writes a ledger row.
- Python 3.11, type hints everywhere, models only in `core/models.py`, a 3-5 line module
  docstring (what it does, who calls it, what it calls), log via `core/log.py` (no `print`).
- Founder email goes only to the test inbox and stays `pending` until a human approves.

## Current state

As of the T00 handoff the repo holds only planning docs; no code exists yet. The first
Claude task is T01 (skeleton). Check `TASKS.md` and `HANDOFF.md` for the real state before
trusting anything below that describes code.

## Commands (planned in PLAN.md / TASKS.md; verify once T01 lands)

- Start a run: `python cli.py run ...` (`python cli.py run --help` is T01's done check)
- Resume after a kill: `python cli.py resume <run_id>`
- All tests (must pass before a human merges to `main`): `pytest -q`
- One test file: `pytest tests/checkers/test_funding.py -q`; one test: add `-k <name>`
- Eval against the answer key: `python tests/eval/run_eval.py`
- UI: `streamlit run ui/app.py`

## Architecture in one pass

Pipeline: `io/adapter` (kickoff-kit format to internal) -> `extract` (PDF slide text, LLM
claims, code confirms each quote is on its slide) -> `resolve` (company by domain, founders
via two-signal identity rule) -> `checkers/<claim_type>.py` (fetch + normalise, return
`CheckResult`) -> `verdict/engine.py` (label chosen by code from `config/rules.yaml`) ->
`report/` -> `actions/` (founder email, human approval, exactly-once send).

Things that span files and are easy to break:

- **Contracts** (`Claim`, `Evidence`, `Verdict`, `LedgerEntry`, `Action`, the checker
  interface) are defined in PLAN.md section 3 and live only in `core/models.py`; the DB
  schema lives in `core/store.py`. Changing either needs a `DECISIONS.md` entry first.
- **Checkpointing:** run states `created -> extracted -> resolved -> checking -> decided ->
  reported -> done`, plus per-claim `pending -> checked -> decided`, all in SQLite. Resume
  skips finished work, so no external call may happen outside a checkpointed step.
- **Limits:** the runner checks the ledger total against `config/rules.yaml` limits before
  every external call. Hitting a limit, a timeout or an error makes a claim `HELD`
  (never `CANNOT_VERIFY`).
- **Exactly-once send:** `approved -> sending` in one transaction, insert into `inbox` with
  `UNIQUE(idempotency_key)`, then `sent`. On restart a `sending` row whose key is already
  in `inbox` becomes `sent`. Never add a plain retry around the send.
- **Config, not code:** tolerances, title levels, materiality weights, limits and output
  fields belong in `config/rules.yaml` (owned by the finance partner). When you add
  something a human may need to change live, add a line to `docs/LIVE_FIX_MAP.md`.
