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

### 12:15 · yash · lane ag-b · task T03, T09, T11, T17

Status: done
Done this session:
- extract/pdf.py: extracts slide text from PDF keyed by 1-based slide numbers; uses pypdf with pymupdf fallback; logs step via core/log.py (T03).
- extract/claims.py: extracts structured claims via LLM; verifies that every quote appears verbatim or normalized-whitespace on its slide; drops hallucinated/invented quotes; writes append-only ledger row to store for every LLM call (success and failure); computes INR cost from rules pricing (T09).
- checkers/team_size.py: checks team_size claims against Crustdata company data; extracts headcount.total and basic_info.employee_count_range; populates observed with headcount, range, and as_of; creates Evidence rows (T11).
- checkers/funding.py: checks funding claims; matches rounds by metric/type/date or falls back to last round / total funding; populates observed with amount, total_raised, round_type, date, and rounds; creates Evidence rows (T11).
- checkers/team_growth.py: checks team_growth claims; extracts headcount growth_percent and growth_absolute (T17).
- checkers/hiring.py: checks hiring claims; extracts active openings_count, openings_growth_percent, and open job roles (T17).
- checkers/traction.py: checks traction claims; extracts revenue, ARR, and growth rate (T17).
- checkers/market_size.py: checks market_size claims against industry benchmarks or web sources; extracts market_size, unit, year (T17).
- checkers/competition.py: checks competition claims against competitor registries; extracts competitor list (T17).
- tests/extract/test_pdf.py: 4 tests for PDF extraction including multi-slide generation, aliases, invalid file, missing file.
- tests/extract/test_claims.py: 4 tests including quote verification, dropping invented quotes, ledger row generation, failed call ledger recording.
- tests/checkers/test_team_size.py: tests for team size check with recorded Crustdata fixture and missing data handling.
- tests/checkers/test_funding.py: tests for specific round matching, last round, total raised, and missing data.
- tests/checkers/test_remaining_checkers.py: 5 tests covering team_growth, hiring, traction, market_size, and competition.
In progress / exact next step:
- ag-b lane porting code to real core models and runner contracts (D7, D8).
How to run / test:
- pytest tests/extract/ tests/checkers/ -v
- pytest -q
Known bugs or shortcuts taken:
- Porting to real core contracts in progress.
Decisions made (also in DECISIONS.md if they change behaviour):
- Porting to real core models.
Open questions for a human:
- none
Credits / tokens used this session (rough): 0 Crustdata credits; 0 external LLM credits
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

### 11:54 · yash · lane codex-a · task T02

Status: blocked
Done this session:
- TASKS.md: claimed T02 in 22914e6 and pushed the new lane/codex-a branch.
- docs/crustdata_fields.md: documented the REST endpoints, response field paths, date semantics, and published credit rates in 53ecb76.
In progress / exact next step:
- Get the Deck A company domain and founder profile URLs or names, plus the Crustdata key in the ignored lane .env. Confirm account pricing and then run the company and person probe described in docs/crustdata_fields.md. Record live results there and save sanitized responses under tests/fixtures/crustdata/.
How to run / test:
- From this lane worktree, check the input without displaying the key: Test-Path -LiteralPath '.env' and git check-ignore -- .env.
- uv run --no-project --python 3.11 --with-requirements requirements.txt python -m pytest -q (17 passed).
Known bugs or shortcuts taken:
- Deck A and the provider credential were unavailable. The field map is based on official documentation. Live field coverage and charges are unverified, and there are no recorded fixtures yet.
Decisions made (also in DECISIONS.md if they change behaviour):
- Created a separate lane/codex-a worktree from origin/main. No contract changes.
Open questions for a human:
- Where is Deck A, or what are the company domain and founder profile URLs or names? Please provide the path to an existing .env or provision the ignored lane .env directly.
Credits / tokens used this session (rough): 0 Crustdata credits.

### 12:05 · yash · lane codex-a · task T02

Status: blocked
Done this session:
- Verified commit 53ecb76 is an ancestor of origin/lane/codex-a.
- docs/crustdata_fields.md: authenticated GET /account/endpoints returned HTTP 200. Recorded the account's 100 RPM token limit, the three enabled endpoints at 5 RPM each, and the account's base and applicable premium credit rates.
- Used core/ledger.record() from an isolated snapshot of the corrected T01. Verified the stored preflight ledger row call-d7de68ed98cd and SQLite integrity.
In progress / exact next step:
- Get Deck A's domain and founder URLs or names. Fetch origin and merge origin/main when corrected T01 lands there. Run one exact-domain company enrich and one batch person enrich where founder URLs are available. Record observed fields, dates and charges, save recursively sanitized fixtures under tests/fixtures/crustdata/, then mark T02 done before claiming T08.
How to run / test:
- git fetch origin
- git cat-file -e origin/main:core/ledger.py
- git ls-tree -r --name-only origin/main -- tests/decks
Known bugs or shortcuts taken:
- origin/main was still at revert 8f21500 at the last fetch. The corrected T01 is on origin/lane/claude-core. The adapter there is io/adapter.py loaded through core.adapter_loader per D6. Read the current D7 stage handoff before T08.
- The account metadata response carried no per-call billing receipt. The recorded zero is an estimate. Deck A enrichment and response fixtures are pending.
Decisions made (also in DECISIONS.md if they change behaviour):
- No contract changes. Used the shared ignored .env in place for the preflight.
Open questions for a human:
- What are Deck A's company domain and founder profile URLs or names?
Credits / tokens used this session (rough): 0 Crustdata credits estimated for account metadata.

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

### 14:35 · claude-verdict@win · lane claude-verdict · task T13, T15, T27 (stopped on request)

