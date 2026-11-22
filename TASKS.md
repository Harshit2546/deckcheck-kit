# TASKS.md — task board

Status: todo | in-progress (owner, % , next step) | blocked (why) | done.
Claim a task by writing your account label and committing (AGENTS.md section 1).
Lanes: claude-core, claude-verdict, codex-a, ag-b, ag, human (see PLAN.md section 5).

| ID | Lane | Task | Done when | Status |
|---|---|---|---|---|
| T00 | human | Add rule files to repo | AGENTS.md etc. on main | done |
| T01 | claude-core | Skeleton: core/models.py, core/store.py (all tables incl. inbox with UNIQUE key), core/log.py, config/rules.yaml schema, cli.py (run, resume), io/adapter.py stub | `python cli.py run --help` works; tables created | done (harshit) |
| T02 | codex-a | Probe Crustdata on Deck A company and founders; write fields we get into docs/crustdata_fields.md | doc lists endpoints, fields, credit cost per call | blocked (yash, Locus company probe recorded. Founder enrichment paused by the human.) |
| T03 | ag-b | extract/pdf.py: text per slide | test on Deck A passes | done |
| T04 | ag | ui/app.py shell: upload form, run list from DB | shows a run row | done (harshit) |
| T05 | human | Partner: Deck A (8 claims) + answer key; rules.yaml values | files in tests/decks/ | todo |
| T06 | human | Read kickoff kit; record Investing request input/output format in DECISIONS.md | D3 written | todo |
| T07 | claude-core | core/runner.py: state machine, per-claim checkpoints, resume, cost and time limits | kill mid-run then resume finishes with no duplicate calls | done (harshit) |
| T08 | codex-a | sources/crust.py: rate limit, backoff on 429/5xx, per-call timeout to HELD, ledger row per call, TTL cache | unit tests for 429, timeout, ledger | done (yash) |
| T09 | ag-b | extract/claims.py: LLM structured claims + quote-on-slide check | invented quote is rejected in test | done |
| T10 | claude-verdict | resolve/entities.py: company by domain, founders, two-signal rule, confidence | namesake fixture returns identity_unclear | done (claude-verdict@win: resolve/entities.py + 29 tests, namesake fixture gives unclear, company confirmed on the real Locus recording; founder lookups by URL or name still need get_people and search_people in sources/crust.py, D12) |
| T11 | ag-b | checkers: team_size, funding | tests pass | done |
| T12 | ag-b | checkers: founder_background | tests pass | done (yash) |
| T13 | claude-verdict | verdict/engine.py for founder, team_size, funding | Deck A matches answer key for those claims | done (claude-verdict@win: engine + D3, D13, D14 rules, 101+ verdict tests; waits only for tolerances.funding.max_record_age_days in rules.yaml, D14) |
| T14 | human | MILESTONE 1 at 12:45: Deck A end to end | report generated | todo |
| T15 | claude-verdict | report/: red flags by materiality, table, questions, evidence requests, kit-format JSON | output validates against kit format | done (claude-verdict@win: report/builder.py, render.py, question templates, 11 tests; kit-format output is io/adapter.py to_kit, claude-core, not re-checked by me) |
| T16 | codex-a / ag-b | checkers: prior_exit, company_fact (done by ag-b), customer (web quote verify) | tests pass | in-progress |
| T17 | ag-b | checkers: team_growth, hiring, traction, market_size, competition | tests pass | done |
| T18 | ag | UI: verdict detail with source link and date; approvals page; inbox; ledger view | click-through works | done (harshit) |
| T19 | claude-core | actions/: draft, approve, exactly-once send | kill between approve and send, restart, one inbox row | done (harshit) |
| T20 | claude-verdict | Hour-3 requirement change | DECISIONS entry + tests | todo (claude-verdict@win: waiting for the hour-3 requirement text) |
| T21 | claude-verdict | tests/eval/run_eval.py: accuracy vs answer key for decks A, B, C | prints per-claim pass/fail | in-progress (claude-verdict@win, 85%: tests/eval/run_eval.py offline for deck A works, 10 tests; todo: decks B and C files, one approved --live run) |
| T22 | human | MILESTONE 2 at 15:00: 3 decks, kill/resume, send once | all green | todo |
| T23 | ag | docs/ARCHITECTURE.md + diagram (components, data flow, data calls, approvals, retries, ledger) | in repo | todo |
| T24 | human | ETHICS.md, BUSINESS.md (measured cost per deck in rupees) | in repo | todo |
| T25 | ag + human | README: job, who pays, input, result, pass mark, data sources, how to run, credits | every claim in it is true | todo |
| T26 | human | Rehearse demo with kill, 3 live-fix drills, design question | done twice | todo |
| T27 | claude-verdict | Merge reviews before each human merge to main (12:15, 12:45, then every merge) | review notes in HANDOFF | in-progress (claude-verdict@win: reviews of ag-b and codex-a in docs/reviews/; repeat before each merge to main) |
