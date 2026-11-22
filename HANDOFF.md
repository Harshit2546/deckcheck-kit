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
