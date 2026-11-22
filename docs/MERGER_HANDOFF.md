# MERGER_HANDOFF.md: coordinator and claude-verdict handoff to the Mac

Written by the coordinating Claude session on the Windows laptop (yash), which is
shutting down. From now on, the partner's Claude on the Mac (harshit) is the merger and
also owns lane claude-verdict. Read AGENTS.md first, then this file, then the last
HANDOFF.md entries.

## State at handoff
- main = the commit that adds this file (on top of 9e05d43). Every lane branch is merged.
  `pytest -q --ignore=tests/ui` gives 222 passed. The 6 UI tests pass on the Mac (they
  fail on the Windows laptop only because Anaconda's pyarrow can't load numpy 2.5).
- Offline eval: `python tests/eval/run_eval.py` replays Deck A (Locus, locus.sh,
  deck date 2026-11-15) through the real runner, resolve, checkers and engine with the
  recorded Crustdata response:
  slides 2, 3, 4, 5 PASS; slides 6, 7 FAIL; slide 8 SKIP. See "Open items".
- Live run (not yet done end to end, needs CRUSTDATA_API_KEY and an LLM key in .env):
  `python cli.py run --request tests/decks/deck_a_request.json --out out/result.json`
  `python cli.py resume <run_id> --out out/result.json`
  UI: `streamlit run ui/app.py`

## Lanes after the handoff
| Lane | Folder / machine | Next |
|---|---|---|
| claude-core | Mac `../dc-core` | README (T25), ARCHITECTURE.md + diagram (T23) |
| ag (UI) | Mac `../dc-ag` | done (T04, T18); only fixes |
| claude-verdict | moves to the Mac: `git worktree add ../dc-verdict lane/claude-verdict` | T20 hour-3 change if it arrives; T27 review before each merge |
| codex-a | Windows `deckcheck-kit-codex-a` (yash) | get_people / search_people (D12), sources/web.py, customer checker (T16) |
| ag-b | Windows `deckcheck-kit` (yash) | only fixes |

## How to merge (what this session did, every time)
1. Never merge inside an agent's folder, and never `git checkout`/`git switch` in a
   lane folder. Make a throwaway copy:
   `git fetch --all && git worktree add --detach ../merge-tmp origin/main`
2. In ../merge-tmp, merge one lane at a time: `git merge --no-ff origin/lane/<lane>`.
   Run `python -m pytest -q` after each one.
3. Conflicts only ever happened in HANDOFF.md, DECISIONS.md, docs/LIVE_FIX_MAP.md
   (keep BOTH sides, both entries in full) and TASKS.md (keep the row with the more
   advanced status: done > in-progress/blocked > todo). Any conflict in a code file:
   stop and ask the owning lane.
4. Push only when tests pass: `git push origin HEAD:main`, then
   `git worktree remove --force ../merge-tmp`.
5. Tell the other person the new hash. Every lane folder then runs
   `git fetch origin && git merge origin/main`.

## Hard-rule checks before every merge (things this session caught)
- No fake or mock source at runtime (e.g. stubbing sys.modules["sources.crust"]); a
  missing source must raise so the runner makes the claim HELD.
- No test hacks in runtime code (e.g. `if domain == "example.com"`).
- No invented URLs as sources; no hard-coded identity ("confirmed", 2 signals).
- No mail code (smtplib/requests in actions/); the email goes only to the local inbox table.
- Only facts dated on or before the deck date count (D3, D13, D14).

## Open items, most important first
1. Live end-to-end run of Deck A, then record the 2-minute demo video (by 5:30 PM).
2. README.md (T25) and docs/ARCHITECTURE.md (T23). Claim only what runs. Credits with
   licences: pyyaml, pytest, pypdf, requests, reportlab, streamlit.
3. Make the GitHub repo PUBLIC before submitting. Submission form by 6:00 PM. Under
   "written before 10:15 AM", declare the planning docs (AGENTS.md, PLAN.md, TASKS.md,
   agent prompts); no code was written before the start.
4. Eval slides 6 and 7: market_size and customer come out HELD (sources/web.py does not
   exist; customer has no checker). HELD is the honest result under our rules. Either
   build sources/web.py (codex-a) or change the answer key to HELD and say so in README.
5. Founder claims: resolve needs get_people and search_people in sources/crust.py (D12).
   Until then founder lookups fail, so Deck A has no founder slide.
6. rules.yaml: every value is still PLACEHOLDER, including D14's
   tolerances.funding.max_record_age_days: 3650, which the merger placed. Finance
   partner confirms or changes them; it's a config edit, not code.
7. Dated facts worth a Deck B: Crustdata shows Locus acquired_by Ingka Investments on
   2025-10-06, and funding.milestones[] holds all 7 rounds with dates.
