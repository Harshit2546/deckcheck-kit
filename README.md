# DeckCheck

DeckCheck checks the factual claims in a startup's pitch deck against live data.
Each claim gets a verdict (Supported, Contradicted, Not comparable, Cannot verify or
Held), a reason and dated sources. The system drafts a founder email and holds it until
a person approves it.

Built at ContextCon 05 (Investing track).

## The job

**Service it replaces:** a VC analyst or diligence firm checking a deck before the
second meeting. That takes 3 to 8 analyst hours per deck.

**Who pays:** the client's strategic-investment / corporate-venture desk, which screens
logistics-tech startups it may invest in, acquire or partner with. Small Indian VC funds
and angel networks need the same check. The price is per deck, in rupees. Each run's
real cost is in its ledger.

**Input:** a text-based deck PDF, the company domain and the deck date, plus optional
founder profile URLs. These come as a request JSON
([tests/decks/deck_a_request.json](tests/decks/deck_a_request.json) is the real Deck A
request) or as command-line flags. `io/adapter.py` maps the kickoff-kit format to the
internal one.

**Result:**
- a claim table: quote, slide, claimed value, verdict, reason code, confidence,
  explanation and sources
- red flags ranked by materiality
- questions for the founder and a list of evidence to request
- the run ledger with rupee cost
- a founder email in `pending` state

The output is a result JSON plus a Markdown report written next to it.

**Pass mark:**
- On our answer key, no Supported or Contradicted verdict is wrong.
- Every claim that is not decided is Cannot verify or Held, with a reason.
- The founder email is sent exactly once after approval, including after a kill.

## How it works

```
io/adapter -> extract      -> resolve         -> checkers/<type>    -> verdict/engine -> report     -> actions
kit format    PDF text,       company by         live Crustdata       label chosen      red flags,    email draft,
to internal   LLM claims,     domain, founders   call, returns        by code from      questions,    human approval,
              code checks     by two-signal      Evidence with a      config/rules.yaml ledger        send exactly once
              each quote      identity rule      record date
```

- **The LLM never decides.** It only extracts claims and quotes. Code checks that every
  quote is on its slide. `verdict/engine.py` decides every label from
  `config/rules.yaml`.
- **Every fact has a source.** Each Evidence row stores the source, the URL or endpoint,
  the exact field or quote, the record's own date and `retrieved_at`.
  - Only facts dated on or before the deck date count (DECISIONS D3, D13, D14).
- **Every external call writes a ledger row**, failed calls included. The row holds the
  provider, endpoint or model, credits or tokens, rupee cost, duration and run id.
- **Limits:** `max_cost_inr`, `max_seconds` and `max_credits` are in `config/rules.yaml`.
  When a limit is hit, a call times out or a source fails, the claim becomes **Held**,
  never Cannot verify.
- **Kill and resume:** the run and every claim are checkpointed in SQLite.
  `cli.py resume <run_id>` skips work that is already done.
- **Exactly-once email:** the email row goes `approved -> sending` in one transaction.
  It is then inserted into a local `inbox` table that has `UNIQUE(idempotency_key)`.
  Nothing is sent to a real person; the inbox is a local test table.

## How to run

Requires Python 3.11.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Put the keys in `.env` at the repo root. The file is gitignored. It needs
`CRUSTDATA_API_KEY`, plus `GEMINI_API_KEY` or `OPENAI_API_KEY` for claim extraction.
If both LLM keys are set, Gemini is used.
Load it into the shell before a run, because the extraction step reads the keys from
the environment:

```bash
set -a; . ./.env; set +a
```

Run Deck A:

```bash
python cli.py run --request tests/decks/deck_a_request.json --out out/result.json
```

After a kill:

```bash
python cli.py resume <run_id> --out out/result.json
```

The UI (run, claims, approvals, inbox and ledger pages):

```bash
streamlit run ui/app.py
```

All tests:

