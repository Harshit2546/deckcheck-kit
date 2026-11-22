# AGENT_PROMPTS.md: the first prompt for each AI account

Paste the prompt for the lane into the tool, opened in that lane's worktree folder.
Replace `<label>` with the account label (e.g. `claude-b1`, `gemini-3`).
When an account hits its limit, the next account of any tool uses the
"Continue a lane" prompt at the bottom.

## 0. One-time setup (each person, on their own machine)

```powershell
git clone <repo-url> deckcheck-kit
cd deckcheck-kit
git worktree add ../dc-<lane> -b lane/<lane> origin/main
```

Run the `worktree add` line once per lane you drive (merger: `claude-core`, `ag`;
finance partner: `claude-verdict`, `codex-a`, `ag-b`). Copy `.env` (API keys,
gitignored) into each worktree folder. Open each AI tool in its `../dc-<lane>` folder.

---

## 1. Claude Pro A: lane `claude-core` (merger's machine)

```
You are account <label> on lane claude-core of DeckCheck, a hackathon project.
First read AGENTS.md completely and follow it exactly. Then read PLAN.md (all of it,
especially section 3 "Contracts"), TASKS.md, DECISIONS.md and the last 3 entries of
HANDOFF.md. Your branch is lane/claude-core and this folder is its worktree.
You may edit only: core/, io/adapter.py, actions/, cli.py, config/rules.yaml (schema
only, values belong to the finance partner), requirements.txt, and your own tests in
tests/core/ and tests/actions/.

Do the start-of-session ritual from AGENTS.md section 1: claim T01 in TASKS.md and
commit that alone as "[claude-core] tasks: claim T01", then push.

T01 is the team's critical path; every other lane waits for core/models.py. Build:
- core/models.py: every contract in PLAN.md section 3 (Claim, Evidence, Verdict,
  LedgerEntry, Action, CheckResult, plus the run and claim state enums). Pydantic or
  dataclasses, all type-hinted. Nothing else may define models.
- core/store.py: SQLite schema and helpers for runs, claims, evidence, verdicts, ledger,
  actions, and inbox with UNIQUE(idempotency_key). Tables created on first use.
- core/log.py: one-line structured log per step (run id, claim id, step, result).
- config/rules.yaml: the schema with keys for tolerances per claim type, title levels,
  materiality weights, limits (max_cost_inr, max_seconds, max_credits,
  per_call_timeout_s) and output fields. Put clearly marked placeholder values and a
  comment that the finance partner sets the real ones.
- cli.py: "run" (deck PDF, company domain, deck date, optional founder URLs) and
  "resume <run_id>", argparse. A stub runner is fine for now.
- io/adapter.py: stub that maps kickoff-kit input to internal models, with a TODO
  pointing to the DECISIONS entry the merger will write about the kit format.
Done when: "python cli.py run --help" works and the tables are created; pytest -q passes.
Commit small, push as soon as models.py and store.py exist so other lanes can pull.

Then continue with T07 (core/runner.py: state machine, per-claim checkpoints, resume,
cost and time limits checked against the ledger before every external call; limit,
timeout or error makes a claim HELD) and later T19 (actions/: draft, approval,
exactly-once send exactly as PLAN.md section 3 describes; never a plain retry).

Never change a contract after you push it without a DECISIONS.md entry. Do the
end-of-session ritual (AGENTS.md section 5) before your usage limit, not after.
```

## 2. Claude Pro B: lane `claude-verdict` (finance partner's machine)

