# TEAMMATE_BRIEF.md: test decks, rule values and the business docs

For: the teammate who owns test decks and the human-owned docs. From: harshit (merger).
Date: 2026-11-22. Code freeze is 18:00 IST. Everything here is non-code or test-only, so it
does not clash with the four coding sessions (T30 to T33, web source).

Read first, about 15 minutes:
- `AGENTS.md`, sections 2 and 5. These are the hard rules; breaking one can disqualify the team.
- `README.md`. It says what works today, with the live Deck A results.
- `docs/WEB_SOURCE.md`. Market-size and customer claims will use web search after the four
  web tasks merge.

## How to work

- Clone or pull `main`, then make your own branch: `git switch -c lane/teammate`. Only
  harshit merges to `main`.
- Claim a task in `TASKS.md` before you start it. Commit that change alone:
  `[teammate] tasks: claim T05`.
- Commit messages look like `[teammate] decks: add deck B`, and you commit small and often.
  Never force-push.
- When you stop, add an entry to `HANDOFF.md` using the template in that file, then push.
- Never commit a `.env` file or a key. Never put a real person's contact details in a deck or doc.

## Task 1 (T05 / T21): Decks B and C, with answer keys

### Why we need them

Our eval runs only Deck A, and the judges test with hidden decks: lookalike names, questions
that can't be answered, and a requirement change. Two more decks show that the system decides
correctly and not just on one example.

### What each deck needs (copy Deck A's files)

| File | What it is | Deck A example |
|---|---|---|
| `tests/decks/make_deck_<x>.py` | builds the PDF with ReportLab, every slide as selectable text, with the footer "Synthetic test deck for DeckCheck. Not issued by <company>." | `make_deck_a.py` |
| `tests/decks/deck_<x>.pdf` | the generated deck, 6 to 10 slides, one claim per slide, slide 1 a title with the deck date | `deck_a.pdf` |
| `tests/decks/deck_<x>_request.json` | the request: `deck_path` (repo-relative), `company_domain`, `deck_date`, `founder_urls` | `deck_a_request.json` |
| `tests/decks/deck_<x>_answers.yaml` | the answer key, one entry per claim slide: `slide`, `quote`, `expected_verdict`, `expected_reason_code`, `basis` | `deck_a_answers.yaml` |
| `tests/eval/deck_<x>_claims.json` | what extraction should produce per claim: `type`, `metric`, `value`, `unit`, `as_of` | `deck_a_claims.json` |

You don't make the recorded Crustdata response (`tests/fixtures/crustdata/deck_<x>_*_company.json`).
Recording it costs about 2 credits and needs the key, so ask harshit when your request file is ready.

### What to put in the decks

Use real Indian logistics-tech or SaaS companies whose facts you can see on Crustdata or in
dated news, then write claims that are deliberately right, wrong or uncheckable. Every deck
needs a mix of all three:

| Claim | Write it so the right answer is | Why it matters |
|---|---|---|
| headcount close to the real number | SUPPORTED | the basic happy path |
| headcount or funding clearly inflated (2x) | CONTRADICTED | catches a false claim |
| a funding round with stage, amount and month | SUPPORTED or CONTRADICTED | date matching on funding milestones |
| founded year (exact, then one year off) | SUPPORTED / CANNOT_VERIFY | the company_fact rule from T29 |
| a named customer with a real press release | SUPPORTED (independent mention) | the web customer check |
| a named customer found only on the company's own site | CANNOT_VERIFY `self_reported_only` | self-published proof isn't counted |
| a market size quoted in a dated report | SUPPORTED within 50% | the web market-size check |
| revenue or ARR the company never published | CANNOT_VERIFY | nothing to check against must never become a verdict |
| a fact dated after the deck date | NOT_COMPARABLE `record_after_as_of` | the date rule (D3) |

- **Deck B:** a clean company with several funding rounds and public customers. Mostly
  checkable claims.
- **Deck C, the trap deck:** a company whose name has a namesake, e.g. two companies called
  the same in different countries. Include claims about founders and a prior exit; founder
  lookups aren't built yet, so the honest answer is CANNOT_VERIFY or HELD. The goal is
  **zero wrong SUPPORTED or CONTRADICTED**.

### Rules for the answer key (most important)

- Write the expected verdict **from the evidence**, never from what our system outputs. If
  our output and the key disagree, that's a finding; note it in HANDOFF, don't change the key.
- `basis` names the source, the exact field or quote, and the record's date, e.g.
  "Crustdata headcount 349 on 2026-11-02".
