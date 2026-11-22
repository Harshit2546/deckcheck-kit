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

### 11:58 · claude-verdict-1 · lane claude-verdict · task T13

Status: in-progress (~20%)
Done this session:
- verdict/DESIGN.md: engine interface (`decide`, `held_verdict`), the shared order of checks, the `observed` keys checkers must fill for founder_background, team_size and funding, label/reason_code/confidence tables, the rules.yaml keys read, and asks for the other lanes. Written against the real T01 contracts on origin/lane/claude-core (dataclasses, `rules` as a dict).
- TASKS.md: T13 claimed.
In progress / exact next step:
- core/ is not on main yet. When it lands: `git merge origin/main` into lane/claude-verdict, then write verdict/engine.py per DESIGN.md and fixture tests in tests/verdict/ (one test per row of the tables).
- codex-a and ag-b: read verdict/DESIGN.md sections 2, 3 and 5 before writing checkers.
How to run / test:
- n/a yet (design only). Later: pytest tests/verdict -q
Known bugs or shortcuts taken:
- DESIGN.md is a draft; the three open questions below may change a rule.
- The engine will fall back to default margins (supported_margin 0.5, strong_margin 2.0, fresh_days 90) until the `verdict:` block exists in rules.yaml.
Decisions made (also in DECISIONS.md if they change behaviour):
- A funding total LOWER than the deck is CANNOT_VERIFY (`source_may_be_incomplete`), never CONTRADICTED. Absence of an employer or investor is never a contradiction. Team-size contradictions are at most medium confidence.
- The engine never converts currencies; a unit mismatch is NOT_COMPARABLE.
Open questions for a human:
- Finance partner: (1) meaning of `tolerances.founder_background.min_title_level` (my reading is in DESIGN.md section 6); (2) is `tolerances.max_record_age_days` global; (3) confirm the cautious funding rule above.
- claude-core (partner): please add the `verdict:` block to config/rules.yaml and REQUIRED_KEYS (DESIGN.md section 6).
- Docs to fix (human-owned; the coordinating session will do it): PLAN.md, TASKS.md and docs/AGENT_PROMPTS.md still say io/adapter.py; D4 moved it to kit_io/adapter.py.
Credits / tokens used this session (rough): 0 Crustdata credits; Claude tokens moderate

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

### 12:05 · harshit · lane claude-core · task T01

Status: done (supersedes the 11:50 entry where it differs)
Done this session:
- io/adapter.py: from_kit() maps a kit request to RunInput with a provisional field map (TODO to D3); to_kit() passes the report through (TODO to D3). Load it with core/adapter_loader.load_adapter().
- config/rules.yaml: tolerances now have one entry for every claim type; all values PLACEHOLDER for the finance partner.
- kit_io/ deleted (D6 withdraws D4). pytest.ini and tests/conftest.py removed; test setup is tests/core/conftest.py. CLAUDE.md and .gitignore are back to main's version.
- main's T01 (8761021) was reverted on main by its author (8f21500); this branch's T01 is the one to merge.
In progress / exact next step:
- T07: core/runner.py.
How to run / test:
- python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
- .venv/bin/pytest -q   (14 tests)
- .venv/bin/python cli.py run --help
Known bugs or shortcuts taken:
- runner is still a stub until T07; rules.yaml values are placeholders.
Decisions made (also in DECISIONS.md if they change behaviour):
- D6: adapter at io/adapter.py, loaded by file path.
Open questions for a human:
- ag-b and codex-a branches start from the reverted Pydantic T01; after this branch is merged, pull main and use core/models.py (dataclasses).
- Merger: kit format (D3) for io/adapter.py. Finance partner: rules.yaml values.
Credits / tokens used this session (rough): 0 Crustdata credits

### 12:40 · harshit · lane claude-core · task T07

