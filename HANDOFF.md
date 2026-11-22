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
- ag-b lane has finished T03, T09, T11, T17! Next lane tasks can be Milestone 1 integration with claude-verdict (verdict/engine.py) once Deck A is placed in tests/decks/ by finance partner.
How to run / test:
- pytest tests/extract/ tests/checkers/ -v
- pytest -q
Known bugs or shortcuts taken:
- Deck A PDF was not yet in tests/decks/ (finance partner is adding it), so extract/pdf.py was tested on multi-slide PDF generated via reportlab in tests/extract/test_pdf.py.
- If sources/crust.py is not yet implemented by codex-a, checkers safely read ctx.company or return held_reason="error" if network fails.
Decisions made (also in DECISIONS.md if they change behaviour):
- extract/pdf.py uses pypdf with graceful pymupdf fallback.
- extract/claims.py quote verification matches verbatim or normalized whitespace across newlines.
Open questions for a human:
- Finance partner: add pypdf to requirements.txt (requirements.txt is owned by claude-core).
- Finance partner: provide Deck A PDF under tests/decks/ when ready.
Credits / tokens used this session (rough): 0 Crustdata credits; 0 external LLM credits (used unit tests and local execution)
