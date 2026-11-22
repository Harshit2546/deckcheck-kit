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