Status: done
Done this session:
- core/runner.py: start()/resume() walk created -> extracted -> resolved -> checking -> decided -> reported -> done. Each step saves its output and the new state in one transaction; each claim is checkpointed (checked, then decided), so resume skips finished claims. Stages are imported by name from STAGES (signatures in D7); tests inject fakes.
- core/limits.py: limit_reason() / ensure_within() compare ledger cost, credits and elapsed time since runs.started_at with rules limits; LimitExceeded.
- core/models.py: RunContext, HeldReason. core/store.py: resolutions table + save/get_resolution.
- cli.py: exit 0 = done, 1 = not finished (waiting for a stage or failed; see runs.error), 2 = bad input.
- tests/core/test_runner.py: 9 tests incl. a real `os._exit(137)` kill in a child process, then resume: one ledger call per claim, one action.
In progress / exact next step:
- T19: claim it, then actions/email.py draft() (pending founder email to rules actions.test_inbox), approve/reject, and the exactly-once send (approved -> sending -> inbox UNIQUE key -> sent; restart reconciles `sending`).
How to run / test:
- .venv/bin/pytest -q   (24 tests)
- .venv/bin/pytest tests/core/test_runner.py -q -k kill
Known bugs or shortcuts taken:
- A claim killed in the middle of its check re-runs on resume, so calls it made before the kill happen again (ledger shows both). Finished claims never repeat.
- max_seconds counts from the first start, including time the process was dead; a long pause before resume makes remaining claims HELD (time).
- Until extract/ is merged, `cli.py run` creates the run and stops with exit 1 ("extract.claims is not built yet").
Decisions made (also in DECISIONS.md if they change behaviour):
- D7: stage signatures, HeldReason values, ensure_within() before every external call, resolutions table.
Open questions for a human:
- Tell every lane about D7 (their function names and signatures).
- report lane: confirm module name report/builder.py, or tell claude-core to change STAGES.
Credits / tokens used this session (rough): 0 Crustdata credits

### 12:58 · claude-verdict-1 · lane claude-verdict · task T13

Status: in-progress (~85%; code done, waiting on D8 keys)
Done this session:
- Merged origin/lane/claude-core (T01, T07) into lane/claude-verdict; HANDOFF.md conflict resolved by keeping both entries.
- verdict/engine.py: `decide(claim, result, rules)` (D7 signature), `held_verdict()`, `check_rules()`. Shared order of checks, no LLM, no clock, no code defaults (every threshold via core.config.rule; missing key raises ValueError naming all of them).
- verdict/common.py, team_size.py, funding.py, founder.py: the metric rules from verdict/DESIGN.md section 3 (team_size headcount; funding total_raised, round_amount, investor; founder past_employer, title, tenure_years).
- tests/verdict/: 64 tests, one per row of the order table and per metric row (hand-built CheckResult fixtures in tests/verdict/fakes.py). `pytest -q` from the worktree root: 89 passed (25 core + 64 verdict).
- verdict/DESIGN.md v2 (matches the code), DECISIONS D8, docs/LIVE_FIX_MAP.md lines.
In progress / exact next step:
- claude-core: add the `verdict:` block (supported_margin, strong_margin, fresh_days) to config/rules.yaml and REQUIRED_KEYS (D8). UNTIL THEN a real run raises ValueError at its first decide() call; the tests inject the block.
- claude-verdict: T15 report/builder.py (`build(conn, rules, run_id) -> (dict, str)` per D7).
- codex-a / ag-b: checkers must put `reference_date`, `reference_date_source`, `record_date`, `identity`, `identity_signals` and the per-type keys into CheckResult.observed (verdict/DESIGN.md sections 2, 3, 5; D8).
How to run / test:
- cd dc-claude-verdict && python -m pytest tests/verdict -q   (all: python -m pytest -q)
Known bugs or shortcuts taken:
- Explanations are fixed templates built from the evidence (no LLM wording yet).
- team_size accepts only metric `headcount` (or empty); other metrics are CANNOT_VERIFY `unsupported_metric`. Tell ag-b to emit `headcount`.
- Funding claim.value must be absolute major units and claim.unit an ISO currency (extract lane); no currency conversion.
Decisions made (also in DECISIONS.md if they change behaviour):
- D8 (above). A funding total lower than the deck is CANNOT_VERIFY; a missing employer or investor is never a contradiction; headcount contradictions are at most medium confidence.
Open questions for a human:
- Finance partner: min_title_level meaning, max_record_age_days global, cautious funding rule (see DESIGN.md section 6), and real values for the three verdict keys.
- PLAN.md, TASKS.md, docs/AGENT_PROMPTS.md still say io/adapter.py in places (D6 restored io/adapter.py, so check which doc is right).
Credits / tokens used this session (rough): 0 Crustdata credits; Claude tokens moderate

### 13:20 · claude-verdict-1 · lane claude-verdict · task T15