```
You are account <label> on lane claude-verdict of DeckCheck, a hackathon project.
First read AGENTS.md completely and follow it exactly. Then read PLAN.md (all of it,
especially section 3 "Contracts" and section 7), TASKS.md, DECISIONS.md and the last 3
entries of HANDOFF.md. Your branch is lane/claude-verdict and this folder is its worktree.
You may edit only: verdict/, report/, and your own tests in tests/verdict/ and
tests/report/. Never edit core/ (lane claude-core) even if it looks wrong: write the
problem in your HANDOFF entry and tell the human.

Do the start-of-session ritual: claim T13 in TASKS.md, commit "[claude-verdict] tasks:
claim T13", push.

core/models.py does not exist yet (lane claude-core is writing it in T01). Until it is on
origin/main, write verdict/DESIGN.md only, no code:
- For founder_background, team_size and funding: which keys checkers must put in
  CheckResult.observed, and how the engine maps (claim value, observed value,
  comparable, held_reason, evidence) to SUPPORTED, CONTRADICTED, NOT_COMPARABLE,
  CANNOT_VERIFY or HELD, with a reason_code and confidence for each path.
- Which config/rules.yaml keys the engine reads (tolerances, title levels). Values come
  from rules.yaml, never from code.
- Rule: wrong SUPPORTED/CONTRADICTED costs more than CANNOT_VERIFY, so lean cautious.
  Timeouts, errors and limits are HELD, never CANNOT_VERIFY.
Push verdict/DESIGN.md early: lanes codex-a and ag-b build checkers that must
fill those observed keys, so record the keys in your HANDOFF entry too.

When core/models.py is on origin/main, merge it in and build verdict/engine.py (T13) with
tests from recorded fixtures in tests/ only. Then T15 (report/: red flags by
materiality, claim table, founder questions, evidence-request list, JSON and Markdown in
the kit format). At 13:15 the organizers change one requirement: you own T20 (read it,
write the DECISIONS entry, assign the work). You also own T27: when the human asks for a
merge review, review the lane branch diff against AGENTS.md hard rules and PLAN.md
contracts and report problems before they merge.

The LLM never decides a verdict, number, date or comparison; code does. Do the
end-of-session ritual (AGENTS.md section 5) before your usage limit, not after.
```

## 3. ChatGPT Plus (Codex): lane `codex-a` (finance partner's machine)

```
You are account <label> on lane codex-a of DeckCheck, a hackathon project.
First read AGENTS.md completely and follow it exactly. Then read PLAN.md (especially
section 3 "Contracts" and section 4), TASKS.md, DECISIONS.md and the last 3 entries of
HANDOFF.md. Your branch is lane/codex-a and this folder is its worktree.
You may edit only: sources/, resolve/, checkers/founder_background.py,
checkers/prior_exit.py, checkers/company_fact.py, checkers/customer.py, docs/crustdata_fields.md,
and your own tests in tests/sources/, tests/resolve/, tests/checkers/ (for your checkers).

Start-of-session ritual: claim T02, commit "[codex-a] tasks: claim T02", push.

T02 now: probe the Crustdata API (key in .env, never print it) on the Deck A company and
its founders. Write docs/crustdata_fields.md: each endpoint, the fields it returns that
matter for our claim types, record dates available, and the credit cost per call.
Save a few raw responses as fixtures under tests/fixtures/crustdata/ only, with personal
contact details (emails, phones) removed.

Then, in order:
- T08 sources/crust.py: rate limit, backoff on 429/5xx, per-call timeout that returns a
  HELD reason (not an error the claim swallows), one ledger row per call including
  failures, short-TTL entity cache that keeps retrieved_at. Use core/models.py and
  core/store.py from origin/main once lane claude-core pushes them; until then build the
  HTTP layer and tests only.
- T10 resolve/entities.py: company by domain, founders by profile URL or name+company,
  the two-signal identity rule, confidence; a namesake fixture must return
  identity_unclear.
- T12 checkers/founder_background.py, then T16 prior_exit, company_fact, customer (web
  quote verification in sources/web.py).
Checkers implement check(claim, ctx) -> CheckResult and only fetch and normalise; they
never choose a verdict label. Fill CheckResult.observed with the keys lane
claude-verdict lists in verdict/DESIGN.md and its HANDOFF entry.

No mock data or stored answers outside tests/. Every Evidence has source type, locator,
exact field or quote, record date and retrieved_at. Do the end-of-session ritual
(AGENTS.md section 5) before your usage limit, not after.
```

## 4. Gemini 2 (Antigravity): lane `ag-b` (finance partner's machine)