```bash
python -m pytest -q
```

Offline eval against the Deck A answer key:

```bash
python tests/eval/run_eval.py
```

The offline eval replays a recorded Crustdata response. Only tests use recorded data.

## Results

### Offline eval, Deck A (Locus, locus.sh, deck date 2026-11-15)

This replay runs the real runner, resolve, checkers and engine on the recorded company
response.

| Slide | Expected | Actual | |
|---|---|---|---|
| 2 | SUPPORTED / within_tolerance | SUPPORTED (high) | PASS |
| 3 | SUPPORTED / within_tolerance | SUPPORTED (medium) | PASS |
| 4 | SUPPORTED / within_tolerance_undated_rounds | SUPPORTED (low) | PASS |
| 5 | CONTRADICTED / outside_tolerance | CONTRADICTED (medium) | PASS |
| 6 | CANNOT_VERIFY / no_evidence | HELD / no_checker | FAIL |
| 7 | CANNOT_VERIFY / no_evidence | HELD / error | FAIL |
| 8 | not set in the key | CANNOT_VERIFY / no_evidence | SKIP |

There are no wrong Supported or Contradicted verdicts.

### Live run, Deck A

Run `run-20261122-092339-ef3899` on 2026-11-22 used live Crustdata and a live LLM
(gpt-4o-mini).
- The LLM extracted 7 claims, and code found every quote on its slide.
- The company resolved as confirmed on 2 signals (domain and name).

| Slide | Type | Claimed | Verdict | Evidence (field, value, record date) |
|---|---|---|---|---|
| 2 | team_size | 350 | SUPPORTED / within_tolerance (high) | `headcount.timeseries[2026-11-02].employee_count` = 349, 2026-11-02 |
| 3 | funding | $50M | SUPPORTED / within_tolerance (medium) | `funding.milestones[2021-06-02].amount_usd` = 50,000,000, 2021-06-02 |
| 4 | funding | $78.75M total | SUPPORTED / within_tolerance_undated_rounds (low) | 4 dated `funding.milestones[]` rows; 3 rounds lack a date or amount and are not counted |
| 5 | team_size | 700 | CONTRADICTED / outside_tolerance (medium) | `headcount.timeseries[2026-11-02].employee_count` = 349, 2026-11-02 |
| 6 | customer | Acme Freight Corp | HELD / no_checker | none (no customer checker) |
| 7 | market_size | $9B | HELD / error | none (`sources/web.py` missing) |
| 8 | hiring | 40 open roles | CANNOT_VERIFY / missing_record_date | `hiring.openings_count` = 5, with no record date |

The live verdicts are the same as the offline replay on every slide.

The ledger has 4 calls: 2 Crustdata credits, ₹2.79 and 16.5 s in calls. One of those calls
is a failed first LLM attempt.
- The first attempt failed on an invalid Gemini key. Its ledger row is kept (`ok = 0`).
- The run was resumed with `cli.py resume` and finished from its checkpoint.

The founder email is waiting for approval (`pending`).

### Live run with web search, Deck A

Run `run-20261122-102749-b58f62` on 2026-11-22 had the web source (DECISIONS D16) switched
on. Slides 2 to 5 and 8 gave the same verdicts as the first live run. The web slides:

| Slide | Claim | Verdict | What happened |
|---|---|---|---|
| 6 | Acme Freight Corp is a customer | HELD / timeout | The search ran, but the page fetch took longer than the 20 s `limits.per_call_timeout_s`. A slow source is held, never treated as missing. |
| 7 | India's logistics software market is $9B | CANNOT_VERIFY / source_may_be_incomplete | 3 pages fetched; 2 had no publish date and were skipped. One dated page (Economic Times, 2024-09-18) gave a verified quote, but it is about a different market (home and household, USD 237 billion by 2030). One estimate is not enough to contradict, so the verdict stayed safe. |

