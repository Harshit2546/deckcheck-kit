# DeckCheck explained from zero

Written for someone who knows only the overview. Every number comes from the repo on `main`
(commit `8b7343e` at about 16:55 IST). Where something is an estimate or a placeholder, it says so.

---

## 1. The one-minute version

**The job.** Before a venture fund meets a startup a second time, an analyst reads the pitch
deck and checks each factual claim: "350 employees", "raised a $50M Series C in 2021",
"customers include Acme". That takes 3 to 8 hours per deck.

**What DeckCheck does.** You give it the deck PDF, the company's website domain and the deck's
date. It:

1. reads the deck and lists every factual claim (with the exact quote and slide);
2. finds the real company and founders in live data (Crustdata);
3. fetches the matching facts and keeps each fact's own date;
4. gives every claim one of five verdicts, chosen by plain Python rules, not by the AI;
5. writes a report (red flags, questions for the founder, documents to request, cost);
6. drafts an email to the founder and **holds it** until a human clicks approve. When approved,
   it is "sent" once into a local test inbox (no real email leaves the machine).

**Why it is trustworthy.** The AI only does two mechanical things: list claims, and copy one
sentence from a web page. Every number, date, comparison and verdict is decided by code.
Every fact shows its source, the exact field or quote, the record's date and when we fetched it.
When it cannot check something, it says "cannot verify" and names what is missing.

---

## 2. Where we changed from the plan, and why

The plan (`PLAN.md`, written before 10:15 AM) was a good skeleton. These are the places reality
forced changes. Each one is a written decision in `DECISIONS.md`.

| # | Plan said | What happened | Why | Where |
|---|---|---|---|---|
| 1 | One Claude lane, several Codex accounts | Two Claude lanes (`claude-core`, `claude-verdict`), one Codex lane, Gemini lanes | We had 2 Claude Pro, 1 ChatGPT Plus, 3 Gemini accounts | D2 |
| 2 | Data models in a Pydantic-style file | Plain Python dataclasses, times as ISO strings | Simpler, no extra dependency; a first version pushed to `main` by mistake was reverted | D5, `INCIDENTS` E1 |
| 3 | Adapter at `io/adapter.py` | Still `io/adapter.py`, but loaded by file path | Python's built-in `io` module owns the name, so `import io.adapter` fails. Moved to `kit_io/` (D4), then moved back (D6) with a loader | D4, D6, `core/adapter_loader.py` |
| 4 | "Use the kickoff kit's format" | No format was in our files, so we defined our own request/result JSON | Handbook says only that formats come at kickoff | D3 |
| 5 | Each lane guesses how the runner calls it | Fixed function shapes per stage (`extract.claims:run`, `checkers.<type>:check`, `verdict.engine:decide`, ...) | Lanes needed one contract to code against in parallel | D7 |
| 6 | Compare the claim with whatever Crustdata returns | Only facts dated on or before the deck date count | The handbook says "no fact from after that date". Crustdata's headcount total has only a refresh date | D3, D13 |
| 7 | Use `headcount.total` | Use the latest dated point from `headcount.timeseries[]` | The total is undated; the history point has its own date (349 on 2026-11-02) | D13 |
| 8 | One record-age limit (365 days) | A limit per claim type (funding 3,650 days, founder 18,250, customer 1,095) | Locus's funding rounds are from 2016 to 2021; a 365-day limit would have made every funding claim "stale" | D14 |
| 9 | Funding from a list of rounds | Read `funding.milestones[]` | The field the plan assumed (`funding_rounds`) is absent in the live record; milestones holds all 7 rounds with dates | `INCIDENTS` B2 |
| 10 | Customer claims verified by "web quote verify" in a Codex lane | Built on Crustdata's own web search + fetch; the page's publish date is read from its HTML | Search results carry no date; a fact needs one | D16 |
| 11 | Undated records never count | A guarded fallback: an undated record may be used at low confidence if the deck is at most 90 days older than the fetch | Without it, nearly every web claim ended "cannot verify" | D17 |
| 12 | Founder lookups later | Built live: `get_people` and `search_people` | Needed to check "previously worked at Amazon" | D18, D19 |
| 13 | Verdict rules for three claim types | Rules for ten (hiring, traction, company fact, prior exit, team growth, market size, customer added) | Claim types the extractor can produce all need an answer | D15 |
| 14 | Email "sent" to a test inbox | A table named `inbox` inside the same SQLite file; no mail code exists | Rulebook: agents never contact real people | `actions/email.py` |
| 15 | 7-hour build, freeze 17:15 | Freeze is **6:00 PM**; handbook asks for a **2-minute video** | Real event schedule | Handbook |
| 16 | "Hour-3 requirement change" (T20) | Not received in our notes; T20 is still `todo` | Check the WhatsApp group | `TASKS.md` |
| 17 | UI shell in Streamlit | Streamlit app with a custom look (dark, Apple-style palette), seven pages and small JS widgets | Judges see this; also a human clicks approve here | T28, T38 |

