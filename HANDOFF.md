# HANDOFF.md — append-only log between accounts

Newest entry at the BOTTOM. Never edit or delete an old entry. Copy the template,
fill every field, commit with `[lane] handoff: <task id> <one line>`.

## Template

```
### <HH:MM> · <account label, e.g. codex-2> · lane <claude-core|claude-verdict|codex-a|ag-b|ag|human> · task <T-id>

Status: done | in-progress (~__%) | blocked
Done this session:
- <file>: <what it does now>
In progress / exact next step:
- <the very next thing to do, specific enough to start in 1 minute>
How to run / test:
- <exact command, e.g. pytest tests/checkers/test_funding.py -q>
Known bugs or shortcuts taken:
- <anything fragile, anything marked TODO>
Decisions made (also in DECISIONS.md if they change behaviour):
- <decision>
Open questions for a human:
- <question>
Credits / tokens used this session (rough): <n>
```

## Log

### 11:00 · human · lane human · task T00

Status: done
Done this session:
- Added AGENTS.md, CLAUDE.md, GEMINI.md, PLAN.md, TASKS.md, HANDOFF.md, DECISIONS.md.
In progress / exact next step:
- Claude: T01 skeleton (core/models.py, core/store.py, config/rules.yaml, cli.py).
How to run / test:
- n/a yet
Known bugs or shortcuts taken:
- none
Decisions made:
- Stack: Python 3.11, Streamlit, SQLite, Crustdata API + web fetch.
Open questions for a human:
- Exact input/output format from the kickoff kit for the Investing request. Map it in io/adapter.py.
Credits / tokens used this session (rough): 0

### 11:50 · claude-core-1 · lane claude-core · task T01

Status: done
Done this session:
- core/models.py: every contract (Run, RunInput, Claim, Evidence, CheckResult, Verdict, LedgerEntry, Action, InboxMessage) + enums, make_idempotency_key(), now_iso(). Stdlib dataclasses.
- core/store.py: SQLite schema (runs, claims, ledger, evidence, check_results, verdicts, actions, inbox, reports) created on connect(); helpers per table; save_check_result()/save_verdict() are atomic per-claim checkpoints; ledger_totals(); ledger+inbox append-only by trigger; actions and inbox UNIQUE(idempotency_key).
- core/ledger.py: record() writes one ledger row with cost_inr from rules.yaml `costs`; new_call_id().
- core/config.py: load_rules() fails fast on missing REQUIRED_KEYS; rule(rules, "a.b").
- core/log.py: log_step()/log_error(), UTC, stderr + logs/deckcheck.log (DECKCHECK_LOG_DIR overrides).
- core/runner.py: stub start()/resume() (signatures are the contract for T07).
- cli.py: `run --deck --domain [--deck-date] [--founder-url]`, `resume <run_id>`, global --db/--rules.
- config/rules.yaml: full schema, every value PLACEHOLDER for the finance partner.
- kit_io/adapter.py: from_kit()/to_kit() stubs raising NotImplementedError until D3.
- tests/core/: 12 tests (tables, round trips, rollback, append-only, unique keys, cli).
In progress / exact next step:
- claude-core: claim T07, then write core/runner.py steps: extract -> resolve -> per-claim check (skip claims already `checked`) -> verdict -> report, checking store.ledger_totals() and elapsed time since runs.started_at against rules limits before each external call.
How to run / test:
- python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
- .venv/bin/python -m pytest -q
- .venv/bin/python cli.py run --help
Known bugs or shortcuts taken:
- runner is a stub: `run` creates the run row and logs; nothing else happens yet.
- rules.yaml values are placeholders (costs, limits, tolerances, title levels, materiality, test inbox).
- tests/conftest.py and pytest.ini are shared files added by claude-core; other lanes may add fixtures there.
Decisions made (also in DECISIONS.md if they change behaviour):
- D4: adapter is kit_io/adapter.py (a top-level io/ package cannot be imported).
- D5: extra models/tables (check_results, reports), evidence.call_id FK to ledger, append-only triggers, costs in rules.yaml.
Open questions for a human:
- PLAN.md, AGENT_PROMPTS.md and TASKS.md still say io/adapter.py; update them (human-owned) or tell lanes about D4.
- Finance partner: real rupee rates for a Crustdata credit and for the LLM model we use, plus limits.
- Merger: kickoff-kit format (D3) so kit_io/adapter.py can be filled.
Credits / tokens used this session (rough): 0 Crustdata credits; Claude tokens moderate