Status: in-progress (~80%; code and tests done, kit-format JSON waits for D3)
Done this session:
- report/builder.py: `build(conn, rules, run_id) -> (dict, str)` (D7 signature), read-only on the DB. JSON has run, generated_at, summary (counts by label + run-level flags), red_flags (CONTRADICTED only, ordered by rules.yaml materiality, then confidence, then slide), claims (columns = rules.yaml `output.fields`), founder_questions, evidence_requests (CANNOT_VERIFY and NOT_COMPARABLE), held (internal notes), ledger (calls, failed, credits, INR, per provider).
- report/render.py: Markdown version of the same dict (pipes escaped, sources show locator, field, record date and retrieved_at).
- report/question_templates.yaml: wording of questions and requests per claim type. PLACEHOLDER wording; the finance partner owns it.
- tests/report/test_builder.py: 11 tests. Full suite: 100 passed.
- An unknown name in `output.fields` raises ValueError before any row is built (even for a run with no claims).
In progress / exact next step:
- Kit-format JSON: not done. It needs D3 (merger records the kit's output format) and then claude-core's `io/adapter.py to_kit()` maps this report dict; I will not guess the format.
- T20 (hour-3 change) waits for the organisers' requirement; T27 merge reviews start at the first merge request.
How to run / test:
- cd dc-claude-verdict && python -m pytest tests/report -q   (all: python -m pytest -q)
Known bugs or shortcuts taken:
- Report rows for claims with no verdict show label PENDING (not a contract label; report only) and the summary flags the report as incomplete.
- `held` and `founder_questions` use placeholder wording. Questions are only produced for CONTRADICTED claims.
- Nothing here calls an LLM; explanations are the engine's fixed sentences.
Decisions made (also in DECISIONS.md if they change behaviour):
- Question templates live in report/question_templates.yaml (my lane) because rules.yaml has no section for them and the finance partner owns the wording.
Open questions for a human:
- Merger: D3 (kit output format) so to_kit() can be written; finance partner: rewrite report/question_templates.yaml.
Credits / tokens used this session (rough): 0 Crustdata credits; Claude tokens moderate

### 13:35 · claude-verdict-1 · lane claude-verdict · task T27

Status: in-progress (first merge review done; T27 repeats before every merge to main)
Done this session:
- docs/reviews/T27_ag-b.md: 16 numbered fixes for lane ag-b (origin/lane/ag-b @ 64b2a9e) against the real core. Their tests fail at import on the real core (`CheckContext`, `Rules`, `Store` do not exist); every `log_step` call has the wrong argument order; every `Evidence(...)` lacks `retrieved_at` and `call_id`; observed keys differ from D8; funding falls back to the wrong round; Gemini key sits in the URL and can leak into the ledger and logs.
- docs/reviews/T27_codex-a.md: lane codex-a (origin/lane/codex-a @ 501e19b) has only T02 docs so far, no code. The file lists what breaks on merge (nothing expected) and the contract T08, T10, T12 must meet (signatures, ledger in finally, limits, 5 RPM budget, entities shape, ethics, observed keys).
- verdict/engine.py: a result with no evidence and `comparable=False` but no `not_comparable_reason` is now CANNOT_VERIFY `no_evidence` (not NOT_COMPARABLE); DESIGN.md row 2 and a test updated. 101 tests pass.
In progress / exact next step:
- Tell ag-b and codex-a to read their review file, `git fetch && git merge origin/main`, then work the list in order.
- T20: waits for the hour-3 requirement change (13:15 in PLAN; read it, write the DECISIONS entry, assign it, change config or code).
How to run / test:
- cd dc-claude-verdict && python -m pytest -q
Known bugs or shortcuts taken:
- Reviews are static: I ran ag-b's tests on a scratch copy of origin/main (removed afterwards) and read the code; codex-a has no code to run. Items about Crustdata field names are not verified against the live API.
Decisions made (also in DECISIONS.md if they change behaviour):
- Entities shape for resolve (codex-a review item 9) is a proposal, not a contract; codex-a and ag-b must agree it in their HANDOFF entries.
Open questions for a human:
- Correction: an earlier entry of mine says the adapter moved to kit_io/adapter.py (D4). D6 withdrew D4: the adapter is io/adapter.py, loaded with core.adapter_loader. origin/main has io/adapter.py and no kit_io/. The coordinating session asked me to rename mentions to kit_io; I did not, because that would be wrong on main today. Please confirm D6 is current.
- Still open from before: D8 keys in rules.yaml (claude-core), finance partner's answers to the three DESIGN.md questions, D3 kit output format.
Credits / tokens used this session (rough): 0 Crustdata credits; Claude tokens moderate

### 14:12 · claude-verdict@win · lane claude-verdict · task T27

Status: in-progress (waiting for the hour-3 requirement, T20)
Done this session:
- DECISIONS D9: the Windows laptop owns lane claude-verdict (user's decision); labels are `<lane>@<laptop>`.
In progress / exact next step:
- Mac laptop: do not run claude-verdict. Other lanes: the user still has to say which laptop owns each.
- Suggested for the merger (human, on main): add a `.gitattributes` with `* text=auto eol=lf`; Windows and Mac currently disagree on line endings (git warns "LF will be replaced by CRLF" here).
How to run / test:
- n/a (decision only)
Known bugs or shortcuts taken:
- none
Decisions made (also in DECISIONS.md if they change behaviour):
- D9.
Open questions for a human:
- Which laptop owns claude-core, ag, ag-b and codex-a (add a line under D9).
Credits / tokens used this session (rough): none