---

## 3. One claim, followed through the code

Take slide 2 of Deck A: *"Locus has a team of 350 people."* The run command is
`python cli.py run --request tests/decks/deck_a_request.json --out out/result.json`.

1. **`cli.py` `main`** reads the request file through **`io/adapter.py` `from_kit`**, which
   returns a `RunInput` (deck path, domain `locus.sh`, deck date `2026-11-15`, founder URLs).
   It makes a run id, opens the database (`core/store.py` `connect`) and calls
   **`core/runner.py` `start`**.
2. **Runner state CREATED -> `_extract`** calls **`extract/claims.py` `run`**:
   - `extract/pdf.py` `extract_pdf_slides` returns `{1: "...", 2: "..."}` slide text.
   - `extract_claims` builds one prompt, calls the LLM (`_default_llm_call`, OpenAI gpt-4o-mini; the Gemini branch is disabled in code),
     and writes a **ledger row** with tokens and rupees (`core/ledger.py` `record`).
   - `_parse_claims_json` turns the reply into `Claim` objects. "5M" becomes 5,000,000
     (`_parse_numeric_value`).
   - `verify_claim_quotes` **drops any claim whose quote is not on its slide**. The AI can
     therefore never invent a claim.
   - The runner gives each claim a fixed id (`<run>-c001`) and saves them, state `EXTRACTED`.
3. **State EXTRACTED -> `_resolve`** calls **`resolve/entities.py` `run`**. It asks Crustdata for
   the company by exact domain (`sources/crust.py` `get_company`) and counts independent
   signals: domain matched, name matched, a deck founder is in the company's founder list. Two
   signals means `confirmed`; fewer means `unclear`. Result saved (`save_resolution`).
4. **State RESOLVED -> `_check_and_decide`** loops over the claims. For our claim:
   - `_check_one` first asks **`core/limits.py` `limit_reason`**: has the run used its rupee,
     credit or time budget? If so, the claim is HELD (`budget` or `time`).
   - It then calls **`checkers/team_size.py` `check`**. That reads the cached company record,
     picks the latest `headcount.timeseries[]` point dated on or before 2026-11-15 (349 on
     2026-11-02) and returns a `CheckResult`: `Evidence` rows (source, field name, value,
     record date, fetch time, ledger id) plus an `observed` dictionary.
   - Any timeout, error or missing checker becomes HELD with a reason, never "cannot verify".
   - `save_check_result` writes the evidence and sets the claim to `checked` in one
     transaction. If the program is killed after this line, resume will not call Crustdata again.
   - **`verdict/engine.py` `decide`** turns claim plus result into a verdict. Order: held?
     then no evidence? then identity unclear/not found? then not comparable? then date rules
     (a record after the deck date is `record_after_as_of`; too old is `stale_record`) then the
     per-type rule. `verdict/team_size.py` compares 349 with 350: difference 0.3%, tolerance 20%
     from `rules.yaml`, so **SUPPORTED / within_tolerance**, high confidence because the record is
     fresh and the gap is under half the tolerance. For "700" the gap is 50%, so
     **CONTRADICTED / outside_tolerance**, medium confidence (headcount is a derived number, so
     the engine never says "high" for a contradiction on it).
   - `save_verdict` marks the claim `decided`.
