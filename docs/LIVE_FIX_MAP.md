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
- To run the accuracy check against the answer key -> `python tests/eval/run_eval.py` (offline, no credits); `--live` runs cli.py for real and spends credits; answer keys are tests/decks/deck_<x>_answers.yaml, recorded claims tests/eval/deck_<x>_claims.json
- To change how far a founded year may be off before it is CONTRADICTED -> `tolerances.company_fact.year_gap_cannot_verify` in config/rules.yaml
- To change how far a yearly headcount-growth window may be from 365 days -> `tolerances.team_growth.window_tolerance_days` in config/rules.yaml
- To change how many web pages are fetched per claim (credits and LLM calls), edit `web.results_to_fetch` in config/rules.yaml (D16).
- To change the web search country or sources, edit `web.location` / `web.sources` in config/rules.yaml (D16).
- To change how long a web page fetch may take before the claim is HELD, edit `web.fetch_timeout_s` in config/rules.yaml.
- To change how many agreeing web estimates a market-size CONTRADICTED needs, edit `tolerances.market_size.min_agreeing_sources` (D16).
- To change how old a web page may be and still count, edit `tolerances.market_size.max_record_age_days` / `tolerances.customer.max_record_age_days` (D16).
- To turn off using undated records (D17), or change how recent a deck must be for it, edit `verdict.undated_fallback` / `verdict.undated_max_deck_age_days` in config/rules.yaml.
