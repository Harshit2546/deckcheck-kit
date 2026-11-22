# DECISIONS.md — changes to contracts, rules and requirements

Append-only. One entry per decision. Required before changing anything in
`core/models.py`, the DB schema, a listed function signature, or `config/rules.yaml`
semantics. The hour-3 requirement change from the organizers goes here too.

```
### <HH:MM> · <who> · D<n>: <title>
Change:
Why:
Files affected:
Who must know (lanes):
```

### 11:00 · human · D1: verdicts are decided by code, not the LLM
Change: verdict/engine.py compares values using config/rules.yaml. The LLM only extracts claims, picks exact quotes, and writes explanations.
Why: hidden test cases punish wrong answers more than "cannot verify"; code is repeatable and explainable to judges.
Files affected: verdict/, checkers/
Who must know: all lanes

### 11:00 · human · D2: lanes match the team's real accounts
Change: the single claude lane splits into claude-core (core/, io/adapter.py, actions/) and claude-verdict (verdict/, report/, hour-3 change, merge reviews). Lane codex-b becomes ag-b (Gemini/Antigravity). Third Gemini account is a spare for ag-b or codex-a. Branches: lane/claude-core, lane/claude-verdict, lane/codex-a, lane/ag-b, lane/ag.
Why: the team has 2 Claude Pro, 1 ChatGPT Plus and 3 Gemini Pro accounts, not several Codex accounts. Two Claude lanes on separate folders run in parallel and back each other up.
Files affected: PLAN.md (sections 4-6), TASKS.md, AGENTS.md (section 4), CLAUDE.md
Who must know: all lanes