5. **State DECIDED -> `_report`** calls **`report/builder.py` `build`**, which reads everything
   from the database and returns the report JSON and Markdown: red flags ordered by weight in
   `rules.yaml` `materiality`, the claim table (columns picked by `output.fields`), founder
   questions from `report/question_templates.yaml`, a list of evidence to request, and ledger totals.
6. **State REPORTED -> `_draft`** calls **`actions/email.py` `draft`**, which writes the founder
   email with status `pending`. The run is `DONE`.
7. **`cli.py` `write_result`** writes `out/result.json` (through `io/adapter.py` `to_kit`) and
   `out/result.md`.
8. **A human opens the UI**, Approvals page, types their name and clicks. That calls
   `actions/email.py` `approve` then `send_approved`: `approved -> sending` is committed, then
   one transaction inserts the row into the `inbox` table (which has a UNIQUE key on the
   idempotency key) and sets `sent`. After a crash, `reconcile` finishes any email left in
   `sending`. There is no retry loop around the send, on purpose.

**Kill and resume.** `cli.py resume <run_id>` calls `runner.resume`, which loads the run's state
and runs only the steps still open. Finished claims are skipped because they are already
`checked` or `decided`.

---

## 4. Folder by folder, with the reason for each function

### `core/`: the spine (about 1,150 lines)
| File | What it does | Why it is built this way |
|---|---|---|
| `models.py` | Every shape of data: `Claim`, `Evidence`, `CheckResult`, `Verdict`, `LedgerEntry`, `Action`, run and claim states, `HeldReason`, `RunContext`, `make_idempotency_key` | The only place contracts live. Other lanes code against it, so a change needs a decision entry |
| `store.py` | SQLite schema and every read/write: runs, claims, evidence, check_results, verdicts, ledger, actions, inbox, resolutions, reports | `save_check_result` and `save_verdict` are single transactions so a crash never leaves a half-saved claim. Ledger and inbox rows are protected by database triggers from edits |
| `runner.py` | The state machine (`STEPS`, `_drive`), `start`, `resume`, and `STAGES`, the table naming which module does each stage | Imports each stage by name so a missing module makes a claim HELD instead of crashing the run |
| `limits.py` | `limit_reason`, `ensure_within`: compares ledger totals and elapsed time with `limits` in `rules.yaml` | Checked before every external call. Elapsed time counts from the first start, so resuming cannot reset the clock |
| `ledger.py` | `record` writes one row per external call (provider, endpoint or model, credits, tokens, rupees, duration, ok, error); `cost_inr` turns usage into rupees from `rules.yaml costs` | Failed calls are recorded too, so cost records are honest |
| `config.py` | `load_rules`, `rule("a.b.c")`; fails fast if a needed key is missing | A bad live edit of `rules.yaml` is caught at start, not mid-demo |
| `log.py` | One line per step: run id, claim id, step, result | Judges read logs; no `print` anywhere |
| `adapter_loader.py` | Loads `io/adapter.py` by file path | Works around the `io` name clash |

### `io/adapter.py`: the doorway (92 lines)
`from_kit` maps a request JSON to `RunInput` and rejects a bad date or missing field with a clear
message. `to_kit` maps the report to the result JSON, keeping the field order from
`rules.yaml output.fields`. If the organizers publish an official format, this is the only file to change.

### `extract/`: reading the deck (about 640 lines)
- `pdf.py` `extract_pdf_slides`: slide text with `pypdf`. Text-based PDFs only.
- `claims.py`: `extract_claims` (LLM call + ledger row), `_parse_claims_json`,
  `_parse_numeric_value` (turns "$2.5M" into a number), `verify_claim_quote(s)` (quote must be on
  the slide), `_extract_pdf_creation_date` (fallback deck date, flagged), and `run`, the
  runner's entry point. **Why:** the LLM is allowed to propose claims, but code gets the last word.
- `quotes.py`: for web pages, `pick_quote` asks the LLM for one sentence copied exactly from the
  page; `_accept` checks the sentence is really on the page; `parse_amount` reads "$9 billion" or
  "crores" by code. **Why:** the number comes from code reading the sentence, not from the model.

