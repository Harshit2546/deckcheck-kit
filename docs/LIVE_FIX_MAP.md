# LIVE_FIX_MAP.md

One line per thing a judge might ask to change. Format: To change X -> edit Y in file Z.

- To change a tolerance (e.g. headcount +-20%) -> `tolerances.team_size.tolerance_pct` in config/rules.yaml
- To add an output field -> report/ builder + io/adapter.py `to_kit()` + `output.fields` in config/rules.yaml
- To change the cost limit -> `limits.max_cost_inr` in config/rules.yaml
- To change a rupee rate (Crustdata credit, LLM tokens) -> `costs.*` in config/rules.yaml
- To change the email test inbox -> `actions.test_inbox` in config/rules.yaml
- To change a stage function name or module the runner calls -> `STAGES` in core/runner.py (signatures in DECISIONS.md D7)
- To make verdicts stricter or looser (how close counts as "clearly close"/"clearly wrong", what counts as a fresh record) -> `verdict.supported_margin`, `verdict.strong_margin`, `verdict.fresh_days` in config/rules.yaml (needs D8 keys)
- To change when a record is too old to compare -> `tolerances.max_record_age_days` in config/rules.yaml
- To change which titles count as senior -> `title_levels` (order = seniority) and `tolerances.founder_background.min_title_level` in config/rules.yaml
- To add a verdict rule for a new claim type -> new file verdict/<type>.py with `judge(...)`, one branch in `_route` in verdict/engine.py, its keys in rules.yaml