- Use these labels: SUPPORTED, CONTRADICTED, NOT_COMPARABLE, CANNOT_VERIFY, HELD. Use `TBD`
  if you can't decide; the eval skips it. The reason codes are listed in `verdict/DESIGN.md`
  section 4.

**Done when:** for each deck, the PDF opens with selectable text, all four files exist, and
`python tests/eval/run_eval.py --deck b` runs once harshit has added the recorded response.

## Task 2 (T05): real values in `config/rules.yaml` (finance partner)

Every value marked `PLACEHOLDER` is a guess by an engineer. For each one, either confirm it
by deleting the word PLACEHOLDER or change it, and add a one-line reason in the comment. The
most important ones:

| Key | Now | Question to answer |
|---|---|---|
| `tolerances.team_size.tolerance_pct` | 20 | How far off can a headcount claim be and still count as true? |
| `tolerances.funding.tolerance_pct` and `max_record_age_days` | 10 / 3650 | Funding gap allowed; how old a round still counts |
| `tolerances.market_size.tolerance_pct`, `min_agreeing_sources` | 50 / 2 | Market reports vary; how many agreeing sources before we call a claim false? |
| `tolerances.company_fact.year_gap_cannot_verify` | 1 | A founded-year gap of 1 year: unsure or wrong? |
| `tolerances.hiring`, `traction`, `team_growth` | 30 / 15 / 25 | Allowed gaps |
| `limits.max_cost_inr`, `max_credits`, `max_seconds` | 500 / 200 / 900 | The most one deck may cost and take |
| `costs.crustdata.inr_per_credit` | 1.0 | The real rupee price of a Crustdata credit on our plan |
| `costs.llm.default` | 0.25 / 1.25 per 1k tokens | The real rupee price of our LLM (gpt-4o-mini) |
| `materiality` | 1 to 5 | Which wrong claims hurt an investor most? This ranks the red flags. |
| `title_levels`, `founder_background.min_title_level` | director | What title counts as "senior"? |

Also rewrite the wording in `report/question_templates.yaml`, the founder questions and
evidence requests. The tone stays neutral; the report is advice, never a rejection. Keep the
`{placeholders}`; a misspelled one fails loudly.

**Done when:** no PLACEHOLDER is left that you didn't consciously keep, and `python -m pytest
-q` still passes. Tests read some of these values, so run them after every change.

## Task 3 (T24): BUSINESS.md

Judges score finance at 25 points. Write it for a VC partner, one page:
1. **Buyer:** small Indian VC funds, angel networks, and corporate-venture desks such as a 3PL
   screening logistics startups.
2. **What it replaces:** an analyst checking a deck before the second meeting, 3 to 8 hours.
   Put the analyst's cost per deck in rupees.
3. **Our cost per deck, measured from the ledger, not guessed.** Deck A live run: 4 calls,
   2 Crustdata credits, ₹2.79, 16.5 seconds (README, "Live run"). With web search on, add
   about 8 credits per deck. Ask harshit for the new number after the next live run.
4. **Price per deck** and the margin. A small table of price, cost and analyst cost.
5. **What scaling to 100x needs:** a queue, a shared cache, rate limits (Crustdata web
   endpoints allow 10 requests per minute), and a ledger per client.
6. **Risks:** data coverage gaps (many claims end Cannot verify), and provider price changes.

## Task 4 (T24): ETHICS.md

Judges score ethics at 25 points. One page:
1. **What we store about founders:** only professional fields. No emails or phones (dropped
   on the way in), and no raw person payloads.
2. **Namesakes:** the two-signal identity rule. A person or company is matched only on 2
   independent signals.
3. **Every verdict is explained** with its source and date; facts from the model's memory are
   forbidden.
4. **Humans decide:** the founder email waits for a person's approval, goes only to a local
   test inbox, and is sent exactly once.
5. **The output is advice,** never an automatic rejection. Cannot verify is not a red flag.
6. **Web pages:** we quote at most one sentence per page and link the source.

## Task 5 (T26): demo script and rehearsal

Write `docs/DEMO.md`: a 2-minute script for the video, plus 3 live-fix drills. Example
drills: change a tolerance in rules.yaml; add an output field in `output.fields`; raise or
lower a limit and show claims becoming HELD. Rehearse twice, including killing a run with
Ctrl-C and running `python cli.py resume <run_id>`. The video is due by 17:30.

## Order, if time is short

1. Task 5, the demo video (due 17:30).
2. Tasks 3 and 4, BUSINESS.md and ETHICS.md (50 judge points between them).
3. Task 2, the rules.yaml values.
4. Task 1, Decks B and C.

Questions: write them under "Open questions" in your HANDOFF entry and message harshit.