### `resolve/`: who is this company, who are these people (about 330 lines)
`entities.py` `resolve_company`, `_company_signals`, `_person_signals`, `_from_urls`,
`_by_search`, `run`. `names.py` normalises names (drops "Pvt Ltd", ignores order in person names)
and domains. `payloads.py` reads the provider's person and company shapes. **Why:** namesakes.
The hidden tests include lookalike names, and a wrong match is worse than "unclear".

### `sources/`: the outside world (about 790 lines)
- `crust.py`: `get_company`, `get_people`, `search_people`. Handles pacing from the account's
  rate limit, one retry after HTTP 429, per-call timeout, a ledger row per attempt, a 60-second
  cache per run, and `drop_contact_fields`, which strips emails and phones recursively.
- `web.py`: `search` and `fetch` through Crustdata's web endpoints, with their own longer
  timeout for pages.
- `pages.py`: `page_text` and `published_date`, which finds a page's publish date in JSON-LD,
  `article:published_time`, meta tags or `<time>`. **Why:** search results have no date, and a fact
  without a date is not allowed to decide a verdict (except under the D17 guard).

### `checkers/`: fetch and normalise, never judge (about 2,100 lines)
One file per claim type: `team_size`, `team_growth`, `funding`, `hiring`, `traction`,
`market_size`, `competition`, `customer`, `company_fact`, `prior_exit`, `founder_background`.
`_common.py` holds the shared company fetch and identity keys. Each returns evidence plus an
`observed` dictionary whose keys are listed in `verdict/DESIGN.md`. **Why separate from the
verdict:** the same checker output can be judged under different tolerances, which is exactly
the "live fix" a judge may ask for.

### `verdict/`: the rule engine (about 1,030 lines)
`engine.py` `decide` runs the common order (see section 3), then `_route` sends the claim to
`team_size.py`, `funding.py`, `founder.py`, `hiring.py`, `traction.py`, `company_fact.py`,
`prior_exit.py`, `team_growth.py`, `market_size.py` or `customer.py`. `common.py` has helpers
(`rel_diff`, `cap` for confidence ceilings, `make`). `DESIGN.md` is the written rule book.
Notable cautious rules:
- a funding total *lower* than the deck is "cannot verify", not "contradicted" (databases miss rounds);
- a person missing a past employer in their profile is never a contradiction;
- a market-size claim needs two agreeing sources from different domains to be contradicted;
- competition claims are never judged (always "cannot verify").

### `report/` (223 lines)
`builder.py` `build` (read-only on the database) and `render.py` (Markdown). Output columns come
from config, so adding one is a config edit.

### `actions/email.py` (156 lines)
`draft`, `approve`, `reject`, `send_approved`, `reconcile`, `check_recipient` (refuses any
recipient other than the test inbox in `rules.yaml`). No SMTP or HTTP mail library is imported.

### `ui/`: Streamlit (about 1,230 lines)
Seven pages: **Run** (start from a request file, an upload or flags; resume), **Report**,
**Claims** (verdicts with sources), **Entities** (who we matched), **Approvals** (typed name, then
approve or reject), **Inbox** ("local test inbox, no real email"), **Ledger** (calls, credits,
rupees, seconds). The UI reads through `core/store.py` and acts only through `actions/`.

### `config/rules.yaml`: every number you might change live
`limits` (cost, time, credits, per-call timeout), `costs` (rupee rates), `web`, `identity`
(min signals), `tolerances` (per claim type), `verdict` (confidence margins, undated fallback),
`title_levels`, `materiality` (red-flag weights), `output.fields`, `actions.test_inbox`. The
live-fix list is in `docs/LIVE_FIX_MAP.md`.

### Tests: about 6,500 lines, 477 passing
Includes a test that kills the process mid-run and resumes, tests that the UI never writes
claims or ledger rows, and `tests/eval/run_eval.py`, which replays Deck A through the real code
and scores it against `tests/decks/deck_a_answers.yaml`.

---

## 5. Database tables (all in one SQLite file)

