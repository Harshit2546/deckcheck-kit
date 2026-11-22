# LIVE_FIX_MAP.md

One line per thing a judge might ask to change. Format: To change X -> edit Y in file Z.

- To change a tolerance (e.g. headcount +-20%) -> `tolerances.team_size.tolerance_pct` in config/rules.yaml
- To add an output field -> report/ builder + io/adapter.py `to_kit()` + `output.fields` in config/rules.yaml
- To change the cost limit -> `limits.max_cost_inr` in config/rules.yaml
- To change a rupee rate (Crustdata credit, LLM tokens) -> `costs.*` in config/rules.yaml
- To change the email test inbox -> `actions.test_inbox` in config/rules.yaml
