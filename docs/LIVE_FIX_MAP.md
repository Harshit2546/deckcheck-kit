# LIVE_FIX_MAP.md

One line per thing a judge might ask to change. Format: To change X -> edit Y in file Z.

- To change a tolerance (e.g. headcount +-20%) -> `tolerances.team_size.tolerance_pct` in config/rules.yaml
- To add an output field -> report/ builder + io/adapter.py `to_kit()` + `output.fields` in config/rules.yaml
- To change the cost limit -> `limits.max_cost_inr` in config/rules.yaml
- To change the Crustdata request timeout -> `limits.per_call_timeout_s` in config/rules.yaml
- To adjust quote matching strictness -> `verify_claim_quote` in extract/claims.py
- To change observed fields extracted for a checker -> checkers/<claim_type>.py
- To change a rupee rate (Crustdata credit, LLM tokens) -> `costs.*` in config/rules.yaml
- To change the email test inbox -> `actions.test_inbox` in config/rules.yaml
- To change a stage function name or module the runner calls -> `STAGES` in core/runner.py (signatures in DECISIONS.md D7)
- To make verdicts stricter or looser (how close counts as "clearly close"/"clearly wrong", what counts as a fresh record) -> `verdict.supported_margin`, `verdict.strong_margin`, `verdict.fresh_days` in config/rules.yaml (needs D8 keys)
- To change when a record is too old to compare -> `tolerances.max_record_age_days` in config/rules.yaml
- To change which titles count as senior -> `title_levels` (order = seniority) and `tolerances.founder_background.min_title_level` in config/rules.yaml
- To add a verdict rule for a new claim type -> new file verdict/<type>.py with `judge(...)`, one branch in `_route` in verdict/engine.py, its keys in rules.yaml
- To add or remove a column in the report claim table -> `output.fields` in config/rules.yaml (names allowed: `ROW_FIELDS` in report/builder.py; add a new name there and in `_fields`)
- To reword founder questions, evidence requests or held notes -> report/question_templates.yaml (per claim type, `default` is the fallback)
- To change how many signals identify a company or person -> `identity.min_signals` in config/rules.yaml
- To change which words are dropped from company names before matching (Pvt, Ltd, ...) -> `LEGAL_SUFFIXES` in resolve/names.py
- To add an identity signal -> `_company_signals` or `_person_signals` in resolve/entities.py (and its test in tests/resolve/)

- To change the founder email wording -> `_body()` in actions/email.py (questions come from report/question_templates.yaml)
- To change how old a record may be for one claim type (for example funding rounds) -> `tolerances.<claim type>.max_record_age_days` in config/rules.yaml; without it `tolerances.max_record_age_days` (global) applies (D14)
- To add or remove a column on the UI Claims page -> `output.fields` in config/rules.yaml (same list as the report; ui/data.py `claim_columns`). Renamed for display: `label` -> verdict, `value` -> claimed_value (`DISPLAY_NAMES` in ui/data.py)
- To change the UI colours -> `.streamlit/config.toml` (Streamlit theme), `VERDICTS`, `CSS` and the font stacks in ui/theme.py, and the tokens at the top of ui/components/frontend/style.css
- To change an animation's timing -> `duration` values in ui/components/frontend/<route|strip|gauge|sent>.js (deck scan length: `SCAN_MS` in strip.js)
- To turn all animated components off (static HTML instead) -> set env `DECKCHECK_STATIC_UI=1` before `streamlit run ui/app.py`
- To show the value gauge for another numeric metric -> add `metric: (path in observed)` to `GAUGE_FOUND` in ui/data.py (needs `tolerances.<type>.tolerance_pct`)