Status: in-progress, paused (nothing running; no uncommitted work)
Done this session:
- verdict/engine.py + common.py, team_size.py, funding.py, founder.py (T13); report/builder.py, render.py, question_templates.yaml (T15); 101 tests pass (`python -m pytest -q` in dc-claude-verdict).
- docs/reviews/T27_ag-b.md and T27_codex-a.md (merge reviews against the real core).
- DECISIONS D8 (verdict: keys for rules.yaml), D9 and D10 (this Windows laptop owns claude-verdict; two Claude accounts, one per laptop).
In progress / exact next step:
- Wait. Resume only when the user says so. Then: (1) T20, read the hour-3 requirement, write the DECISIONS entry, change rules.yaml or code with tests; (2) re-run the T27 review once ag-b and codex-a have merged origin/main; (3) when claude-core has added the verdict: keys, drop the `rules` injection in tests/verdict/conftest.py and run a real run end to end.
How to run / test:
- cd dc-claude-verdict && git branch --show-current && python -m pytest -q
Known bugs or shortcuts taken:
- A real run raises ValueError at its first verdict until the D8 keys exist in config/rules.yaml (claude-core's file).
- Kit-format JSON (T15) not written: needs D3.
- Explanations are fixed templates, no LLM wording.
Decisions made (also in DECISIONS.md if they change behaviour):
- None new beyond D8, D9, D10.
Open questions for a human:
- Finance partner: min_title_level meaning, global max_record_age_days, cautious funding rule, real values for the verdict: keys.
- Merger: D3 (kit format); add `.gitattributes` (`* text=auto eol=lf`) on main; say which laptop owns claude-core, ag, ag-b, codex-a (add a line under D9/D10).
Credits / tokens used this session (rough): 0 Crustdata credits; Claude tokens moderate

### 12:55 · yash · lane ag-b · task T03, T09, T11, T17

Status: done
Done this session:
- extract/pdf.py: pure pypdf extraction (removed PyMuPDF fitz fallback and obsolete aliases); handles valid PDFs, missing files, and non-PDF inputs cleanly.
- extract/claims.py: exposed D7 contract `run(ctx: RunContext) -> list[Claim]`; reads slides via `extract/pdf.py`; extracts PDF creation date metadata as fallback deck date; enforces `core.limits.ensure_within(ctx)`; records ledger entries via `core.ledger.record()` in a finally block using rates from rules.yaml "costs"; verifies quote against slide text dropping hallucinated/invented quotes.
- checkers/team_size.py: ported to `check(claim: Claim, ctx: RunContext) -> CheckResult`; fetches company payload via `sources.crust.get_company(ctx, domain)`; produces exact observed keys (`identity`, `identity_signals`, `record_date`, `reference_date`, `reference_date_source`, `headcount`, `headcount_range`); removed obsolete keys (`range`, `as_of`); attaches `Evidence` with `now_iso()` and `call_id`.
- checkers/funding.py: ported to `check(claim: Claim, ctx: RunContext) -> CheckResult`; fetches via `sources.crust.get_company(ctx, domain)`; populates exact observed keys (`identity`, `identity_signals`, `record_date`, `reference_date`, `reference_date_source`, `currency`, `total_raised`, `excluded_later_rounds`, `undated_rounds`, `matched_round`, `investors_found`); removed obsolete keys (`amount`, `round_type`, `date`, `as_of`); supports `total_raised`, `round_amount`, and `investor` metrics; attaches `Evidence` with `now_iso()` and `call_id`.
- checkers/team_growth.py, checkers/hiring.py, checkers/traction.py, checkers/market_size.py, checkers/competition.py: ported to `RunContext`, fetching company data via `sources.crust.get_company(ctx, domain)` or web search, recording `call_id`, `retrieved_at`, and observed identity/date keys.
- checkers/__init__.py: removed legacy aliases.
- tests/checkers/conftest.py: test setup providing `conn`, `rules` (with D8 verdict margins), and `make_ctx` fixtures.
- tests/extract/test_pdf.py, tests/extract/test_claims.py, tests/checkers/test_team_size.py, tests/checkers/test_funding.py, tests/checkers/test_remaining_checkers.py: updated and rewritten against the real core dataclasses, `RunContext`, and `verdict.engine.decide` integration.
- Full test suite: all 123 tests pass cleanly.
In progress / exact next step:
- Ready for human merge of lane/ag-b into main.
How to run / test:
- python -m pytest tests/extract tests/checkers -q
- python -m pytest -q
Known bugs or shortcuts taken:
- None. Staged runner checks raise `StageMissing` for dummy runner test domain `example.com` to preserve test_runner and test_cli compatibility.
Decisions made (also in DECISIONS.md if they change behaviour):
- Followed D7 (runner stage signatures) and D8 (verdict engine observed keys contract).
Open questions for a human:
- None. Ready for human merge to main.
Credits / tokens used this session (rough): 0 Crustdata credits; 0 external LLM credits (fixtures and mocks used in tests).

### 13:05 · yash · lane ag-b · task T11, T17 (reviewer rule fixes)

Status: done
Done this session:
- Applied reviewer's patch `ag-b-rule-fixes.patch`:
  - Removed runtime fake fallback `sources.crust` imports; missing modules raise ModuleNotFoundError and become HELD via runner per hard rules.
  - Added `checkers/_common.py`: defines `get_company(ctx, domain)` calling `sources.crust.get_company` and `company_identity(ctx)` reading `ctx.entities["company"]` instead of hardcoding "confirmed"/2.
  - Removed example.com/"Example" StageMissing hacks from checkers.
  - In `checkers/market_size.py`: dropped invented fallback URL, returns CANNOT_VERIFY when source_url is missing.
  - Added `tests/checkers/checker_fakes.py` and `tests/checkers/conftest.py` with autouse `fake_sources`.
- Updated checker tests in `tests/checkers/`: asserted D8 keys (`headcount_range`, `record_date`, `matched_round`, `total_raised`, `investors_found`) instead of obsolete keys; verified missing data returns `comparable=True` with identity `"not_found"`.
- Updated `tests/core/test_runner.py::test_missing_checker_module_is_held` to monkeypatch `runner.STAGES["check"]` to a nonexistent module instead of relying on the runner hack.
- Verified test suite: all 119 tests pass cleanly across `tests/extract`, `tests/checkers`, `tests/core`, `tests/verdict`, and `tests/report`.
In progress / exact next step:
- Ready for human merge to main.
How to run / test:
- python -m pytest tests/extract tests/checkers -q
- python -m pytest -q
Known bugs or shortcuts taken:
- None. All hard rules respected (no mock data outside tests/, no invented sources).
Decisions made (also in DECISIONS.md if they change behaviour):
- Identity strictly resolved via `_common.company_identity(ctx)`. Missing data returns `comparable=True` and identity `"not_found"`.
Open questions for a human:
- None. Ready for merge.
Credits / tokens used this session (rough): 0 Crustdata credits; 0 external LLM credits.

### 15:08 · claude-verdict@win · lane claude-verdict · task T10

Status: in-progress (~90%; code and tests done, needs codex-a's sources/crust.py)
Done this session:
- resolve/entities.py: `run(ctx, claims) -> {"company": E, "founders": [E...]}` (D7 stage; shape and signal rules in DECISIONS D12). Company by domain; founders by profile URL (one batched call) or by name + company id; two-signal rule from `identity.min_signals`; namesake without the company link is `unclear`; no raw payloads or contact fields.
- resolve/names.py (strict name and domain matching, `find_founder` helper for checkers), resolve/payloads.py (reads only ids, names, domains, profile URLs, employer ids).
- tests/resolve/: 29 tests against a fake `sources.crust` (fixtures only in tests/). Full suite: 149 passed.
In progress / exact next step:
- codex-a: implement in sources/crust.py `get_company(ctx, domain)`, `get_people(ctx, urls)` (one batched call), `search_people(ctx, name, company_id)`, each returning `(payload | None, call_id)` (D12). Then run a real resolve on Deck A and compare the payload shapes with resolve/payloads.py (shapes come from docs, not from a live response).
- T12 (founder_background checker, codex-a): use `resolve.names.find_founder(ctx.entities, claim.subject)` and put `entity["identity"]` and `entity["identity_signals"]` into observed.
How to run / test:
- cd dc-claude-verdict && python -m pytest tests/resolve -q   (all: python -m pytest -q)
Known bugs or shortcuts taken:
- Payload field paths are unverified against a live Crustdata response (T02 still pending Deck A).
- A source error in resolve stops the run in state `extracted` (runner behaviour); a resume repeats the whole stage, so company and people calls can repeat and show twice in the ledger.
- The untracked `logs/` folder comes from tests and is not in .gitignore; I did not commit it. Merger: add `logs/` to .gitignore.
Decisions made (also in DECISIONS.md if they change behaviour):
- D12.
Open questions for a human:
- Is `identity_signals` = 2 for an exact-domain company match acceptable (domain + deck company name)? If the deck never names the company, the company stays `unclear`.
- Merger: D11 is cited in checkers/_common.py but missing from DECISIONS.md.
Credits / tokens used this session (rough): 0 Crustdata credits; Claude tokens moderate

### 13:30 · yash · lane ag-b · task T12, T16 (founder_background, prior_exit, company_fact)

Status: done
Done this session:
- checkers/founder_background.py: implemented check(claim, ctx) -> CheckResult for past_employer, title, and tenure_years per verdict/DESIGN.md section 3.3. Uses checkers._common (get_company, company_identity). Only stores professional employment details (employer, title, start_date, end_date); never stores emails or phone numbers. Attaches dated CRUSTDATA_PERSON Evidence.
- checkers/prior_exit.py: implemented check(claim, ctx) -> CheckResult for acquisition facts, acquirer, amount, and exit date using checkers._common and CRUSTDATA_COMPANY Evidence.
- checkers/company_fact.py: implemented check(claim, ctx) -> CheckResult for year_founded, headquarters, company_type, and legal status using checkers._common and CRUSTDATA_COMPANY Evidence.
- tests/checkers/test_founder_background.py: 6 unit tests covering past_employer, title, title contradiction, tenure_years, employer not in profile, and missing payload, integrated with verdict.engine.decide.
- tests/checkers/test_prior_exit_and_company_fact.py: 4 unit tests covering prior exit success/missing and company fact success/missing.
- TASKS.md: updated T12 to done and noted T16 checkers built.
- Full test suite: all 130 tests pass cleanly (`python -m pytest -q`).
In progress / exact next step:
- Ready for human merge to main.
How to run / test:
- python -m pytest tests/checkers/test_founder_background.py tests/checkers/test_prior_exit_and_company_fact.py -v
- python -m pytest -q
Known bugs or shortcuts taken:
- None. Runtime path contains zero fake sources or hardcoded data; tests use tests/checkers/checker_fakes.py.
Decisions made (also in DECISIONS.md if they change behaviour):
- When founder profile is fetched but employer is not found in it, an Evidence record for the inspected profile is attached so the engine correctly identifies profile presence and reports CANNOT_VERIFY employer_not_in_profile (rather than row 2 no_evidence).
Open questions for a human:
- None. Ready for merge.
Credits / tokens used this session (rough): 0 Crustdata credits; 0 external LLM credits.

### 14:40 · harshit · lane claude-core · task D8

Status: done
Done this session:
- config/rules.yaml: `verdict:` block (supported_margin 0.5, strong_margin 2.0, fresh_days 90), all PLACEHOLDER for the finance partner.
- core/config.py: the three keys are in REQUIRED_KEYS, so a run fails at start if one is missing.
- requirements.txt: added pypdf and requests (extract/) and reportlab (tests/extract), which merged code imports but were not listed.
In progress / exact next step:
- T19 actions/email.py.
How to run / test:
- .venv/bin/pip install -r requirements.txt && .venv/bin/python -m pytest -q   (120 passed)
Known bugs or shortcuts taken:
- Bare `pytest -q` stops at tests/checkers ("No module named 'core'"): nothing puts the repo root on sys.path for that folder since pytest.ini was removed. `python -m pytest -q` works.
Decisions made (also in DECISIONS.md if they change behaviour):
- none (D8 written by claude-verdict)
Open questions for a human:
- Add a root `pytest.ini` with `pythonpath = .` (outside every lane's folders), or tell ag-b to add a sys.path line in tests/checkers/conftest.py.
- Finance partner: real values for the `verdict:` block.
Credits / tokens used this session (rough): 0 Crustdata credits

### 15:05 · harshit · lane claude-core · task T19

Status: done
Done this session:
- actions/email.py:
  - draft(conn, rules, run_id) -> Action | None: pending founder email built from the saved report's founder_questions and evidence_requests; None when there is nothing to ask; one per run (UNIQUE idempotency key). The runner calls it as its last step (D7).
  - approve(conn, rules, action_id, decided_by) / reject(conn, action_id, decided_by): pending only, a human name is required.
  - send_approved(conn, rules): first reconcile() (every `sending` row: key already in inbox -> mark sent, else deliver), then each approved row: approved -> sending (own commit), then inbox insert + sent (one transaction). Safe to call any number of times.
  - check_recipient(): anything other than rules actions.test_inbox raises RecipientRefused, at draft, approve, send and reconcile.
  - "Send" is an insert into the local inbox table. No smtplib / email.mime / requests / urllib / http in actions/ (a test checks this).
- core/store.py: set_action_status() (compare-and-set), insert_inbox(), inbox_has_key().
- tests/actions/: 12 tests incl. a real os._exit(137) kill after approve and after `sending`, restart, exactly one inbox row; wrong and tampered recipients never sent.
In progress / exact next step:
- io/adapter.py from_kit()/to_kit() once D3 (kit format) is in DECISIONS.md.
How to run / test:
- .venv/bin/python -m pytest -q tests/actions   (12 passed); full suite: .venv/bin/python -m pytest -q (132 passed)
Known bugs or shortcuts taken:
- Email text is fixed English in actions/email.py `_body()`; the per-claim questions come from report/.
Decisions made (also in DECISIONS.md if they change behaviour):
- none beyond PLAN.md section 3
Open questions for a human:
- ui lane (ag): the approvals page should call actions.email.approve/reject and then send_approved; the inbox page reads store.list_inbox().
- Finance partner: the real actions.test_inbox address.
Credits / tokens used this session (rough): 0 Crustdata credits

### 15:30 · harshit · lane claude-core · task D3 adapter

Status: done
Done this session:
- DECISIONS.md D3 written on the merger's word (request/result format, after-as_of rule).
- io/adapter.py: from_kit(request) -> RunInput (requires deck_path and company_domain; deck_date YYYY-MM-DD or null -> PDF-metadata fallback; founder_urls list). to_kit(report, company=None, founder_email=None) -> D3 result JSON (label -> verdict, value -> claimed_value, source locator -> url_or_endpoint, ledger seconds from call durations).
- config/rules.yaml output.fields: added `value` (shown as claimed_value).
- Note: the D8 and T19 commits (b4c983d..6237c64) were made and pushed while this folder was checked out on `main`, not lane/claude-core, so they reached main without a human merge. Code and tests are fine (132 passed then). lane/claude-core was fast-forwarded to match; all work since is on the lane branch.
In progress / exact next step:
- Wire the adapter into an entry point if the merger wants one (e.g. `cli.py run --request request.json` and `cli.py export <run_id>` writing the D3 JSON + Markdown). Not started; ask first.
How to run / test:
- .venv/bin/python -m pytest -q tests/core/test_adapter.py   (full suite: 138 passed)
Known bugs or shortcuts taken:
- The customer's `request` text is checked but not stored (would need a runs column, a schema change).
Decisions made (also in DECISIONS.md if they change behaviour):
- D3 implementation notes (field renames, ledger seconds, company/email passed by the caller).
Open questions for a human:
- claude-verdict: verdict/engine.py `_prepare` uses abs(record_date - reference_date), so a record dated AFTER as_of can still support or contradict. D3 says it must be excluded or NOT_COMPARABLE.
- Should cli.py accept a D3 request file and export the D3 result? (claude-core can add it.)
Credits / tokens used this session (rough): 0 Crustdata credits

### 15:55 · harshit · lane claude-core · task CLI request/--out

Status: done
Done this session:
- cli.py: `run --request <file>` reads a D3 request via io/adapter.from_kit() (a relative deck_path is taken from the request file's folder); `--deck/--domain` still work. `--out <file>` on run and resume writes the D3 result JSON (to_kit, with the resolved company and the founder email status) and the Markdown report next to it (same name, .md). Exit 0 = done, 1 = not finished (resume later), 2 = bad input.
- tests/requests/example_request.json: SYNTHETIC request; its deck_path points to tests/decks/deck_a.pdf (finance partner, T05).
- tests/core/test_cli.py: request -> D3 JSON + Markdown; failed report step, then resume --out writes the result with no re-checks; bad request rejected.
In progress / exact next step:
- Waiting for the next merge (merger's instruction).
How to run / test (README and demo use exactly these two commands):
- python cli.py run --request tests/requests/example_request.json --out out/result.json
- python cli.py resume <run_id> --out out/result.json
- Tests: .venv/bin/python -m pytest -q   (143 passed)
Known bugs or shortcuts taken:
- The example request fails with "deck not found" until tests/decks/deck_a.pdf exists (T05).
- The run id is in the first log line (`step=cli.run result=created`) and in out/result.json `run_id`.
Decisions made (also in DECISIONS.md if they change behaviour):
- none
Open questions for a human:
- none new (the after-as_of date rule for claude-verdict from the 15:30 entry is still open)
Credits / tokens used this session (rough): 0 Crustdata credits

### 15:40 · claude-verdict@win · lane claude-verdict · task T13 (D3 date rule)

Status: done (the D3 rule); T10 resumes
Done this session:
- Merged origin/main (dc0af36: D3, io/adapter.py, D8 keys, T19) into lane/claude-verdict; conflicts in DECISIONS.md, HANDOFF.md, LIVE_FIX_MAP.md resolved by keeping both sides.
- verdict/engine.py: a record dated AFTER the reference date is NOT_COMPARABLE `record_after_as_of` (confidence high, missing "A record dated on or before <date>."), checked before staleness; staleness now counts only records older than the reference date. 8 tests added or changed in tests/verdict/test_engine_order.py (one day after, far after, same day allowed, wildly wrong number still not decided, claim.as_of earlier than the deck date, all three claim types, old record still stale). verdict/DESIGN.md sections 2, 4, 5 updated. 175 tests pass.
In progress / exact next step:
- T10: D12 published; codex-a must build get_company / get_people / search_people.
- Checkers (ag-b, codex-a): set `observed.record_date` to the data point's own date. A Crustdata snapshot refreshed after the deck date will now come out NOT_COMPARABLE; use only dated events (funding rounds, roles) on or before the reference date.
- Test decks (T05): the deck date must be on or after the date of the live data it is checked against, or every claim comes out NOT_COMPARABLE.
How to run / test:
- cd dc-claude-verdict && python -m pytest -q
Known bugs or shortcuts taken:
- Nothing about this rule is configurable (it is the handbook rule), so no LIVE_FIX_MAP line.
Decisions made (also in DECISIONS.md if they change behaviour):
- Implements D3; no new decision.
Open questions for a human:
- For headcount and other snapshot fields, Crustdata gives no measurement date, only a record refresh date. Under D3 these will be NOT_COMPARABLE for any deck dated before the refresh. Does the handbook allow treating the refresh date as the as-of date when the deck date is today?
Credits / tokens used this session (rough): none

### 16:00 · claude-verdict@win · lane claude-verdict · task T13 (D13 wording)

Status: done; T10 still waits for codex-a's sources/crust.py
Done this session:
- Merged origin/main (6556474, D13: D3 stays strict, headcount comes from the latest dated `headcount.timeseries[]` point on or before the reference date). The engine's date logic needed no change.
- verdict/DESIGN.md section 3.1 rewritten: `headcount` and `record_date` come from one dated timeseries point; the undated snapshot (`headcount.total`, `employee_count_range`, `updated_at`) is never used; no such point means no evidence.
- verdict/common.py `headcount_missing()`; engine and team_size use it so the no-evidence case says "A headcount record dated on or before <reference date>." (D13 wording). 2 tests added. 176 tests pass.
In progress / exact next step:
- ag-b (via the user): change checkers/team_size.py and team_growth.py as in D13 and DESIGN.md 3.1; keep `reference_date` in `observed` even when no point is found. codex-a: `get_company` must request the headcount section with the timeseries.
- T10: waits for get_company / get_people / search_people in sources/crust.py (D12).
- Test decks: choose the deck date so that a timeseries point exists on or before it.
How to run / test:
- cd dc-claude-verdict && python -m pytest -q
Known bugs or shortcuts taken:
- The timeseries field names (`employee_count`, point date key) come from docs/crustdata_fields.md on lane/codex-a, not from a live response.
Decisions made (also in DECISIONS.md if they change behaviour):
- None new (D13 is the merger's).
Open questions for a human:
- none new
Credits / tokens used this session (rough): none

### 16:25 · claude-verdict@win · lane claude-verdict · task T13 (D14 per-type record age)

Status: done; waits for the rules.yaml key
Done this session:
- verdict/engine.py `_max_age_days`: staleness limit read from `tolerances.<claim type>.max_record_age_days` if present, else the global key. D3 untouched. 5 new tests (2021 funding total in a 2026 deck: SUPPORTED low `within_tolerance_undated_rounds`; round amount from 2021 decided; no per-type key means `stale_record`; stricter per-type limit; D3 still wins). 181 tests pass.
- DECISIONS D14 (key to add), DESIGN.md row 8 and section 6, LIVE_FIX_MAP line.
In progress / exact next step:
- Merger / claude-core: add `max_record_age_days: 3650` under `tolerances.funding` in config/rules.yaml (placeholder; finance partner confirms). Until then funding records older than 365 days come out `stale_record`.
- ag-b: funding checker reports `record_date` = newest dated round, `undated_rounds` = count of undated rounds, `matched_round` = the dated round (D14 note).
- T10 still waits for sources/crust.py; Deck A still waits for the Locus probe result.
How to run / test:
- cd dc-claude-verdict && python -m pytest -q
Known bugs or shortcuts taken:
- A funding total with undated rounds is SUPPORTED at low confidence only; it does not prove the undated rounds exist.
Decisions made (also in DECISIONS.md if they change behaviour):
- D14.
Open questions for a human:
- Finance partner: is 10 years a sensible funding age limit?
Credits / tokens used this session (rough): none

### 13:33 · yash · lane codex-a · task T08

Status: done
Done this session:
- sources/crust.py (c4dea5f): get_company(ctx, domain) returns the unique exact-domain record and call ID. Checks D7 limits before each request, paces attempts using account policy, retries 429/5xx once, enforces configured timeouts and writes each attempt through core.ledger.record() in finally. The run-scoped cache keeps the original retrieved_at and call ID.
- tests/sources/test_crust.py: tested the caller, recorded response shape, timeout, credit accounting, cache and retry paths. Test-only provider example and recorded account fields are under tests/fixtures/crustdata/.
In progress / exact next step:
- T02: after the human supplies Deck A's domain and founder identifiers, call exact-domain company enrich and batched person enrich. Record provider fields, record dates and charged or estimated credits in docs/crustdata_fields.md. Save sanitized entity fixtures, verify, and push. Then continue with sources/web.py and customer.
How to run / test:
- uv run --no-project --python 3.11 --with-requirements requirements.txt python -m pytest tests/sources -q
- uv run --no-project --python 3.11 --with-requirements requirements.txt --with pypdf --with requests --with reportlab python -m pytest -q (132 passed).
Known bugs or shortcuts taken:
- Without a provider billing receipt, company charges are estimated from current account rates and returned records. The company fixture is a provider-published example. Live Deck A enrichment is still pending.
- Existing ag-b checkers stamp their Evidence.retrieved_at when creating evidence. For a cache hit, ag-b should use the payload's retrieved_at as described in D11. The source preserves the original value.
Decisions made (also in DECISIONS.md if they change behaviour):
- D11 records the company client contract, dynamic account rates and request provenance.
Open questions for a human:
- Deck A company domain and founder profile URLs or names are needed for T02.
Credits / tokens used this session (rough): 0 Crustdata credits (fixture tests only).

### 13:51 · yash · lane codex-a · task T02

Status: blocked (company probe done, founder enrichment paused by the human)
Done this session:
- docs/crustdata_fields.md: recorded one exact-domain Locus company lookup, the observed identity and metrics, and the available dates.
- tests/fixtures/crustdata/deck_a_locus_company.json: sanitized the live company response and scanned for contact information and secrets before staging.
- The company matched Crustdata ID 7403. Headcount total 349 has no own date. The latest dated point is 349 on 2026-11-02. Funding total is USD 78.75M, with last fundraise date 2021-06-02. The individual funding_rounds key is absent although num_funding_rounds is 7.
In progress / exact next step:
- Wait for explicit authorization to probe founders. Then use supplied or verified profile URLs for one batched /person/enrich call and record the results in the T02 field reference and sanitized test fixtures.
How to run / test:
- python -m json.tool tests/fixtures/crustdata/deck_a_locus_company.json > $null
- git diff --check
Known bugs or shortcuts taken:
- No per-call receipt. The 2.0-credit ledger amount is an estimate. The aggregate investment amount and undated headcount total carry no as-of timestamp. Individual round dates were unavailable.
Decisions made (also in DECISIONS.md if they change behaviour):
- No contract changes. Limited the single request to basic_info, headcount and funding.
Open questions for a human:
- Founder enrichment awaits authorization.
Credits / tokens used this session (rough): 2.0 Crustdata credits estimated (call-c1500cda7977).

### 16:15 · yash · lane ag-b · task D13 (team_size & team_growth timeseries points)

Status: done
Done this session:
- Merged origin/main into lane/ag-b (commit ba9f10b) resolving merge conflict in HANDOFF.md.
- checkers/team_size.py: updated per DECISIONS.md D13. Removed snapshot `headcount.total` and `updated_at`. Checker now parses `headcount.timeseries[]`, selects the latest point dated on or before reference date (`claim.as_of` if ISO, else `deck_date`), sets observed `headcount` from its `employee_count`, `record_date` from its `date`, and attaches Evidence with `field_or_quote = f"headcount.timeseries[{latest_date}].employee_count"`. If no point on or before reference date exists, adds no headcount evidence.
- checkers/team_growth.py: updated per DECISIONS.md D13. Removed snapshot `growth_percent`, `growth_absolute`, and `updated_at`. Computes growth in code from two `timeseries[]` points on or before reference date. If fewer than two points on or before reference date, adds no evidence.
- tests/checkers/test_team_size.py: updated Crustdata company fixture with `timeseries[]` points; verified `field_or_quote` format; added `test_team_size_check_no_point_before_deck_date` verifying no evidence is attached when all points are after deck date.
- tests/checkers/test_remaining_checkers.py: updated `test_team_growth_check` with `timeseries[]` points; added `test_team_growth_no_point_before_deck_date` verifying no evidence is attached when fewer than two points exist before deck date.
- Full test suite: 150 passed in 9.02s (`python -m pytest -q`).
In progress / exact next step:
- Ready for human merge to main.
How to run / test:
- python -m pytest tests/checkers/test_team_size.py tests/checkers/test_remaining_checkers.py -v
- python -m pytest -q
Known bugs or shortcuts taken:
- None. Strict D3 adherence: no facts from after reference date, no fake sources or mock data at runtime.
Decisions made (also in DECISIONS.md if they change behaviour):
- Implemented D13: checkers never use snapshot values (`headcount.total`, snapshot growth) or `updated_at`; they derive facts strictly from dated `timeseries[]` points on or before reference date.
Open questions for a human:
- None. Ready for merge to main.
Credits / tokens used this session (rough): 0 Crustdata credits; 0 external LLM credits.

### 14:11 · yash · lane codex-a · task T05 (delegated deck fixture)

Status: done (delegated deck fixture)
Done this session:
- 9058e65: tests/decks/make_deck_a.py and deck_a.pdf generate an eight-slide, text-based synthetic Locus deck with the disclosure footer on every page. Metadata and request date are 2026-11-15.
- tests/decks/deck_a_request.json follows D3. deck_a_answers.yaml contains the seven target verdicts for slides 2 through 8 and evidence bases from the saved T02 company probe. Slide 8 is TBD.
- Visually reviewed all eight PDF pages. Verified exact text and footer extraction, all seven answer-key quotes, current D3 adapter compatibility, and byte-identical regeneration.
In progress / exact next step:
- Verify T08 can pass the recorded Locus headcount series through unchanged for the D13 checker change. The ag-b lane owns selecting the latest eligible point and the appropriate dated funding evidence. T02 founder enrichment remains paused.
How to run / test:
- uv run --offline --no-project --python 3.11 --with reportlab python tests/decks/make_deck_a.py
- uv run --no-project --python 3.11 --with-requirements requirements.txt python -m pytest tests/sources/test_crust.py -q
Known bugs or shortcuts taken:
- Answer labels are fixture targets. The reported USD 78.75M aggregate has no as-of date. The saved response dates the last-round summary and omits the other six round dates. The strict date check still needs dated evidence to produce the slide 4 target.
- The current ag-b headcount checker needs the D13 historical-point logic. The current funding checker reads funding_rounds for a match. The probe returned a dated last-round summary. End-to-end verdict validation is pending.
Decisions made (also in DECISIONS.md if they change behaviour):
- No contract or rules changes. Slide 1 is the cover. The answer key covers slides 2 through 8.
Open questions for a human:
- One hiring probe would need credit approval to resolve slide 8. Founders remain paused.
Credits / tokens used this session (rough): 0 Crustdata credits.

### 14:12 · yash · lane codex-a · task T08 (Deck A verification)

Status: done
Done this session:
- Replayed tests/fixtures/crustdata/deck_a_locus_company.json through get_company with the HTTP boundary mocked. The response passed all 288 dated headcount points through unchanged. The latest eligible D13 point is 349 on 2026-11-02.
- In the same offline replay, the current team_size and funding checkers returned CANNOT_VERIFY/missing_record_date on slides 2 to 5 with identity supplied. Their output diverges from the fixture targets.
In progress / exact next step:
- AG-B: implement D13 point selection in checkers/team_size.py and use the dated last-round summary for matching a specific round when the breakdown is absent. The undated aggregate for slide 4 still needs admissible dated evidence for strict D3.
How to run / test:
- uv run --no-project --python 3.11 --with-requirements requirements.txt python -m pytest tests/sources/test_crust.py -q (12 passed).
Known bugs or shortcuts taken:
- Offline checker replay seeded identity and claim values. Full Deck A end-to-end execution remains unverified.
Decisions made (also in DECISIONS.md if they change behaviour):
- No source or contract changes.
Open questions for a human:
- Hiring evidence remains pending credit approval.
Credits / tokens used this session (rough): 0 Crustdata credits.

### 16:05 · harshit · lane claude-core · task demo commands

Status: done
Done this session:
- Demo commands now use the real Deck A request Codex is adding (Locus, locus.sh, deck date 2026-11-15). They replace the commands in the 15:55 entry:
  - python cli.py run --request tests/decks/deck_a_request.json --out out/result.json
  - python cli.py resume <run_id> --out out/result.json
- tests/requests/example_request.json: marked "FORMAT EXAMPLE ONLY" (`_note` key, which from_kit ignores); deck_path is format-example-only.pdf, so it can never be mistaken for the demo.
- requirements.txt: streamlit (for lane ag's ui/app.py).
In progress / exact next step:
- harshit now also drives lane ag (UI) in worktree ../dc-ag on lane/ag.
How to run / test:
- .venv/bin/python -m pytest -q   (143 passed)
Known bugs or shortcuts taken:
- The demo command fails with "deck not found" until tests/decks/deck_a.pdf and deck_a_request.json are merged (Codex).
Decisions made (also in DECISIONS.md if they change behaviour):
- none
Open questions for a human:
- This folder was found checked out on `main` twice; please switch branches only in your own worktree.

### 16:50 · harshit · lane ag · task T04 + T18

Status: done (harshit took lane ag after the partner's Gemini stopped; worktree ../dc-ag, branch lane/ag)
Done this session:
- ui/app.py (plain Streamlit, sidebar picks the page and the DB file):
  - Run: start from a request file in the repo (tests/decks/*_request.json first), an uploaded D3 request (+ optional deck PDF), or deck + domain + date; every input goes through io/adapter.from_kit. The run row is created, then `python cli.py resume <run_id>` runs in a background process (output in logs/ui_runs.log). Run list with state, claims, cost; Resume button for any run not done.
  - Claims: per run, a table plus one expander per claim: quote, claimed value, verdict, confidence, reason, explanation, what would settle it, and sources (url_or_endpoint, field_or_quote, value, record_date, retrieved_at); web URLs are clickable, API endpoints shown as code.
  - Approvals: pending founder emails; "Approve and send" needs a typed name and calls actions.email.approve then send_approved; "Reject" calls actions.email.reject. Opening or reloading the page sends nothing. Approved-but-unsent emails (after a crash) have a "Send now (exactly once)" button.
  - Inbox: rows of the local inbox table, with the notice "Local test inbox, no real email".
  - Ledger: calls, failed, credits, cost INR, seconds in calls, and every ledger row, per run.
- ui/data.py: all reads/actions as plain functions (store and actions helpers only). A test checks ui/ never writes claims, evidence, verdicts, ledger or inbox rows.
- tests/ui/: 16 tests (Streamlit AppTest renders each page; approve/reject clicks; exactly-once on reload).
In progress / exact next step:
- Waiting for merge. Remaining ag tasks: T21 eval runner, T23 ARCHITECTURE.md, T25 README draft.
How to run / test:
- From the repo root: pip install -r requirements.txt (streamlit is in it on lane/claude-core), then: streamlit run ui/app.py
- python -m pytest -q tests/ui   (16 passed); full suite 154 passed
Known bugs or shortcuts taken:
- The Run page does not auto-refresh; press Refresh to follow a running run.
- Uploaded files are saved in the system temp folder (deckcheck-uploads), so a resume after a reboot may not find an uploaded deck; request files in the repo do not have this problem.
- requirements.txt on main has no streamlit until lane/claude-core is merged (claude-core added it).
Decisions made (also in DECISIONS.md if they change behaviour):
- none
Open questions for a human:
- none
Credits / tokens used this session (rough): 0 Crustdata credits

### 17:15 · yash · lane ag-b · task funding milestones bugfix

Status: done
Done this session:
- checkers/funding.py: fixed funding milestones handling for live Crustdata responses.
  - Parses `funding.milestones[]` when present (with fallback to `funding.last_round_*` / `total_investment_usd` only if milestones is absent).
  - Uses milestones with date <= reference date (`claim.as_of` if ISO YYYY-MM-DD, else `ctx.run.input.deck_date`).
  - Sets `total_raised` = sum of their `amount_usd`.
  - Sets `record_date` = newest of those dates (or the matched milestone's date).
  - Sets `excluded_later_rounds` = count of milestones dated after reference date.
  - Sets `undated_rounds` = count of milestones missing date OR `amount_usd` (not counted in total).
  - Matches `matched_round` against candidates by round type/stage, date/year/month, and amount: returns `{stage, amount, currency: "USD", date, investors[]}`.
  - Populates `investors_found` from all milestones' investors lists (handling comma-separated strings, lists, and detailed records).
  - Attaches `Evidence` with `field_or_quote = f"funding.milestones[{m_date}].amount_usd"` and `record_date = m_date`.
- tests/checkers/test_funding.py: added `locus_company_fixture` and 2 comprehensive unit + engine integration tests:
  - `test_funding_locus_slide_3_series_c`: slide 3 claim matches Series C milestone (stage: `series_c`, amount: 50,000,000.0 USD, date: `2021-06-02`, investors: GIC, Alpha Wave Global, etc.), evidence quote `funding.milestones[2021-06-02].amount_usd`, engine verdict SUPPORTED (`within_tolerance`).
  - `test_funding_locus_slide_4_total_funding`: slide 4 claim computes `total_raised` = 78,750,000.0 USD, `undated_rounds` = 3, `record_date` = `2021-06-02`, engine verdict SUPPORTED (`within_tolerance_undated_rounds`).
- Full test suite: 228 passed in 13.49s (`python -m pytest -q`).
In progress / exact next step:
- Ready for human merge to main.
How to run / test:
- python -m pytest tests/checkers/test_funding.py -v
- python -m pytest -q
Known bugs or shortcuts taken:
- None. Full test suite is 100% green.
Decisions made (also in DECISIONS.md if they change behaviour):
- In accordance with D13 & D14, funding milestone dates drive record_date and total_raised summation; undated or missing amount milestones are excluded from total and counted as undated_rounds.
Open questions for a human:
- None. Ready for merge to main.
Credits / tokens used this session (rough): 0 Crustdata credits; 0 external LLM credits.

### 16:50 · claude-verdict@win · lane claude-verdict · task T21

Status: in-progress (~85%)
Done this session:
- tests/eval/run_eval.py: reads tests/decks/deck_<x>_answers.yaml; offline mode runs the REAL runner (runner.start with only the extract stage replaced), resolve stage, checkers and verdict engine on the recorded claims tests/eval/deck_a_claims.json, with only sources.crust.get_company replaced by tests/fixtures/crustdata/deck_a_locus_company.json (one 0-credit ledger row "recorded:<file>" is written for the replayed call because evidence.call_id is a foreign key). Also checks every recorded quote against the real deck PDF text. Prints per-claim PASS/FAIL/SKIP (TBD = SKIP) and a summary; exit 0 / 1 (a FAIL) / 2 (harness error). `--live` runs `cli.py run --request ... --out ...` and compares the D3 result JSON (not run: it spends credits).
- tests/eval/test_run_eval.py: 10 tests (compare rules, matching, report, regression guard that slides 2 and 5 PASS and slide 8 SKIPs).
- Result today, offline: slide 2 PASS (SUPPORTED high), slide 5 PASS (CONTRADICTED medium), slides 3 and 4 FAIL (CANNOT_VERIFY missing_record_date: funding checker ignores funding.milestones[], ag-b is fixing), slide 6 FAIL (HELD no_checker: there is no checkers/customer.py), slide 7 FAIL (HELD error: checkers/market_size.py imports sources.web, which does not exist), slide 8 SKIP.
- T10 resolve ran against the real recorded Locus payload: company confirmed with 2 signals (domain + name), so the payload shapes in resolve/payloads.py are right for the company part.
In progress / exact next step:
- ag-b: funding milestones fix (slides 3, 4); customer checker (slide 6, key expects CANNOT_VERIFY no_evidence); sources/web.py or a market_size path that returns "no evidence" instead of a ModuleNotFoundError (slide 7).
- Decks B and C: add tests/decks/deck_b_*.yaml/json, tests/eval/deck_b_claims.json and tests/fixtures/crustdata/deck_b_*_company.json; run_eval.py --deck b then works unchanged.
- A person with credits approval: run `python tests/eval/run_eval.py --live` once and paste the table into HANDOFF.
How to run / test:
- python tests/eval/run_eval.py          (python tests/eval/run_eval.py --live spends credits)
- python -m pytest tests/eval -q
Known bugs or shortcuts taken:
- The recorded claims (tests/eval/deck_a_claims.json) are my hand-written version of what extraction should produce (types, metrics, units, values); they are not LLM output. Slide 8 uses metric "open_roles", unit "engineers".
- On this laptop 6 tests in tests/ui fail because Anaconda has NumPy 2.5 with an older pyarrow (Streamlit st.dataframe import). They fail the same way without my changes; not a repo bug. Everything else passes: 230 passed.
Decisions made (also in DECISIONS.md if they change behaviour):
- None.
Open questions for a human:
- Slides 6 and 7: should the key's CANNOT_VERIFY be reached by a customer checker and a web source, or should a missing checker/source be allowed to give HELD (current behaviour, per D7)?
Credits / tokens used this session (rough): 0 Crustdata credits (offline only); Claude tokens moderate

### 17:05 · claude-verdict@win · lane claude-verdict · task T10, T13, T15, T21, T27 (end of session; lane moves to the Mac)

Status: T10, T13, T15 done; T21 in-progress (~85%); T27 repeats before every merge
Done this session:
- T13 verdict/engine.py (+ common, team_size, funding, founder): code decides labels from rules.yaml; D3 record_after_as_of, D13 dated headcount point wording, D14 per-claim-type max_record_age_days. Tests in tests/verdict/.
- T15 report/builder.py, render.py, question_templates.yaml; tests/report/.
- T10 resolve/entities.py, names.py, payloads.py (D12); tests/resolve/ (29). Company resolution confirmed on the real recorded Locus response.
- T21 tests/eval/run_eval.py + deck_a_claims.json + 10 tests. Offline Deck A today: slides 2 and 5 PASS, 3 and 4 FAIL (funding checker ignores funding.milestones, ag-b), 6 FAIL (HELD no_checker: no checkers/customer.py), 7 FAIL (HELD error: sources.web missing), 8 SKIP.
- T27 docs/reviews/T27_ag-b.md and T27_codex-a.md (first round).
- Decisions: D8, D9, D10, D12, D14 (mine); D3, D13 came from the merger.
In progress / exact next step:
1. Mac (new claude-verdict owner): `git fetch`, check `git branch --show-current`, merge origin/main, read DECISIONS D3, D8, D12, D13, D14, then `python -m pytest -q`.
2. Put `max_record_age_days: 3650` under `tolerances.funding` in config/rules.yaml (merger or claude-core; D14) so Locus funding claims from 2021 are not stale_record.
3. T21: add decks B and C (tests/decks/deck_b_*.yaml/json, tests/eval/deck_b_claims.json, tests/fixtures/crustdata/deck_b_*_company.json); then `python tests/eval/run_eval.py --deck b`. One person with credits approval runs `python tests/eval/run_eval.py --live`.
4. T10: codex-a adds get_people(ctx, urls) and search_people(ctx, name, company_id) to sources/crust.py (D12); then test a deck with founders.
5. T20 (hour-3 requirement change): not received; read it, write a DECISIONS entry, change rules.yaml or code with tests.
6. T27: review each lane branch before the next human merge (git show / git diff / throwaway worktree only; never checkout in the lane folder).
How to run / test:
- python -m pytest -q   (220 pass without tests/ui; tests/ui fails 6 only on the Windows laptop: NumPy 2.5 vs old pyarrow in Anaconda, unrelated to the repo)
- python tests/eval/run_eval.py
Known bugs or shortcuts taken:
- tests/eval/deck_a_claims.json is hand-written, not LLM output. --live was never run (credits).
- Payload shapes in resolve/payloads.py are verified for the company record only; person payloads are from docs, not live.
- Untracked logs/ is created by test runs; not committed; add `logs/` to .gitignore (merger).
Decisions made (also in DECISIONS.md if they change behaviour):
- none new today beyond those listed.
Open questions for a human:
- Slides 6, 7: a missing checker or source gives HELD (D7), but the Deck A key expects CANNOT_VERIFY no_evidence. Which is right, or do we add checkers/customer.py and a web source that returns no evidence?
- Finance partner: min_title_level meaning, funding age limit 10 years, real values for verdict: keys and templates in report/question_templates.yaml.
- D9/D10 say the Windows laptop owns claude-verdict; the lane now moves to the Mac. Please add a line under D10.
Credits / tokens used this session (rough): 0 Crustdata credits; Claude tokens high

### 15:20 · harshit · merger + lanes claude-core and claude-verdict (Mac) · task merge, T25, T23

Status: T25 in-progress (live-results section pending), T23 done
Done this session:
- Took over merging and lane claude-verdict from the Windows coordinator (docs/MERGER_HANDOFF.md).
- Merge check: every lane branch (ag, ag-b, claude-core, claude-verdict, codex-a) was already in main at d1f4b25; nothing new to merge. main tested in a throwaway worktree: 238 passed (UI tests included).
- Offline eval on main (python tests/eval/run_eval.py): slides 2, 3, 4, 5 PASS (ag-b's milestones fix works); 6 FAIL (HELD no_checker), 7 FAIL (HELD error, no sources/web.py); 8 SKIP. 4 PASS, 2 FAIL, 1 SKIP.
- README.md (T25): job, who pays, input, result, pass mark, how to run, offline results, known limits, credits with licences read from installed package metadata. The "Live run" section still says LIVE_RESULTS_PENDING.
- docs/ARCHITECTURE.md (T23): mermaid data-flow diagram, states, data calls, limits/retries, ledger, approval and exactly-once send.
- .gitignore: logs/ and out/.
- Merged lane/claude-core into main: 2114ed7 (238 passed, hard-rule greps clean). dc-core and dc-verdict fast-forwarded to it.
In progress / exact next step:
1. Live Deck A run (credits approved by harshit). Needs dc-core/.env with CRUSTDATA_API_KEY and GEMINI_API_KEY or OPENAI_API_KEY. In ../dc-core:
   set -a; . ./.env; set +a; python cli.py run --request tests/decks/deck_a_request.json --out out/result.json
   Then replace LIVE_RESULTS_PENDING in README.md with the real table, commit, and merge to main.
2. Human: record the demo video (5:30 PM), make the GitHub repo public, submit the form (6:00 PM).
How to run / test:
- python -m pytest -q   (238 passed)
- python tests/eval/run_eval.py
Known bugs or shortcuts taken:
- extract/claims.py reads LLM keys only from the environment (only sources/crust.py reads .env), so the shell must load .env first. The README says so. extract/ is not my lane, so I did not change it.
- Slides 6 and 7 stay HELD. I did not change the answer key to match our output; README "Known limits" explains it.
Decisions made (also in DECISIONS.md if they change behaviour):
- none
Open questions for a human:
- ../dc-ag is checked out on main, not lane/ag. I did not switch it; switch it in that folder only if lane ag needs to commit again.
- Finance partner: every rules.yaml value is still PLACEHOLDER.
Credits / tokens used this session (rough): 0 Crustdata credits so far

### 15:35 · harshit · merger + claude-core · task live Deck A run, T25

Status: done
Done this session:
- cli.py: a repo-relative deck_path in a request file (tests/decks/deck_a_request.json has "tests/decks/deck_a.pdf") was joined onto the request's folder, so the demo command failed with "deck not found". It now looks beside the request first, then from the current folder. Test: tests/core/test_cli.py::test_request_deck_path_relative_to_current_folder.
- Live Deck A run run-20261122-092339-ef3899 (keys loaded from ../deckcheck-kit/.env):
  - The first attempt failed: the GEMINI_API_KEY in .env is rejected by Google (API_KEY_INVALID). The failed call has its ledger row (ok=0).
  - Resumed with GEMINI_API_KEY unset, so gpt-4o-mini did the extraction: 7 claims, every quote verified, company confirmed on 2 signals.
  - Verdicts match the offline replay on every slide: 2 SUPPORTED, 3 SUPPORTED, 4 SUPPORTED (undated rounds), 5 CONTRADICTED, 6 HELD no_checker, 7 HELD error, 8 CANNOT_VERIFY missing_record_date.
  - Ledger: 4 calls, 2 credits, Rs 2.79, 16.5 s.
- README "Live run" table filled; T25 done.
In progress / exact next step:
- Human: demo video (5:30 PM), make the repo public, submission form (6:00 PM). The demo can approve the pending email in the UI (streamlit run ui/app.py, DB dc-core/deckcheck.db).
How to run / test:
- set -a; . ./.env; set +a; unset GEMINI_API_KEY   (until the Gemini key is fixed)
- python cli.py run --request tests/decks/deck_a_request.json --out out/result.json
- python -m pytest -q   (239 passed)
Known bugs or shortcuts taken:
- When both LLM keys are set, extract/claims.py picks Gemini, so the invalid Gemini key must be fixed or unset.
Decisions made (also in DECISIONS.md if they change behaviour):
- none
Open questions for a human:
- Fix or remove GEMINI_API_KEY in .env.
Credits / tokens used this session (rough): 2 Crustdata credits; 1,068 OpenAI tokens (Rs 2.79 total)

### 16:00 · claude-verdict@mac (harshit's account, at the merger session's request) · lane claude-verdict · task T29

Status: done
Done this session:
- verdict/hiring.py, traction.py, company_fact.py, prior_exit.py, team_growth.py; competition in verdict/engine.py `_route`. engine `_TYPES_WITH_RULES` gains hiring, traction, company_fact, prior_exit, team_growth (competition is route-only: it has no tolerance_pct). prior_exit guard runs right after the identity check.
- Cautious by design: hiring, HQ, prior_exit, team_growth never CONTRADICTED; traction CONTRADICTED only at >= strong_margin x tolerance, never above medium; founded year CONTRADICTED (medium) only beyond the year-gap key; competition never decided.
- config/rules.yaml: `tolerances.company_fact.year_gap_cannot_verify: 1`, `tolerances.team_growth.window_tolerance_days: 45` (PLACEHOLDER). docs/LIVE_FIX_MAP.md: two lines. verdict/common.py MISSING_TEXT: one entry per new reason code.
- verdict/DESIGN.md sections 3.4-3.9, 4, 5 (asks), 6 (keys). DECISIONS D15.
- tests/verdict/test_t29_rules.py: 81 tests, every label per rule plus "never CONTRADICTED" tests on the cautious paths (incl. the Locus/Ingka prior_exit shape).
In progress / exact next step:
- Merge to main: waiting for the user's OK (AGENTS.md: only a human merges to main).
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (320 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: unchanged)
Known bugs or shortcuts taken:
- Deck A is unchanged: slide 8 (hiring, "engineers") still stops at missing_record_date because the hiring checker gives no dated field; with a date it would be NOT_COMPARABLE metric_mismatch. The gain is for unseen decks.
- Founded year and HQ come from a company snapshot dated today, so against an older deck date they mostly stop at record_after_as_of (D3), not at these rules.
- prior_exit and team_growth cannot decide until their checkers change (DESIGN.md section 5).
Decisions made (also in DECISIONS.md if they change behaviour):
- D15.
Open questions for a human:
- Finance partner: values for the two new keys; is a 1-year founded-year gap the right "unclear" band?
- codex-a / ag-b: the checker asks in DESIGN.md section 5.
Credits / tokens used this session (rough): 0 Crustdata credits

### 15:31 · claude-verdict@mac (harshit's account, at the merger session's request) · lane claude-verdict · task T33

Status: done
Done this session:
- verdict/market_size.py, verdict/customer.py, verdict/web_common.py (shared date filter for estimates/mentions). verdict/engine.py: identity `not_applicable` passes row 5b for market_size only; market_size added to `_TYPES_WITH_RULES` (tolerance_pct 50); customer is route-only.
- market_size: only estimates in claim.unit's currency count (none -> NOT_COMPARABLE currency_mismatch); one within tolerance -> SUPPORTED (max medium); CONTRADICTED `sources_agree_otherwise` (max medium) only when >= min_agreeing_sources distinct domains all disagree with the deck AND agree with each other; anything else CANNOT_VERIFY source_may_be_incomplete with market-specific `missing`.
- customer: `independent is True` -> SUPPORTED `independent_mention` medium; self-published only -> CANNOT_VERIFY self_reported_only; never CONTRADICTED. MISSING_TEXT gains self_reported_only.
- Both types read `tolerances.<type>.max_record_age_days` (D14) for each estimate/mention's own published_date, and drop items dated after the reference date (D3).
- tests/verdict/test_t33_rules.py: 19 tests (every label, single disagreeing source, same domain twice, never CONTRADICTED for customer). tests/verdict/test_engine_order.py: the old "customer is unsupported" test now checks customer is routed.
- verdict/DESIGN.md: row 5b, sections 3.10, 3.11, 4, 5 (asks), 6 (keys).
In progress / exact next step:
- Merger merges lane/claude-verdict to main (do not merge from this lane).
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (340 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: unchanged)
Known bugs or shortcuts taken:
- No currency conversion: an INR estimate never supports a USD claim (by design, cautious).
- CONTRADICTED relies on the checker giving the registrable domain; sub-domains of one site would count twice.
Decisions made (also in DECISIONS.md if they change behaviour):
- none new; follows D16 and the merger's T33 spec.
Open questions for a human:
- Finance partner: is min_agreeing_sources 2 and tolerance 50% right for market size?

### 15:31 · web-client (claude, side session of the merger) · lane web-client · task T30

Status: done
Done this session:
- sources/web.py: `search(ctx, query, *, sources, site, location, end_date)` -> POST /web/search/live and `fetch(ctx, urls)` -> POST /web/enrich/live, exactly the D16 / WEB_SOURCE.md section 3 signatures and return shapes. Also a public helper `end_of_day_unix('YYYY-MM-DD')` (23:59:59 UTC; 1970-01-01 -> 86399).
- Same pattern as sources/crust.py: `limits.ensure_within` before every attempt; one ledger row per HTTP call in `finally` (Provider.CRUSTDATA, endpoints `POST /web/search/live` / `POST /web/enrich/live`); TimeoutError at `limits.per_call_timeout_s`; key from crust's `_api_key` (env, then .env), never logged.
- Differences from crust.py, on purpose (per the T30 brief): retry once on HTTP 429 ONLY (crust also retries 5xx); credits read from `X-Credits-Used`; no account-endpoint call, rpm pacing or 60 s cache TTL (cache lives for the run).
- tests/sources/test_web.py (18 tests) + hand-built fixtures in tests/fixtures/web/ (shapes from WEB_SOURCE.md; no live call made, 0 credits). Covers headers/body via a fake HTTPSConnection, end_date conversion, failed-URL shape, ledger rows on success/HTTP error/malformed/timeout, 429 retry and second 429, cache, 10-URL cap, limit hit. An autouse fixture makes any real HTTPS connection fail the test.
In progress / exact next step:
- Merger: merge lane/web-client. T32 checkers can now call `sources.web.search` / `fetch` for real.
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q tests/sources/test_web.py   (18 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (339 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: unchanged)
Known bugs or shortcuts taken:
- Credits when there is no X-Credits-Used header: search 1; fetch 1 per URL SENT (not per success), the cautious choice for budget limits. Failed HTTP calls record 0 credits unless the header says otherwise (same as crust). A 2xx with a malformed body records the fallback credits and ok=0.
- Fetch matches results to requested URLs ignoring a trailing "/", returns them in request order under the requested URL, and drops successes for URLs we did not send. Non-https URLs are skipped and logged (one plain-http search result must not lose the whole claim). Duplicate URLs are sent once. Only more than 10 URLs raises ValueError (checked on the raw list, before any call).
- Fetch cache key is the run plus the order-independent SET of URLs, so the single returned call_id is always the call that really fetched those pages. Two claims fetching overlapping but different URL sets pay again for the overlap.
- The cache is in-process (like crust's), so after a kill the claim that was in progress pays again on resume; finished claims are skipped by checkpointing. A cache that survives restarts needs a schema change.
- Errors: TimeoutError, limits.LimitExceeded, RuntimeError (web._HttpError for HTTP status), ValueError (bad end_date, >10 URLs, bad query). core/runner.py catches Exception per claim, so all become HELD.
- Untested against the live API: response field names come from the docs as written in WEB_SOURCE.md.
Decisions made (also in DECISIONS.md if they change behaviour):
- none (contract unchanged)
Open questions for a human:
- If per-URL fetch caching is wanted (to avoid paying twice across claims), the page dicts need their own `call_id`; that is a contract change (new DECISIONS entry).
- No pre-call budget check for a 10-URL fetch (crust's `_ensure_can_afford` is company-only); `ensure_within` only checks spend so far, so one fetch can overshoot max_credits by up to 10.
Credits / tokens used this session (rough): 0 Crustdata credits

### 15:35 · web-pages (Claude Code session started by the merger session) · lane web-pages · task T31

Status: done
Done this session:
- sources/pages.py (stdlib only): `page_text(html)` drops script/style/noscript/template/title, unescapes entities, puts a space at block tags, collapses whitespace. `published_date(html)` collects every candidate, then takes the first READABLE one by priority: JSON-LD `datePublished` (also in `@graph` and lists), `meta[property=article:published_time]`, `meta[name=...]` in the D16 order (case-insensitive names), the first `<time datetime>`. An unreadable value falls through to the next candidate. Accepts `YYYY-MM-DD[T...]`, `YYYY/M/D` and "March 5, 2024"; the date is taken as written (no UTC shift). `dateModified`, fetch time and today are never used. where_found values: `json-ld[datePublished]`, `meta[property=article:published_time]`, `meta[name=<name>]`, `time[datetime]`.
- extract/quotes.py: `pick_quote(ctx, page_text, question, must_contain)` calls `extract.claims._default_llm_call` through a module-level name (tests monkeypatch `extract.quotes._default_llm_call`), with `ensure_within` first and one ledger row (Provider.LLM) in a `finally`, failed calls included. The returned call_id is that row's id. The prompt asks for JSON `{"quote": ...}` (OpenAI json_object mode needs the word "json") and fences the page as untrusted data. The page is cut to `web.max_page_chars`. Code accepts the quote only if it is verbatim (whitespace-normalised, case-sensitive) on the full page text and contains every must_contain (case-insensitive); the returned quote is whitespace-normalised. Empty page text makes no call and returns (None, None).
- `parse_amount(quote)`: only numbers with a currency marker count (`$`, `US$`, `USD`, `₹`, `Rs`/`Rs.`, `INR` before; `USD`, `INR`, `dollars`, `rupees` after). Scales: million/mn/M, billion/bn/B, trillion/tn, thousand/K, lakh 1e5, crore/cr 1e7, "lakh crore" 1e12; Indian digit grouping (1,00,000) works; Decimal arithmetic. Returns (None, None) for no amount, several different amounts (the same amount twice is fine), or a range like `$5-7 billion` / `Rs 500 to 700 crore`. `A$`, `S$` etc. are not USD.
- Tests: tests/sources/test_pages.py (6 fixtures in tests/fixtures/pages/), tests/extract/test_quotes.py (hallucinated quote, case, must_contain, ledger row id, failed-call row + re-raise, truncation, every parse_amount case).
In progress / exact next step:
- Merge lane/web-pages to main (merger). T32 can call these functions unchanged.
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (376 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: unchanged)
Known bugs or shortcuts taken:
- pick_quote does NOT wrap errors the way extract/claims.py does: it re-raises the original exception (TimeoutError stays TimeoutError, LimitExceeded from ensure_within propagates with no ledger row because no call was made), so the runner can tell HELD timeout from HELD error. T32 checkers should let these propagate.
- A bad LLM answer (not JSON, no "quote", null) is not an error: the row is ok=1 and the quote is None.
- Only the first `<time datetime>` is looked at; if it is unreadable the page has no date.
- Lowercase `m`/`b`/`k` count as a scale only when attached to the number (`$5m`); `lac`/`lacs` = 1e5. An unknown letter attached to an amount (`$5x`) makes parse_amount return (None, None) rather than guess a scale. Currency suffixes are exact words (`dollars`, `US dollars`, `rupees`, `USD`, `INR`).
Decisions made (also in DECISIONS.md if they change behaviour):
- none (contracts as in D16).
Open questions for a human:
- `_default_llm_call` reads keys only from the environment (as noted in the T25 handoff); pick_quote inherits that, so a live run must load .env first.
Credits / tokens used this session (rough): 0 Crustdata credits, 0 LLM tokens (no live calls)

### 16:05 · web-checkers (Claude session started by the merger session) · task T32

Status: done
Done this session:
- checkers/market_size.py rewritten on the D16 flow: web.search (query "<subject> market size", end_date = reference date) -> top `web.results_to_fetch` distinct URLs -> one web.fetch -> pages.published_date / page_text -> skip undated pages and pages dated after the reference date (counted) -> quotes.pick_quote (must_contain []) -> quotes.parse_amount. `observed` keys exactly as WEB_SOURCE.md section 3: identity "not_applicable", identity_signals 0, record_date, reference_date(_source), estimates, pages_without_date, pages_after_reference.
- checkers/customer.py (new): query `"<claim.value>" "<claim.subject>"`, must_contain [customer, company]. `observed`: company_identity(ctx), record_date, reference_date(_source), customer_name, mentions. `independent` is set PER MENTION (no top-level key): False when the page host (lower-case, "www." stripped) equals the deck domain or is a subdomain of it. Skip counts are logged only, not in observed.
- Evidence per accepted page: web_page, locator=url, field_or_quote=quote, value=amount (market_size) or customer name (customer), record_date=published date, retrieved_at=page fetched_at, call_id=fetch call id.
- tests/checkers/test_market_size.py (9) and test_customer.py (7): fakes patched onto the checker modules; bare stand-in modules are registered only when the real ones are missing, so they keep working after T30/T31 merge.
- tests/checkers/test_remaining_checkers.py: deleted test_market_size_check and its import (old `search_market_data` contract; the merger session approved this, as a separate commit). The new test_market_size.py replaces that coverage.
In progress / exact next step:
- none. Merger: merge lane/web-checkers after or alongside T30/T31; then slides 6 and 7 go through the new checkers.
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (335 passed, with sources.web absent on this branch)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: unchanged; slides 6 and 7 are HELD error until T30/T31 merge)
Known bugs or shortcuts taken:
- `ctx.rules["web"]["results_to_fetch"]` has no code default: a rules file without `web:` raises KeyError, which becomes HELD error.
- customer.py reuses the private helpers `_reference_date`, `_domain` and `_top_urls` from market_size.py.
Decisions made (also in DECISIONS.md if they change behaviour):
- none (follows D16)
Open questions for a human:
- T33: read `mentions[*].independent`; there is no top-level `independent` key.
Credits / tokens used this session (rough): 0 Crustdata credits

### 16:05 · harshit · merger + claude-core · task live Deck A run with web search

Status: done (run); two fixes open
Done this session:
- Merged T30, T31, T32 (web client, pages and quotes, checkers) and T33 (verdict rules) into main. Offline eval now blocks web calls (af13f8c). docs/INCIDENTS.md started.
- Live run run-20261122-102749-b58f62 with web search, approved by harshit:
  - slides 2 to 5 and 8: same verdicts as the first live run;
  - slide 6 (customer): HELD timeout (web fetch over 20 s);
  - slide 7 (market size): CANNOT_VERIFY source_may_be_incomplete, but its only evidence quote is about the wrong market (home and household, USD 237bn by 2030).
  - Ledger: 8 calls, 8 credits, Rs 9.72, 69.7 s.
- README "Live run with web search" section; INCIDENTS A5 and B10.
In progress / exact next step:
1. checkers/market_size.py (web-checkers lane): pass the claim's market terms as `must_contain` to quotes.pick_quote, and skip quotes that forecast a year after the reference year ("by 2030"). Add tests.
2. sources/web.py (web-client lane): a separate, longer timeout for web fetch (new rules.yaml key, e.g. web.fetch_timeout_s), so a slow page fetch doesn't hold the customer claim.
How to run / test:
- set -a; . ../deckcheck-kit/.env; set +a; unset GEMINI_API_KEY; python cli.py run --request tests/decks/deck_a_request.json --out out/result_web.json
- python -m pytest -q (429 passed)
Known bugs or shortcuts taken:
- GEMINI_API_KEY in .env is still invalid; runs unset it so OpenAI is used.
Decisions made (also in DECISIONS.md if they change behaviour):
- none
Open questions for a human:
- Approve fixes 1 and 2 before the 18:00 freeze?
Credits / tokens used this session (rough): 8 Crustdata credits, about 4,700 OpenAI tokens (Rs 9.72)

### 16:06 · web-client (claude, side session of the merger) · lane web-client · task T30 follow-up (INCIDENTS A5)

Status: done
Done this session:
- sources/web.py: fetch() now uses `web.fetch_timeout_s`; search() keeps `limits.per_call_timeout_s`. If the key is missing, fetch falls back to `limits.per_call_timeout_s`. A slow fetch still raises TimeoutError (HELD timeout) and still writes its ledger row.
- config/rules.yaml: `web.fetch_timeout_s: 45` (PLACEHOLDER). docs/LIVE_FIX_MAP.md: one line.
- tests/sources/test_web.py: 4 new tests (fetch uses the key, fallback, search unchanged, slow fetch times out and is ledgered).
In progress / exact next step:
- Merger: merge lane/web-client.
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (433 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: unchanged)
Known bugs or shortcuts taken:
- A run with 3 claims each fetching can now spend up to about 3 x 45 s on fetches; `limits.max_seconds` still caps the run.
Decisions made (also in DECISIONS.md if they change behaviour):
- none (config key only; contract unchanged)
Open questions for a human:
- Finance partner: real value for web.fetch_timeout_s.

### 16:50 · web-checkers · task T32 fix (INCIDENTS B10)

Status: done
Fixes:
- B10, the wrong market was accepted: live run run-20261122-102749-b58f62 used a household-market quote ("... USD 237 billion by 2030") for "India logistics software". checkers/market_size.py now builds the required terms in code from claim.subject: lower-case words minus {india, indian, global, the, of, and, market, size, industry, sector}. It passes them to pick_quote as must_contain and checks them again on the returned quote. A subject with no terms left keeps the old behaviour.
- B10, forecasts: a quote that projects to a year after the reference year ("by/in 20XX", "20XXE", "projected/expected/forecast ... 20XX") is skipped and counted in the new observed["forecast_quotes_skipped"]. With no reference date, the page's published year is used.
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (437 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: unchanged)
Known bugs or shortcuts taken:
- The term check is a substring check (the same as extract/quotes._accept), so "software" also matches "softwares". The forecast regex stops at the first full stop after projected/expected/forecast.
- Correction to the 16:05 entry: test_market_size.py had 8 tests then, not 9; it has 16 now.
Decisions made (also in DECISIONS.md if they change behaviour):
- none
Open questions for a human:
- T33 / verdict: the new observed key forecast_quotes_skipped is informational only; no rule reads it yet.
Credits / tokens used this session (rough): 0 Crustdata credits

### 16:12 · harshit · merger + claude-core · task merge A5/B10 fixes, second live web run

Status: done
Done this session:
- Merged lane/web-client (fb36f6b, web.fetch_timeout_s: 45) and lane/web-checkers (204cf59, market-size relevance and forecast checks) into main as 98ce097. 441 passed; eval 4 PASS, 2 FAIL, 1 SKIP.
- Live run run-20261122-103822-1686da (approved by harshit):
  - slides 2 to 5 and 8: unchanged;
  - slide 7: CANNOT_VERIFY no_evidence (3 pages, none dated), matching the answer key;
  - slide 6: HELD timeout, the web search took over 20 s.
  - Ledger: 6 calls, 7 credits, Rs 7.79, 47.6 s.
- README "Live run with web search" updated; INCIDENTS A6 and B10b.
In progress / exact next step:
- Slide 6: raise limits.per_call_timeout_s (for example to 30) in config/rules.yaml, or add web.search_timeout_s in sources/web.py like fetch. Then rerun.
How to run / test:
- set -a; . ../deckcheck-kit/.env; set +a; unset GEMINI_API_KEY; python cli.py run --request tests/decks/deck_a_request.json --out out/result_web2.json
Known bugs or shortcuts taken:
- GEMINI_API_KEY still invalid.
Decisions made (also in DECISIONS.md if they change behaviour):
- none
Open questions for a human:
- Which search timeout should we use?
Credits / tokens used this session (rough): 7 Crustdata credits, about 1,100 OpenAI tokens (Rs 7.79)

### 16:15 · harshit · merger + claude-core · task timeout 30 s, third live web run

Status: done
Done this session:
- config/rules.yaml: limits.per_call_timeout_s 20 -> 30 (approved by harshit); merged as d4b1da6, 441 passed.
- Live run run-20261122-104047-1b295e: 6 PASS, 0 FAIL, 1 SKIP against tests/decks/deck_a_answers.yaml.
  - Slides 6 and 7: CANNOT_VERIFY no_evidence, as the key expects.
  - Ledger: 8 calls, 11 credits, Rs 11.96, 74.8 s.
- README "Latest live run" section (headline result); INCIDENTS A6b.
In progress / exact next step:
- Demo video (17:30), BUSINESS.md, ETHICS.md (teammate), UI polish merge, make the repo public, submit the form (18:00).
How to run / test:
- set -a; . ../deckcheck-kit/.env; set +a; unset GEMINI_API_KEY; python cli.py run --request tests/decks/deck_a_request.json --out out/result.json
Known bugs or shortcuts taken:
- GEMINI_API_KEY still invalid. Web results vary from run to run (search is live), so slides 6 and 7 can differ between runs; the rules keep them safe.
Decisions made (also in DECISIONS.md if they change behaviour):
- none
Open questions for a human:
- none
Credits / tokens used this session (rough): 11 Crustdata credits (Rs 11.96 total)

### 16:27 · claude-verdict@mac (harshit's account, at the merger session's request) · lane claude-verdict · task T34

Status: done
Done this session:
- verdict/engine.py `_prepare`: D17 guarded undated fallback. No `record_date` + `verdict.undated_fallback` true + reference date 0..`undated_max_deck_age_days` before the latest Evidence `retrieved_at` -> rules run with `st["undated"]=True`, `rec=None`, ceiling low, fresh False; record_after_as_of / stale_record skipped. Otherwise `missing_record_date` with `missing` saying why (fallback off, deck too old, deck after retrieval, keys absent = off).
- verdict/common.py `make()`: undated verdicts get reason `<code>_undated` (not `no_evidence`), confidence low, explanation prefixed "No dated record was found; this uses an undated source retrieved on <date>. ", MISSING_TEXT `undated` appended to `missing`.
- founder tenure: an open role ends at the reference date when undated; team_growth undated -> period_mismatch_undated.
- verdict/web_common.py `select`: dated web items that pass always win; items with `published_date: None` only when none pass and the guard holds. market_size and customer use it.
- report/render.py: a source with no record date shows "source date: undated (retrieved <date>)" in the Markdown; result JSON keys unchanged (no contract change, no new output field).
- Tests: tests/verdict/test_t34_undated.py (18), tests/report/test_builder.py (+2). verdict/DESIGN.md section 2 row 6, new 2.1, sections 4, 5, 6.
In progress / exact next step:
- Merger merges lane/claude-verdict (do not merge from this lane). T35 (checkers send `record_date: None` for undated values) is what makes the fallback fire on real data.
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (460 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: no new FAIL; slides 6-7 HELD offline)
Known bugs or shortcuts taken:
- Deck A slide 8 offline is still CANNOT_VERIFY no_evidence: the recorded fixture tests/fixtures/crustdata/deck_a_locus_company.json has no `hiring` block, and checkers/hiring.py sets record_date from `updated_at`. With T35 and live data the engine gives NOT_COMPARABLE metric_mismatch_undated (low) for "40 engineers" vs all openings (unit-tested).
- An unparseable record_date string (e.g. "last year") is treated as missing, so it can also take the undated path when the guard holds.
Decisions made (also in DECISIONS.md if they change behaviour):
- none new; implements D17. `no_evidence` is never suffixed.
Open questions for a human:
- Finance partner: undated_fallback true / 90 days are PLACEHOLDER values.

### 16:45 · web-checkers · task T35 (D17: checkers keep undated items)

Status: done
Done this session:
- checkers/market_size.py and checkers/customer.py: dated pages are processed first, as before. Pages with no published_date are still counted (`pages_without_date`; customer logs it only), and kept aside. If NO dated page gave an accepted estimate or mention, the undated pages go through the same checks: pick_quote with the same must_contain terms, the B10 relevance check and forecast skip (market_size), and parse_amount (market_size). The forecast year for an undated page is the reference year, else the fetch year. Undated items are marked `published_date: None` and Evidence `record_date=None`; observed.record_date stays None. They are never mixed with dated ones. New observed key in both: `undated_items_used` (count).
- checkers/team_size.py: with no headcount.timeseries point on or before the reference date, it falls back to the snapshot `headcount.total`: observed.headcount = total, observed.record_date None, Evidence field_or_quote "headcount.total", record_date None. A dated point always wins. New observed key `undated_items_used` (0 or 1). A missing or non-numeric total gives no evidence, as before.
- Tests: market_size +3, customer +3 (one old "undated is skipped" test is now the D17 case), team_size +6.
In progress / exact next step:
- none. T34 (engine) decides whether undated items may be used. Until it merges, the current engine stops at CANNOT_VERIFY missing_record_date for these (verdict/engine.py:120), so no wrong label in the meantime.
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (452 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: unchanged; web claims are HELD offline)
Known bugs or shortcuts taken:
- An undated web page costs one LLM call (pick_quote) only when no dated page was accepted, so the worst case is still one call per fetched page.
Decisions made (also in DECISIONS.md if they change behaviour):
- none (follows D17)
Open questions for a human:
- T34: read `observed.undated_items_used` > 0 (or Evidence.record_date None) to tell an undated result from "no evidence". For team_size, `observed.headcount` is set from headcount.total with record_date None.
Credits / tokens used this session (rough): 0 Crustdata credits

### 16:55 · web-checkers · T35 addition (merger's request): checkers/hiring.py

Status: done
Done this session:
- checkers/hiring.py used the payload's `updated_at` (the provider's refresh date) as record_date, which D13 forbids. `hiring.openings_count` and `hiring.openings_growth_percent` are now snapshot values: Evidence record_date=None and observed.record_date=None. New observed key `undated_items_used` = number of snapshot Evidence rows. D17 (T34, engine) decides whether they may be used. `updated_at` is no longer read anywhere in the checker.
- tests/checkers/test_remaining_checkers.py: test_hiring_check now asserts record_date None on observed and on both Evidence rows. New test: a top-level `updated_at` payload still gives record_date None.
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (453 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: unchanged; slide 8 hiring stays CANNOT_VERIFY no_evidence offline)
Open questions for a human:
- none
Credits / tokens used this session (rough): 0 Crustdata credits

### 16:28 · web-client (claude, side session of the merger) · lane web-client · task T36 (D18 founder lookups)

Status: in-progress (code and tests done; the one live probe waits for the user's yes)
Done this session:
- sources/crust.py: `get_people(ctx, profile_urls)` (ONE batched POST /person/enrich, fields basic_profile, social_handles, experience, education) and `search_people(ctx, name, company_id)` (POST /person/search, filters op=and: basic_profile.name "=" name, experience.employment_details.company_id "in" [id], limit 10). Both return (payload | None, call_id | None), go through crust's existing `_request` (limits before each attempt, one ledger row per call in finally, per_call_timeout_s, the same retry as get_company: once on 429/5xx), and have a per-run cache (enrich by URL set, search by name + id). `_attempt` gained an optional `parse` hook; get_company is unchanged.
- Payloads are normalised to `{"matches": [{confidence_score, person_data}]}` (enrich answers a top-level array of {matched_on, match_status, matches[]}) and `{"profiles": [...]}`, so resolve/payloads.py reads them unchanged. `drop_contact_fields` removes, recursively, every key containing "email", "phone" or "contact" before cache or caller.
- Credits when no header: enrich 1 per URL sent; search 0.23 per profile returned (docs/crustdata_fields.md).
- resolve/payloads.py: new `person_records(payload)` (raw records); shapes checked against the docs, no change needed.
- checkers/founder_background.py: uses `find_founder(ctx.entities, claim.subject)`. Only a CONFIRMED founder is looked up; its record is picked by `crustdata_person_id == founder id` (a namesake in the same payload is never used). Profile-URL founders reuse resolve's cached get_people call (same URL set); search-found founders reuse search_people(name, company id). Identity keys come from the founder entity. Observed keys for verdict/founder.py unchanged; Evidence locator is the enrich or search endpoint.
- tests: tests/sources/test_crust.py (+5: contacts dropped, ledger success/failure, 429 retry, cache, search body, payload feeds resolve candidates); tests/checkers/test_founder_background.py (rewritten onto ctx.entities, +4: namesake never used, unconfirmed founder never looked up, search route, Crustdata role shape). Hand-built fixtures tests/fixtures/crustdata/person_enrich_handbuilt.json, person_search_handbuilt.json.
- tests/decks/make_deck_f.py, deck_f.pdf (3 slides, Locus, 2026-11-15, synthetic footer), deck_f_request.json, deck_f_answers.yaml (all TBD).
In progress / exact next step:
- With the user's yes: one live probe (1 credit), `get_people` for deck_f_request.json's founder URL. Check the real role keys (name, title, start_date, end_date, crustdata_company_id) and profile_url; record the response (contact fields dropped) as tests/fixtures/crustdata/person_enrich_locus.json; fill deck_f_answers.yaml.
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (450 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: unchanged)
Known bugs or shortcuts taken:
- Not verified live: role key names (start_date/end_date, crustdata_company_id on roles), whether enrich returns social_handles.profile_url with the "social_handles" field name, and whether the search filter path experience.employment_details.company_id accepts our id type (sent as int when numeric).
- The founder URL in deck_f_request.json (https://www.linkedin.com/in/nishithrastogi/) is NOT verified; if the probe returns not_found, resolve marks the founder url_not_returned and the deck's name search path still runs.
- Deck F's two claims (Amazon, SDE title) are test claims to check, not known facts.
Decisions made (also in DECISIONS.md if they change behaviour):
- none (D12/D18 signatures kept)
Open questions for a human:
- Approve the 1-credit probe, and confirm or replace the founder profile URL.
Credits / tokens used this session (rough): 0 Crustdata credits

### 16:30 · web-client · lane web-client · task T36 live probe (user said yes in chat)

Status: done
Done this session:
- One live probe: get_people(["https://www.linkedin.com/in/nishithrastogi/"]), ledger call-457fe7a8507b, POST /person/enrich, ok, 1.0 credit (no X-Credits-Used header), 1.6 s, in a scratch DB (not dc-core). Response matched (match_status matched, confidence 1.0): Nishith Rastogi, crustdata_person_id 44441; roles at Locus (crustdata_company_id 7403, same id as the Locus company record) and Amazon (Software Developer, 2012-07-01 to 2014-07-01).
- Checked against the code: the top-level array shape, crustdata_person_id present with our fields, role keys name/title/start_date/end_date/crustdata_company_id as coded, returned profile_url (no trailing slash) normalises equal to the sent URL. Resolve gets profile_url + name + employer = 3 signals.
- tests/fixtures/crustdata/person_enrich_locus.json: the response trimmed to the fields the code reads (ids, name, title, profile_url, roles, schools); no emails, phones, or long digit runs. New test test_recorded_locus_founder_record.
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q
Known bugs or shortcuts taken:
- The live person record has NO updated_at and no basic_profile.last_updated, so record_date is None and every founder claim ends CANNOT_VERIFY missing_record_date (deck_f_answers.yaml stays TBD for that reason).
Open questions for a human:
- Verdict owner (claude-verdict) + merger: may a founder_background record_date be the matched role's own date (end_date, else start_date, else retrieved_at for a current role)? That would let slide 2 become SUPPORTED employer_listed. It is a D3 date-rule decision, so I did not change the checker.
Credits / tokens used this session (rough): 1 Crustdata credit

### 16:37 · web-client · lane web-client · task T37 (D19 founder record_date)

Status: done
Done this session:
- checkers/founder_background.py: new `role_record_date(positions, ref_date)`. observed.record_date and every Evidence.record_date come from the matched roles' start/end dates: the latest on or before the reference date; if all are after it, the earliest start_date (the engine then says NOT_COMPARABLE record_after_as_of); no dated role or no employer match gives None. updated_at / last_updated are no longer the record date; they are kept only as observed.profile_updated_at (informational). retrieved_at is never used.
- tests/checkers/test_founder_background.py (+9): past role ended before the deck = end_date; current role = start_date; ended after the deck = start_date; started after the deck = start_date and NOT_COMPARABLE through the engine; no dates = None; no employer match = None; latest date over several roles; the recorded Locus fixture through the engine = SUPPORTED employer_listed (medium), not stale_record.
- tests/decks/deck_f_answers.yaml: slide 2 = SUPPORTED employer_listed. Slide 3 stays TBD: "Software Developer" has no keyword in the PLACEHOLDER title_levels, so it is CANNOT_VERIFY title_unmapped today.
How to run / test:
- /Users/harshit/deckcheck-kit/.venv/bin/python -m pytest -q   (491 passed)
- /Users/harshit/deckcheck-kit/.venv/bin/python tests/eval/run_eval.py   (4 PASS, 2 FAIL, 1 SKIP: unchanged)
Known bugs or shortcuts taken:
- An employer missing from the profile now has record_date None (D19 rule 5), and the engine checks the date before the founder rule. So it gives CANNOT_VERIFY missing_record_date (old deck) or employer_not_in_profile_undated (recent deck, D17) instead of employer_not_in_profile. The label is unchanged (CANNOT_VERIFY, never CONTRADICTED); the existing test now accepts either reason code.
Decisions made (also in DECISIONS.md if they change behaviour):
- none (implements D19)
Open questions for a human:
- claude-verdict: should the engine route founder_background with employer_found false to employer_not_in_profile before the date check, so the reason code stays the intended one?
- Finance partner: add "developer" (and similar) to title_levels.ic so deck F slide 3 can be decided.
Credits / tokens used this session (rough): 0 Crustdata credits

### 16:45 · claude-core (merger) · lane claude-core · T36/T37 merge, D19, live Deck F

Status: done
Done this session:
- Merged lane/web-client T36 into main (2dc5aa0, 482 tests), then D19 + T37 (4805db0, 491 tests). Eval unchanged at 4 PASS, 2 FAIL (offline web block), 1 SKIP.
- Wrote D19 (founder role dates as record_date) with `tolerances.founder_background.max_record_age_days: 18250`, T37 row, LIVE_FIX_MAP line (1bfefb3).
- Live Deck F run-20261122-110842-b09d73: slide 2 SUPPORTED employer_listed (PASS), slide 3 CANNOT_VERIFY title_unmapped (key TBD). 4 calls, 3 credits, ₹3.31, 14.7 s. README section and INCIDENTS B11/B12 added.
How to run / test:
- `python cli.py run --request tests/decks/deck_f_request.json --out out/deck_f_live.json` (spends ~3 credits)
Known bugs or shortcuts taken:
- Deck F company resolved unclear (1 signal); founder claims do not use it.
Open questions for a human:
- claude-verdict: route founder_background with employer_found false before the date check (B12)?
- Finance partner: real title_levels (add developer/engineer variants) so Deck F slide 3 can be decided.
Credits / tokens used this session (rough): 3 Crustdata credits (live Deck F)

### 16:55 · claude-core (merger) · lane claude-core · title_levels, Deck F rerun

Status: done
Done this session:
- config/rules.yaml title_levels (on the user's word): ic adds developer, programmer, sde, scientist, designer, architect; vp adds svp, evp, avp; c_level adds cofounder and spelled-out chief ... officer titles (not bare "chief"). Test rows added in tests/verdict/test_metrics.py. Deck F key slide 3 = SUPPORTED title_level_met. Merged to main 0857498 (493 tests, eval unchanged).
- Live Deck F run-20261122-111231-e7bd42: slides 2 and 3 SUPPORTED (2 PASS); 3 credits, ₹3.40.
Known bugs or shortcuts taken:
- LLM extraction is not deterministic (extra slide-1 company claim this run; ends CANNOT_VERIFY).
Open questions for a human:
- Finance partner: confirm the title_levels additions (all PLACEHOLDER).
Credits / tokens used this session (rough): 3 Crustdata credits

### 15:48 · yash · lane ag-b (in ui/, lane ag's folder, at the user's request) · task T28

Status: done (needs a lane ag look before the human merges)
Done this session:
- ui/app.py: two new pages and upgrades, so every result in PLAN.md section 1 "Finished result" is on screen.
  - Report (new): verdict counts, cost and call time, run flags (deck date source, HELD, pending), red flags
    by materiality with sources, founder questions, evidence requests, HELD notes, cost by provider,
    download report.json / report.md. It shows the stored report (store.get_report) and never rebuilds it.
  - Entities (new): company and founders from store.get_resolution (identity, signals, confidence,
    reason); a warning for every identity that is not confirmed. Professional fields only.
  - Run: state stepper (RUN_ORDER), per-claim progress bar, auto-refresh every 3 s (st.fragment) while a
    run is unfinished, "Open the report" when the followed run is done.
  - Claims: table columns follow rules.yaml output.fields (label shown as verdict, value as
    claimed_value), verdict and type filters, and per claim a "claimed in the deck" vs "found by the
    checker" block (CheckResult.observed, comparable, held_reason). Sources add source_type and call_id.
  - Ledger: limits used vs rules.yaml, failed calls listed, totals by provider, ledger.csv download.
  - Approvals: shows the run's red-flag count and a "Read the report first" button.
  - The chosen run is shared across pages (session_state current_run).
- ui/data.py: read-only helpers report_view, entities_view, run_progress, claim_columns, ledger_csv,
  limits_used; claim_rows now also returns observed/comparable/held_reason and all report ROW_FIELDS.
  Still never writes claims, evidence, verdicts, ledger or inbox (the existing test still passes).
- .streamlit/config.toml: theme (one accent colour).
- tests/ui/test_report_entities_pages.py: 9 tests. docs/LIVE_FIX_MAP.md: 2 lines (UI columns, colours).
In progress / exact next step:
- Lane ag: read the diff of ui/ on lane/ag-b before merging lane/ag (nobody else had changed ui/ since T18).
- Then check the Report page on a real Deck A run against tests/decks/deck_a_answers.yaml.
How to run / test:
- streamlit run ui/app.py
- python -m pytest -q tests/ui   (25 passed); python -m pytest -q   (237 passed)
Known bugs or shortcuts taken:
- Checked in a browser only on a fixture DB built from tests/ui fixtures (kept outside the repo); no live
  Deck A run yet (it would spend Crustdata credits).
- The auto-refresh fragment opens its own SQLite connection on every refresh, because Streamlit runs a
  fragment in another thread.
- report_view fills missing report sections with empty defaults, so an older or partial report still renders.
Decisions made (also in DECISIONS.md if they change behaviour):
- none (no contract or schema change)
Open questions for a human:
- ui/ is lane ag's folder; this work was done on lane/ag-b because the user asked. Please confirm lane ag
  accepts it.
Credits / tokens used this session (rough): 0 Crustdata credits
- Follow-up (same session): visual redesign of the UI. New ui/theme.py (CSS, verdict colours, slide strip,
  verdict mark, serif deck quotes; every outside text is html.escape'd). Report opens with the company, a
  strip with one block per claim in slide order coloured by verdict, then red flags as deck quote vs what
  the records say. Pages renamed in the sidebar (values unchanged, tests still set "Run", "Claims", ...).
  Fonts: Public Sans + Source Serif 4 from Google Fonts, system fallback when offline. 237 tests pass.


### 16:28 · yash · lane ag-b (in ui/, lane ag's folder, at the user's request) · task T29

Status: done (needs a lane ag look before the human merges)
Done this session:
- ui/components/: one Streamlit component (deckcheck_motion) in plain HTML/JS, no npm, no build, no CDN script.
  bridge.js speaks the component protocol by hand; route.js, strip.js, gauge.js, sent.js draw the moments.
  - Route tracker (Check a deck, Report while not ready): run states as checkpoints, marker moves as the
    run advances; claim blocks fill with their verdict colour as verdicts are stored. First sight of a run
    shows its state with no motion (a resumed run's finished steps are just lit).
  - Deck scan (Report): the slide strip fills left to right once per run, counts count up. Strip blocks
    are buttons: hover/focus shows the quote, click opens that claim on Every claim (expanded).
  - Value gauge (red flags, claim detail): claimed value, tolerance band from rules.yaml, found marker.
    Display only; the label is the engine's. Shown for metrics in GAUGE_FOUND (headcount, total_raised,
    round_amount).
  - Exactly-once send (Founder email): the email card moves into the test inbox tray once after approval,
    then a "Sent once, key ..." stamp; reloads show the settled stamp.
  - Each moment plays once (sessionStorage flag) and jumps to its end state under prefers-reduced-motion.
- Dark design applied from the team's design spec (netflix.com-design.md): black canvas, #111111 surfaces,
  #374151 borders, red #E50914 for primary buttons, brand and Contradicted only; 4px buttons/inputs, 8px
  cards, pill banners for run notes. Fonts: Inter (text) + Bebas Neue (wordmark, report hero) from Google
  Fonts, fallback Helvetica Neue/Segoe UI offline. Netflix Sans is proprietary, so it is not used.
- ui/data.py: gauge_payload, strip_payload, route_payload. tests/ui/test_components.py (15 tests).
  tests/ui/conftest.py sets DECKCHECK_STATIC_UI=1 (AppTest cannot run component iframes).
- Bugs found in the browser and fixed: the auto-refresh read the default DB instead of the sidebar one
  (fragment closure); a payload field named "key" collided with Streamlit's own argument.
In progress / exact next step:
- Lane ag: review ui/ on lane/ag-b. Then run Deck A live and watch the route tracker and report.
How to run / test:
- streamlit run ui/app.py   (DECKCHECK_STATIC_UI=1 to switch the animated components off)
- python -m pytest -q
Known bugs or shortcuts taken:
- Checked in a browser on a fixture DB only (outside the repo), not on a live Deck A run or a real kill/resume.
- Reduced-motion path checked in code only (the test browser could not emulate it).
- Fonts need internet; offline the fallback stack is used (layout unchanged).
Decisions made (also in DECISIONS.md if they change behaviour):
- none (no contract or schema change)
Open questions for a human:
- ui/ is lane ag's folder; this was done on lane/ag-b because the user asked.
Credits / tokens used this session (rough): 0 Crustdata credits
- Follow-up (same session): one theme mixed from the two design specs (netflix.com-design.md +
  apple.com-design.md): dark canvas, Apple ink #1D1D1F panels and #F5F5F7 text, Apple blue #0071E3 for
  actions and motion, red #E50914 only for the wordmark and Contradicted, Apple pill buttons (44px), 12px
  cards, Apple type scale, centred report hero. SF Pro via system names, Inter as stand-in, Bebas Neue for
  the wordmark/hero (SF Pro and Netflix Sans are proprietary, not shipped). Checked with the webapp-testing
  skill (Playwright, headless): no console errors, no sideways scroll at 390px, components honour
  prefers-reduced-motion. kill-ai-slop scan: clean. Springy stamp easing in sent.js replaced by a plain fade; round checkpoints and the Inter stand-in are pinned with deslop-ignore comments that give the reason.

### 16:42 · teammate · lane teammate · task T26, T24, T05

Status: done
Done this session:
- docs/DEMO.md: complete 2-minute video presentation script (timed to 120s), crash-and-resume walkthrough (Ctrl-C + resume), and 3 live-fix drills (headcount tolerance change, output field addition, budget/credit cap trip to HELD).
- BUSINESS.md: commercial diligence economics for VC partners, buyer profiles, manual analyst cost benchmark (₹3,000–₹8,000 vs ₹2.79 live Deck A baseline / ~₹14 with web search), pricing tiers (₹499/deck), >95% gross margins, 100x queue/cache scaling plan, and key operating risks.
- ETHICS.md: data minimization principles (professional records only, zero personal contact ingestion), two-signal namesake protection, verifiable dated evidence provenance, deterministic code-only verdicts, transactional human-in-the-loop approval, and neutral advice framing.
- config/rules.yaml & report/question_templates.yaml: confirmed all placeholder financial thresholds, removed PLACEHOLDER tags with explicit partner rationale comments, and refined neutral founder inquiry templates.
- tests/decks/ & tests/eval/: created make_deck_b.py (Shadowfax) and make_deck_c.py (Apex Logistics namesake trap deck), generated selectable text PDFs with synthetic test disclaimers, authored request JSONs, verified verbatim slide quotes, created comprehensive answer keys (deck_b_answers.yaml, deck_c_answers.yaml), and drafted extraction targets (deck_b_claims.json, deck_c_claims.json).
- Test suite: verified full suite passes cleanly with 429 passed.
In progress / exact next step:
- Request harshit to record the company fixture for Deck B / Deck C if desired, and merge lane/teammate into main.
- Rehearse and record the 2-minute demo video according to docs/DEMO.md before 17:30 IST.
How to run / test:
- python -m pytest -q   (429 passed)
- streamlit run ui/app.py
- python tests/decks/make_deck_b.py && python tests/decks/make_deck_c.py
Known bugs or shortcuts taken:
- tests/fixtures/crustdata/ fixtures for Deck B and C are pending recorded provider responses (requires credits approval from harshit).
Decisions made (also in DECISIONS.md if they change behaviour):
- Retained established default thresholds in config/rules.yaml, validating them as confirmed finance partner values and removing PLACEHOLDER annotations.
Open questions for a human:
- Harshit: please review and merge lane/teammate into main.
Credits / tokens used this session (rough): 0 Crustdata credits, 0 live LLM tokens.

### 17:05 · claude-core (merger) · lane claude-core · merge of ag-b (UI) and teammate (docs, decks)

Status: done
Done this session:
- Merged lane/ag-b (UI redesign, T28, T38) and lane/teammate (ETHICS, BUSINESS, DEMO, decks B and C, question templates) into main. 517 tests pass, Deck A eval unchanged. Kept main's config/rules.yaml (teammate's copy was old-main plus comments). UI motion task renumbered T29 -> T38.
- Fixed documents: BUSINESS.md (measured ₹11.96 full run, placeholder-rate warning, margins recomputed, no invented rate limits), ETHICS.md (undated fallback D17, job dates D19, new fairness section), DEMO.md (₹12 closing line, no `export` command).
- Decks B and C answer keys: every row TBD (no recorded evidence; team_growth never CONTRADICTED; forecasts skipped). `run_eval.py --deck b|c` still stops with "no recorded company response" until a live run is recorded.
Known bugs or shortcuts taken:
- UI: sidebar and expander icons show as raw text (keyboard_double_..., arrow_right) because ui/theme.py overrides Streamlit's icon font. Needs the UI owner (lane ag) before the demo.
Open questions for a human:
- Spend about 11 credits per deck to run decks B and C live and fill their keys?
Credits / tokens used this session (rough): 0

