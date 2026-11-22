# AGENTS.md — rules for every AI account working on DeckCheck

Every coding agent (Claude Code, Codex, Antigravity, any account) reads this file
FIRST, every session, before touching code. Humans on the team follow it too.

DeckCheck checks every factual claim in a startup's pitch deck against live data
and returns a verdict per claim (Supported / Contradicted / Not comparable /
Cannot verify / Held), each with a dated source. A founder email is drafted and
held for human approval.

Read next: `PLAN.md` (architecture, contracts, lanes), `TASKS.md` (who does what),
the last 3 entries of `HANDOFF.md` (where the previous account stopped),
`DECISIONS.md` (changes to contracts and requirements).

---

## 1. Start-of-session ritual (do all five, in order)

1. Read this file, `PLAN.md` section "Contracts", and the last 3 `HANDOFF.md` entries.
2. Open `TASKS.md`. Pick ONE task in your lane whose status is `todo`, or continue
   the `in-progress` task the last handoff names for your lane.
3. Write your account label and `in-progress` on that task in `TASKS.md`
   (example: `codex-2`). Commit that change alone: `[lane] tasks: claim T07`.
4. `git pull` before you start. Work only in the folders your lane owns (PLAN.md, "Lanes").
5. If anything in the handoff is unclear, run the tests it names before writing new code.

## 2. Hard rules from the hackathon (breaking these can disqualify the team)

- **No hard-coded answers.** Never store expected verdicts, sample API responses or
  demo output in the runtime path. Test fixtures live only in `tests/`.
- **No mock data at runtime.** Every verdict comes from a live call made during the run.
  Mocks are allowed only inside `tests/`.
- **Every fact has a source.** Each piece of evidence stores: source type, URL or API
  endpoint, the exact field name or exact quote, the record's own date, and the time
  we retrieved it. No source, no fact. Facts from model memory are forbidden.
- **The LLM never decides numbers, dates, comparisons or verdicts.** It only extracts
  claims, picks exact quotes from fetched pages, and writes explanations. Code decides.
- **Nothing irreversible without approval.** The founder email is drafted with status
  `pending`. Only a human click changes it to `approved`. Sending goes only to the
  team's test inbox, never to a real person.
- **Every action happens exactly once, even after a kill.** Use the idempotency key
  rules in PLAN.md. Never write code that "just retries the send".
- **Every external call writes a ledger row** (provider, endpoint/model, credits or
  tokens, rupee cost, duration, run id). No exceptions, including failed calls.
- **Respect the run limits** in `config/rules.yaml` (`max_cost_inr`, `max_seconds`).
  When a limit is hit, remaining claims become `HELD` with reason `budget` or `time`.
- **Timeouts and errors become `HELD`, never `CANNOT_VERIFY`.** A slow source is not
  a missing source.
- **Git:** no force-push, no rebase of pushed commits, no amending pushed commits, no
  editing logs or ledger rows. Small commits, often.
- **Secrets** live in `.env` only (gitignored). Never print or commit keys.
- **Open-source code** you copy or adapt gets a line in README "Credits" with its licence.

## 3. Coding rules

- Python 3.11. Type hints on every function. Dataclasses / Pydantic models live ONLY
  in `core/models.py`.
- **Do not change a contract** (anything in `core/models.py`, the DB schema in
  `core/store.py`, or a function signature listed in PLAN.md) without writing a
  `DECISIONS.md` entry first and telling a human.
- Tolerances, title levels, materiality weights, limits and output fields live in
  `config/rules.yaml`. Never hard-code them. (The organizers change one requirement
  at hour 3; it should be a config edit, not a rewrite.)
- Every file starts with a 3–5 line docstring: what it does, what calls it, what it
  calls. Humans must explain this code to judges and fix it live in 5 minutes.
- Every checker has at least one test in `tests/checkers/` that uses a recorded
  fixture (fixtures in tests only).
- Log with `core/log.py` (one line per step: run id, claim id, step, result). No print().
- Keep functions short. Prefer boring, readable code over clever code.

## 4. Commit rules

- Message format: `[lane] module: what changed` — e.g. `[codex] crust: add 429 backoff`.
- Commit after every working step (roughly every 15–30 minutes).
- Work on your lane branch (`lane/claude`, `lane/codex-a`, `lane/codex-b`, `lane/ag`).
  Only a human merges into `main`, after `pytest -q` passes.
- `git pull --rebase` only on commits that are NOT pushed yet. Otherwise plain merge.

## 5. End-of-session ritual (MANDATORY)

Do this when ANY of these is true: your task is done, you have worked ~45 minutes,
your context is getting long, or the account is near its usage limit. If you sense
the limit is close, do this FIRST and stop coding.

1. Make sure the code runs or is clearly marked broken. Commit it.
2. Append an entry to `HANDOFF.md` using the template in that file. Be specific:
   exact file names, the exact next step, the exact command to test.
3. Update `TASKS.md`: status `done`, `in-progress` (with % and next step) or `blocked`
   (with why).
4. If you made a decision that changes behaviour, add it to `DECISIONS.md`.
5. If you added or changed something a human may need to change live, add a line to
   `docs/LIVE_FIX_MAP.md` ("To change X, edit Y in file Z").
6. Commit: `[lane] handoff: <task id> <one line>` and push.

An account that stops without a handoff entry has wasted the next account's time.

## 6. When you are unsure

- About the kickoff kit's input/output format, the client's request, or the rules:
  do NOT guess. Add the question to the "Open questions" part of your HANDOFF entry
  and tell the human.
- About another lane's code: read its handoff entry, do not edit its folder.
- About a verdict rule: it belongs to the finance partner in `config/rules.yaml`.
