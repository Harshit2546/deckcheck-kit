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