`runs`, `claims`, `evidence`, `check_results`, `verdicts`, `ledger`, `actions`, `inbox`,
`resolutions`, `reports`. Ledger and inbox cannot be edited (triggers). `actions` and `inbox`
each have `UNIQUE(idempotency_key)`; the key is the hash of run id, action type and recipient.

---

## 6. How it was built, in one paragraph

Two people, six AI sessions, each owning its own folders ("lanes"): `claude-core` (core, runner,
adapter, email), `claude-verdict` (resolve, verdict, report, reviews), `codex-a` (Crustdata
client), `ag-b` (extraction and checkers), `ag` (UI), plus a teammate session (docs, decks) and
later web-source sessions. Rules in `AGENTS.md` (read first by every session), decisions in
`DECISIONS.md`, a baton in `HANDOFF.md`, tasks in `TASKS.md`. Merges happened in a scratch copy with
the full test suite run after each lane; conflicts were only ever in the shared docs.
`docs/INCIDENTS.md` lists every failure and near miss.

---

## 7. Is it complete? Honest status at about 17:00 IST

| Piece of the idea | Status |
|---|---|
| Read deck, extract claims, verify quotes | Done, live-tested |
| Resolve company and founders (two-signal rule) | Done, live-tested (Deck A, Deck F) |
| Check team size, funding, founder background, market, customer | Done and live-tested; web claims often end "cannot verify" because pages have no dates |
| Check hiring, traction, team growth, prior exit, company fact, competition | Built with rules; **hiring has no dated field, so it stays "cannot verify"**; competition is never judged by design |
| Code-decided verdicts with dated sources | Done. Deck A live run: 4 decided, 3 left open, none wrong against the key |
| Report, ledger, cost per deck | Done. About ₹12 per deck at **placeholder rupee rates** |
| Kill and resume | Done and demonstrated (a real bad-key run was resumed) |
| Human-approved, exactly-once email | Done, to a local inbox only |
| UI | Done (7 pages). The raw-icon-text bug from the 17:05 handoff was fixed in ui/theme.py |
| README, architecture, ethics, business, incidents | Written. README "Known limits" and BUSINESS rates need a last honesty pass |
| Answer keys | Deck A full (6 scored). Decks B and C have every row TBD (no recorded data); Deck F has 2 founder claims |
| Hour-3 requirement change | **Not recorded** (T20 todo). Ask in the WhatsApp group whether it was announced |
| Kickoff-kit official format | Not in our files; we use our own (D3) |
| Real values in `rules.yaml` | Still placeholders (43 marked). The code runs; the judges may ask about them |

**Rough measure:** the pipeline is about 90 percent of the original idea. What is missing is
breadth of proof (one deck with a full key), dated hiring data, and finish (icons bug, placeholders).

---

## 8. What must happen before 6:00 PM

Times are IST. Code freeze 18:00. Handbook: README and video around 17:30.

| By | Who | Task |
|---|---|---|
| now | Merger (harshit) | Fix or hide the UI icon bug (raw `keyboard_double_` text). Judges see the UI first |
| 17:20 | Anyone | Make the GitHub repo **public** (it was private at 16:55). Check commit history starts after 10:15 |
| 17:20 | Anyone | Ask the WhatsApp group whether the hour-3 requirement change was announced. If yes, it is a `rules.yaml` or output-field edit |
| 17:25 | One person | Live run of Deck A on the demo laptop, then rehearse kill (`Ctrl+C`) and resume once |
| 17:30 | One person | Record the 2-minute video from that run (script in `pitch/LAUNCH_VIDEO.md`) |
| 17:40 | One person | Upload the video as unlisted (Loom, YouTube or Drive), test the link in a private window |
| 17:45 | Merger | Final merge, tests, push `main`. No new features |
| 17:50 | One person | Fill the submission form: team name, one line, theme, repo link, video link, "how does it work", diagram link, "written before 10:15" (planning docs only), every member's details |
| 17:55 | Everyone | Check the README claims against what runs. Remove anything false |
| 18:00 | | Freeze |

If time is short, cut in this order: polish, Decks B and C, extra UI pages. Never cut: the live
Deck A run, the video, the public repo, the README.
