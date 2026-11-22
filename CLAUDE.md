# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Read `AGENTS.md` first and follow it exactly. It is the single rule file for every
account on this project (Claude, Codex, Antigravity). Then read `PLAN.md`, `TASKS.md`
and the last 3 entries of `HANDOFF.md`. This file only adds what Claude needs on top.

## Claude's lane

`core/`, `io/adapter.py`, `verdict/`, `report/`, `actions/`, plus merge reviews and the
hour-3 requirement change. Do not edit other lanes' folders (`sources/`, `extract/`,
`resolve/`, `checkers/`, `ui/`); read their HANDOFF entries instead.
Claude Pro limits are the team's scarcest budget: do the hard reasoning work only (no UI,
no boilerplate), and write the HANDOFF entry before the limit hits.

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
