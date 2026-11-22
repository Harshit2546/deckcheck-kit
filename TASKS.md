# TASKS.md — task board

Status: todo | in-progress (owner, % , next step) | blocked (why) | done.
Claim a task by writing your account label and committing (AGENTS.md section 1).

| ID | Lane | Task | Done when | Status |
|---|---|---|---|---|
| T00 | human | Add rule files to repo | AGENTS.md etc. on main | done |
| T01 | claude | Skeleton: core/models.py, core/store.py (all tables incl. inbox with UNIQUE key), core/log.py, config/rules.yaml schema, cli.py (run, resume), io/adapter.py stub | `python cli.py run --help` works; tables created | todo |
| T02 | codex-a | Probe Crustdata on Deck A company and founders; write fields we get into docs/crustdata_fields.md | doc lists endpoints, fields, credit cost per call | todo |
| T03 | codex-b | extract/pdf.py: text per slide | test on Deck A passes | todo |
| T04 | ag | ui/app.py shell: upload form, run list from DB | shows a run row | todo |
| T05 | human | Partner: Deck A (8 claims) + answer key; rules.yaml values | files in tests/decks/ | todo |
| T06 | human | Read kickoff kit; record Investing request input/output format in DECISIONS.md | D2 written | todo |
| T07 | claude | core/runner.py: state machine, per-claim checkpoints, resume, cost and time limits | kill mid-run then resume finishes with no duplicate calls | todo |
| T08 | codex-a | sources/crust.py: rate limit, backoff on 429/5xx, per-call timeout to HELD, ledger row per call, TTL cache | unit tests for 429, timeout, ledger | todo |
| T09 | codex-b | extract/claims.py: LLM structured claims + quote-on-slide check | invented quote is rejected in test | todo |
| T10 | codex-a | resolve/entities.py: company by domain, founders, two-signal rule, confidence | namesake fixture returns identity_unclear | todo |
| T11 | codex-b | checkers: team_size, funding | tests pass | todo |
| T12 | codex-a | checkers: founder_background | tests pass | todo |
| T13 | claude | verdict/engine.py for founder, team_size, funding | Deck A matches answer key for those claims | todo |
| T14 | human | MILESTONE 1 at 12:45: Deck A end to end | report generated | todo |
| T15 | claude | report/: red flags by materiality, table, questions, evidence requests, kit-format JSON | output validates against kit format | todo |
| T16 | codex-a | checkers: prior_exit, company_fact, customer (web quote verify) | tests pass | todo |
| T17 | codex-b | checkers: team_growth, hiring, traction, market_size, competition | tests pass | todo |
| T18 | ag | UI: verdict detail with source link and date; approvals page; inbox; ledger view | click-through works | todo |
| T19 | claude | actions/: draft, approve, exactly-once send | kill between approve and send, restart, one inbox row | todo |
| T20 | claude | Hour-3 requirement change | DECISIONS entry + tests | todo |
| T21 | ag | tests/eval/run_eval.py: accuracy vs answer key for decks A, B, C | prints per-claim pass/fail | todo |
| T22 | human | MILESTONE 2 at 15:00: 3 decks, kill/resume, send once | all green | todo |
| T23 | ag | docs/ARCHITECTURE.md + diagram (components, data flow, data calls, approvals, retries, ledger) | in repo | todo |
| T24 | human | ETHICS.md, BUSINESS.md (measured cost per deck in rupees) | in repo | todo |
| T25 | ag + human | README: job, who pays, input, result, pass mark, data sources, how to run, credits | every claim in it is true | todo |
| T26 | human | Rehearse demo with kill, 3 live-fix drills, design question | done twice | todo |
