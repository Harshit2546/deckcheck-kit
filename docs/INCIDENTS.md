# INCIDENTS.md: errors, failures and near misses during the build

A running log of what went wrong on 2026-11-22, how we caught it and what changed. It is for
the pitch ("what broke and how the system handled it") and for the judges' "logs, cost records,
repo history" check. Every row points to a commit, decision or HANDOFF entry you can open.

**Add to it:** append a row to the right table whenever a run, test, review or merge shows a
bug, a near miss or a wrong assumption. Never edit an old row; add a follow-up row instead.
Times are IST and come from the HANDOFF/DECISIONS headers, log lines (UTC + 5:30) or commit times. Some HANDOFF headers were written on different laptops' clocks, so treat times as approximate.

## Pitch highlights (the six worth telling)

Where it ended up: the last live Deck A run scores **6 of 6 against the answer key** (one claim has no expected answer), for ₹11.96 and 11 credits.

1. **A bad API key did not lose the run.** The first live Deck A run died at extraction
   (Gemini key rejected). The failed call stayed in the ledger, and `cli.py resume`
   finished the same run from its checkpoint with the other LLM key. Total cost: ₹2.79. (#A1)
2. **The date rule caught real data.** Crustdata's headcount "total" has only a refresh
   date, so using it would date a fact by when the provider refreshed it. We decided (D13)
   to use the dated history point instead (349 on 2026-11-02), which is what the live run
   used. (#B1)
3. **Missing parts gave HELD, not wrong answers.** Before the web source existed, the
   market-size checker crashed on a missing module and the customer checker didn't exist.
   The runner turned both into HELD with a reason; no claim got a made-up verdict. (#B5)
4. **A wrong SUPPORTED caught before it shipped.** The prior-exit checker looks up the
   deck's own company, and Locus really was acquired in 2025, so a founder's "prior exit"
   would have been "supported" by the wrong company. The verdict rule refuses to decide
   until the checker fetches the right company. (#B6)
5. **Reviews caught hard-rule violations before main.** A checker stubbing the data
   source at runtime, a test-only `example.com` branch in runtime code, and swallowed
   import errors that would have turned a missing source into "cannot verify". (#C1 to #C3)

6. **The safety margin caught the LLM picking the wrong market.** In the first live web
   run, the quote picker matched "logistics software market, $9B" to a news line about
   the *home and household* market (USD 237 billion by 2030). Because a Contradicted needs
   two agreeing sources, the verdict stayed Cannot verify, and the gap (relevance was left
   to the LLM, not checked by code) went into the fix list. (#B10)

## A. Live runs and external services

| # | When | What happened | How it was caught | Impact | Fix / outcome | Where |
|---|---|---|---|---|---|---|
| A1 | 14:53 | First live Deck A run failed at extraction: Google rejected `GEMINI_API_KEY` (HTTP 400, `API_KEY_INVALID`). | Live run log | Run stopped in state `created`; nothing lost | The failed call kept its ledger row (`ok=0`). Resumed the same run with Gemini unset, so OpenAI (gpt-4o-mini) was used; it finished: 4 calls, 2 credits, ₹2.79, 16.5 s. The Gemini key still needs fixing. | HANDOFF 15:35 (merger); run `run-20261122-092339-ef3899` |
| A2 | 14:53 | The documented demo command failed with "deck not found": `cli.py` joined the repo-relative `deck_path` onto the request file's folder (`tests/decks/tests/decks/deck_a.pdf`). | First live run | Demo command never worked | `cli.py` now looks beside the request first, then from the current folder; test added | commit 895f767 |
| A3 | all day | Crustdata returns no per-call billing receipt on some calls. | codex-a probe | Ledger credits are estimates where the header is missing | Credits recorded from published rates and said so; the web client reads `X-Credits-Used` when present | HANDOFF 13:51 (codex-a), D16 |
| A4 | 15:30 | Crustdata web search results carry **no publish date**. | Reading the API docs before building | A web fact would have had no record date (breaks D3) | Code reads the date from the fetched page's HTML (JSON-LD, meta tags, `<time>`); pages without one are skipped | docs/WEB_SOURCE.md, D16 |
| A5 | 15:58 | First live run with web search: the customer page fetch (`POST /web/enrich/live`) took longer than `limits.per_call_timeout_s` (20 s); the other fetch took 13 s. | Live run `run-20261122-102749-b58f62` | Slide 6 HELD (timeout), no verdict; the timed-out call is in the ledger with no credits | Correct handling. Open: a separate, longer timeout for web fetch (config key, web-client lane) | README "Live run with web search" |
| A6 | 16:08 | Second live web run: the customer **search** call took longer than `limits.per_call_timeout_s` (20 s). Search times so far: 6.4 s, 12.0 s, over 20 s, 6.8 s. | Live run `run-20261122-103822-1686da` | Slide 6 HELD (timeout) again; no credits charged for the timed-out call | Open: raise `limits.per_call_timeout_s` or add a search timeout key (config edit, no code) | README "Live run with web search" |
| A6b | 16:12 | `limits.per_call_timeout_s` raised from 20 to 30 (config only, d4b1da6). Third live run: search 7.0 s and 5.9 s, fetch 28.3 s and 17.0 s, all within limits. | Live run `run-20261122-104047-1b295e` | Slide 6 now CANNOT_VERIFY `no_evidence`; the run scores 6 PASS, 0 FAIL, 1 SKIP against the answer key | Fixed | README "Latest live run" |

## B. Data, dates and verdict correctness

| # | When | What happened | How it was caught | Impact | Fix / outcome | Where |
|---|---|---|---|---|---|---|
| B1 | 15:40 | Headcount and growth "snapshot" fields have only a refresh date, not the record's own date. | claude-verdict question on D3 | Using them would date a number by the provider's refresh | D13: use the latest dated history point on or before the deck date | DECISIONS D13 |
| B2 | 16:50 | Offline eval: funding slides 3 and 4 came out CANNOT_VERIFY `missing_record_date`; the funding checker ignored `funding.milestones[]`, which holds the dated rounds. | Eval against the answer key | 2 of 6 scored claims wrong | ag-b parses milestones, dates each round, counts undated rounds; slides 3 and 4 PASS | HANDOFF 17:15 (ag-b), commit 4d5c91c |
| B3 | 16:20 | Locus's funding rounds are from 2016 to 2021, but the global record age limit was 365 days. | Verdict engine review | Every real funding claim would be `stale_record` | D14: age limit per claim type; `tolerances.funding.max_record_age_days: 3650` | DECISIONS D14 |
| B4 | 14:53 | Slide 8 (hiring) stops at `missing_record_date`: Crustdata's `hiring.openings_count` (5) has no date. | Live run | Claim stays CANNOT_VERIFY | Correct under D3; the hiring checker needs a dated field (open) | README "Live run" |
| B5 | 16:50 | Slide 7: `checkers/market_size.py` imported `sources.web`, which did not exist (ModuleNotFoundError). Slide 6: no customer checker at all. | Offline eval and live run | Both claims HELD (`error`, `no_checker`), never a made-up verdict | Web source built (T30 to T33) | HANDOFF 16:50 (T21), D16 |
| B6 | 15:11 | The prior_exit checker queries the **deck's own** company, not the founder's earlier one. Locus was acquired by Ingka in 2025. | Reading the checker before writing its verdict rule | Would have produced a wrong SUPPORTED | Rule returns CANNOT_VERIFY `prior_company_not_checked` until the checker fetches the right company and sets a flag | DECISIONS D15, verdict/DESIGN.md section 5 |
| B7 | 15:11 | The team_growth checker measures from the oldest history point (years), not the period the claim states. | Same review | Wrong period means wrong SUPPORTED or CONTRADICTED | Rule returns NOT_COMPARABLE `period_mismatch` until the checker reports `baseline_date` | DECISIONS D15 |
| B8 | 15:11 | The engine read `tolerances.<type>.tolerance_pct` for every ruled type; competition has none. | Design review | Every competition claim would crash with KeyError | Competition excluded from the lookup; always CANNOT_VERIFY `competition_not_judged` | DECISIONS D15 |
| B9 | 14:35 | A real run raised ValueError at its first verdict: the engine needs a `verdict:` block in rules.yaml that didn't exist yet. | claude-verdict | No run could finish | D8: `verdict:` block added to rules.yaml | DECISIONS D8 |
| B10 | 15:58 | Live web run: the market-size checker accepted the quote "India's home and household market is projected to reach USD 237 billion by 2030" as evidence for "India's logistics software market is worth $9B". The checker passed no `must_contain` terms, so only the LLM judged relevance, and it also took a 2030 forecast for today's size. | Reading the live result's sources | Verdict stayed safe (CANNOT_VERIFY), only because CONTRADICTED needs 2 agreeing sources (D16). Two such pages would have produced a wrong CONTRADICTED. | Open: code must require the claim's market terms in the quote and skip forecasts dated after the reference year (checkers/market_size.py) | README "Live run with web search" |
| B10b | 16:08 | Fix for B10 merged (98ce097): the market-size checker now requires the claim's market terms in the quote and skips forecasts for a later year. | Second live run | Slide 7 is now CANNOT_VERIFY `no_evidence` (no dated page), which matches the answer key | Fixed | commits 6175715, 204cf59 |
| B11 | 16:30 | Founder lookups (T36) worked live, but Crustdata's person record has no `updated_at`, so every founder claim stopped at CANNOT_VERIFY `missing_record_date`. With a dated job the global 365-day age limit would also have made a 2014 job `stale_record`. | T36 live probe | No founder claim could be decided | D19: the record date is the matched job's own date (latest start/end on or before the deck date); founder_background gets `max_record_age_days` 18250. Live Deck F: slide 2 SUPPORTED employer_listed | Fixed (4805db0) | README "Live run, Deck F" |
| B12 | 16:40 | A job missing from a founder's profile has no date, so the engine's date check runs before the founder rule and gives `missing_record_date` (or `_undated`) instead of `employer_not_in_profile`. | T37 review (web-client) | Label stays CANNOT_VERIFY, never CONTRADICTED; only the reason code differs | Open: route employer_found false before the date check (claude-verdict) | HANDOFF T37 |

## C. Hard-rule violations caught in review (before main)

| # | When | What happened | How it was caught | Fix | Where |
|---|---|---|---|---|---|
| C1 | before 17:05 | Runtime code had a branch for the test domain `example.com` (a test hack in the product path). | Merger hard-rule check | Removed; tests use fakes in `tests/` only | docs/MERGER_HANDOFF.md "Hard-rule checks" |
| C2 | 13:35 | Checkers caught `ImportError` and returned nothing, so a missing data source would have looked like "no evidence" (CANNOT_VERIFY) instead of HELD. | T27 review of ag-b | Errors now propagate; the runner makes them HELD | docs/reviews/T27_ag-b.md fix 5 |
| C3 | before 17:05 | A runtime stub of `sys.modules["sources.crust"]` (a fake source), invented URLs as sources, and a hard-coded identity "confirmed" with 2 signals. | Merger review | All removed; a missing source must raise | docs/MERGER_HANDOFF.md |
| C4 | 13:35 | Checkers used a context type that doesn't exist, the wrong `log_step` argument order, Evidence missing required fields, and `observed` keys the engine doesn't read. | T27 review | Fixed by ag-b before merge | docs/reviews/T27_ag-b.md fixes 1 to 7, commit 77b1f8a |
| C5 | 13:35 | Source client: limits not checked before each call, timeouts not becoming HELD, credits not marked as estimates. | T27 review of codex-a | Fixed in `sources/crust.py` | docs/reviews/T27_codex-a.md |

## D. Tooling and test harness

| # | When | What happened | How it was caught | Fix | Where |
|---|---|---|---|---|---|
| D1 | 15:36 | After the web source merged, the **offline eval** still replaced only the company lookup. With a key in `.env`, the "free" eval would have made real web calls and spent credits. | Merger, reading eval output after the merge (slides 6 and 7 showed "Set CRUSTDATA_API_KEY") | The offline replay now blocks web search, fetch and the quote LLM; a test proves no network call happens even with keys set | commit af13f8c |
| D2 | 15:30 | The T32 rewrite broke an old test that called the replaced `search_market_data` contract, and stopped the suite from loading. | T32 session | Old test removed in its own commit with the merger's OK | commit a1d1633 |
| D3 | 14:40 | Bare `pytest -q` failed in `tests/checkers` ("No module named 'core'") after pytest.ini was removed. | claude-core | Use `python -m pytest -q` (documented in README) | HANDOFF 14:40 |
| D4 | 11:45 | The adapter couldn't live at `io/adapter.py`: Python's built-in `io` module owns the name. | T01 | D4 moved it, D6 withdrew D4; it is loaded by file path via `core/adapter_loader.py` | DECISIONS D4, D6 |
| D5 | 16:50 | 6 UI tests failed on the Windows laptop (Anaconda NumPy 2.5 with an old pyarrow). | claude-verdict@win | Not a repo bug; they pass on the Mac | HANDOFF 16:50 (T21) |
| D6 | 15:35 | A merge helper script passed two conflicted file names as one argument (zsh doesn't split words). | The script failed before committing | Rerun per file; nothing wrong was committed | merger session |

## E. Git and process

| # | When | What happened | How it was caught | Fix | Where |
|---|---|---|---|---|---|
| E1 | 11:43 | T01 was pushed straight to `main` by mistake (only a human merges to main). | claude-core | Reverted 6 minutes later (8f21500); lanes merged main back | commits 8761021, 8f21500 |
| E2 | 16:05 | A lane folder was found checked out on `main` twice; `../dc-ag` is still on `main` instead of `lane/ag`. | claude-core, merger | Rule: never switch branches in a lane folder; merges only in a throwaway worktree | HANDOFF 16:05, docs/MERGER_HANDOFF.md |
| E3 | 14:10 | D9 said one laptop owned claude-verdict; the two laptops actually use two different Claude accounts. | claude-verdict@win | D10 corrected D9 | DECISIONS D9, D10 |
| E4 | all day | Every merge conflict was in HANDOFF.md / TASKS.md (never in code), because lanes own separate folders. | merger | Keep both HANDOFF entries; keep the more advanced TASKS status | docs/MERGER_HANDOFF.md |

## Still open


- `GEMINI_API_KEY` in `.env` is invalid (A1). Fix or remove it before the next live run.
- The hiring checker has no dated field (B4); the prior_exit and team_growth checkers need the fixes in B6 and B7.
- Founder title claims end `title_unmapped` until the finance partner sets real `title_levels` (Deck F slide 3).
- B12: founder claims for a job missing from the profile carry a date reason code instead of `employer_not_in_profile`.
- Deck F's company resolved `unclear` (1 signal) in the live run; founder claims are unaffected.
