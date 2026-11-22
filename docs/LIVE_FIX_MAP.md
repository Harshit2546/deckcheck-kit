# LIVE_FIX_MAP.md

One line per thing a judge might ask to change. Format: To change X -> edit Y in file Z.

- To change a tolerance (e.g. headcount +-20%) -> `team_size.tolerance_pct` in config/rules.yaml
- To add an output field -> report/ builder + io/adapter.py output mapping
- To change the cost limit -> `limits.max_cost_inr` in config/rules.yaml
- To adjust quote matching strictness -> `verify_claim_quote` in extract/claims.py
- To change observed fields extracted for a checker -> checkers/<claim_type>.py