The ledger has 8 calls: 8 Crustdata credits, ₹9.72 and 69.7 s in calls (web: 2 searches, 2 fetches, 1 timed out).

After this run, the market-size checker was fixed: code now requires the claim's market
terms in the quote and skips forecasts for a later year (docs/INCIDENTS.md B10). Page fetches got
their own 45 s timeout, `web.fetch_timeout_s` (A5).

**Second live run with the fixes** (`run-20261122-103822-1686da`): slides 2 to 5 and 8 gave the
same verdicts again.

| Slide | Verdict | What happened |
|---|---|---|
| 6, customer | HELD / timeout | This time the web **search** took longer than the 20 s `limits.per_call_timeout_s`. |
| 7, market size | CANNOT_VERIFY / no_evidence | 3 pages fetched, none had a machine-readable publish date, so no quote was used. This matches the answer key. |

The ledger has 6 calls: 7 credits, ₹7.79, 47.6 s. Web search times across the two runs were
6.4 s, 12.0 s, over 20 s and 6.8 s, so the 20 s limit is tight for search (A6).

## Known limits (what does not work yet)

- **Slides 6 and 7 come out Held.**
  - The customer claim type has no checker (no `checkers/customer.py`).
  - `checkers/market_size.py` needs `sources/web.py`, which does not exist yet.
  - Held is the honest result under our rules: a missing source is not evidence of
    absence. The answer key expects Cannot verify.
- **No founder checks yet.** Founder lookups need `get_people` and `search_people` in
  `sources/crust.py` (DECISIONS D12), and they do not exist yet. Deck A has no founder
  slide.
- **The eval claims are hand-written.** `tests/eval/deck_a_claims.json` is our version
  of what extraction should produce; it is not LLM output. The eval has only one deck
  (Deck A).
- **Every value in `config/rules.yaml` is a PLACEHOLDER** until the finance partner
  confirms it. This covers tolerances, limits, rupee rates and materiality weights.
  Changing one is a config edit; see [docs/LIVE_FIX_MAP.md](docs/LIVE_FIX_MAP.md).

## Repo map

| Folder | What it does |
|---|---|
| `core/` | models (the only place for contracts), SQLite store, config, logging, runner |
| `io/` | kickoff-kit request to internal format |
| `extract/` | PDF slide text, LLM claim extraction, quote check |
| `resolve/` | company and founder identity (two-signal rule) |
| `sources/` | Crustdata client |
| `checkers/` | one checker per claim type, returning evidence |
| `verdict/` | the rule engine that picks every label |
| `report/` | result JSON, Markdown report, founder questions |
| `actions/` | email draft, approval, exactly-once send |
| `ui/` | Streamlit app |
| `config/rules.yaml` | every tolerance, limit, rate and output field |

Planning and process docs: [AGENTS.md](AGENTS.md), [PLAN.md](PLAN.md),
[TASKS.md](TASKS.md), [DECISIONS.md](DECISIONS.md), [HANDOFF.md](HANDOFF.md).

## Written before the start

The planning docs (AGENTS.md, PLAN.md, TASKS.md and the agent prompts in
docs/AGENT_PROMPTS.md) were written before 10:15 AM. No code was written before the
start.

## Credits

| Package | Licence | Used for |
|---|---|---|
| [PyYAML](https://pyyaml.org/) | MIT | reading `config/rules.yaml` |
| [pytest](https://pytest.org/) | MIT | tests |
| [pypdf](https://github.com/py-pdf/pypdf) | BSD-3-Clause | PDF slide text |
| [Requests](https://requests.readthedocs.io/) | Apache-2.0 | HTTP calls to Crustdata and the LLM |
| [ReportLab](https://www.reportlab.com/) | BSD | building test PDFs |
| [Streamlit](https://streamlit.io/) | Apache-2.0 | the UI |

Data: [Crustdata](https://crustdata.com/) company API. Claim extraction: Gemini or
OpenAI API (whichever key is set).