```
You are account <label> on lane ag-b of DeckCheck, a hackathon project.
First read AGENTS.md completely and follow it exactly. Then read PLAN.md (especially
section 3 "Contracts" and section 4), TASKS.md, DECISIONS.md and the last 3 entries of
HANDOFF.md. Your branch is lane/ag-b and this folder is its worktree.
You may edit only: extract/, checkers/team_size.py, checkers/funding.py,
checkers/team_growth.py, checkers/hiring.py, checkers/traction.py,
checkers/market_size.py, checkers/competition.py, and your own tests in tests/extract/
and tests/checkers/ (for your checkers).

Start-of-session ritual: claim T03, commit "[ag-b] tasks: claim T03", push.

T03 now: extract/pdf.py returns the text of each slide of a text-based PDF, keyed by
slide number. Test it on Deck A in tests/decks/ (the finance partner is adding it; if it
is not there yet, test on any text PDF and say so in HANDOFF).

Then, in order:
- T09 extract/claims.py: the LLM returns structured claims (PLAN.md section 3 Claim
  fields and types); then code checks that every quote appears on its slide and drops
  any that does not. A test with an invented quote must show it rejected. Every LLM
  call writes a ledger row (provider, model, tokens, cost).
- T11 checkers/team_size.py and checkers/funding.py, then T17 team_growth, hiring,
  traction, market_size, competition (cut order if late: competition, then market size,
  then hiring).
Use core/models.py from origin/main once lane claude-core pushes it. Checkers implement
check(claim, ctx) -> CheckResult, fetch through sources/ (lane codex-a) and only
normalise; they never choose a verdict label. Fill CheckResult.observed with the keys
lane claude-verdict lists in verdict/DESIGN.md and its HANDOFF entry.

No mock data or stored answers outside tests/. The LLM never decides numbers, dates or
comparisons. Do the end-of-session ritual (AGENTS.md section 5) before your usage limit,
not after.
```

## 5. Gemini 1 (Antigravity): lane `ag` (merger's machine)

```
You are account <label> on lane ag of DeckCheck, a hackathon project.
First read AGENTS.md completely and follow it exactly. Then read PLAN.md, TASKS.md,
DECISIONS.md and the last 3 entries of HANDOFF.md. Your branch is lane/ag and this
folder is its worktree.
You may edit only: ui/, tests/eval/, docs/ARCHITECTURE.md and diagrams, and README.md
drafts (a human approves README).

Start-of-session ritual: claim T04, commit "[ag] tasks: claim T04", push.

T04 now: ui/app.py in Streamlit with an upload form (deck PDF, company domain, deck
date, optional founder URLs) and a run list read from the SQLite DB in core/store.py.
Until lane claude-core pushes core/store.py, build the layout against the table names in
PLAN.md section 3 and read nothing that is not in the DB.

Then, in order: T18 (verdict detail showing the source link, field or quote and record
date; approvals page where only a human click moves an email from pending to approved;
inbox view; ledger view with rupee totals), T21 tests/eval/run_eval.py (per-claim pass or
fail against the answer key for decks A, B, C), T23 docs/ARCHITECTURE.md with a diagram,
T25 README draft.

The UI never shows cached or demo output as live, and never sends email itself; it only
changes action status through core/ helpers. Do the end-of-session ritual (AGENTS.md
section 5) before your usage limit, not after.
```

## 6. Continue a lane (spare Gemini 3, or any account after a limit)

```
You are account <label> continuing lane <lane> of DeckCheck, a hackathon project.
First read AGENTS.md completely and follow it exactly. Then read PLAN.md (section 3
"Contracts" and the row for lane <lane> in section 4), TASKS.md, DECISIONS.md and the
last 3 entries of HANDOFF.md. Your branch is lane/<lane> and this folder is its worktree.
Edit only the folders PLAN.md section 4 gives lane <lane>.

Find the most recent HANDOFF entry for lane <lane>. Run the test command it names
before writing new code. Mark yourself on its in-progress task in TASKS.md and commit
that alone as "[<lane>] tasks: <label> continues <T-id>". Then do exactly the
"In progress / exact next step" it lists. If the entry is missing or unclear, tell the
human before coding.

Do the end-of-session ritual (AGENTS.md section 5) before your usage limit, not after.
```
