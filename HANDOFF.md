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
