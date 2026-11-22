# PLAN.md — DeckCheck build plan (ContextCon 05, Investing track)

Assumes code start 10:15 and freeze 17:15 (7 hours). If the handbook says 10:45,
shift every time below by 30 minutes. The organizers change one requirement at
hour 3 (about 13:15).

## 1. The job

**Service replaced:** a VC analyst or diligence firm checking a pitch deck before
the second meeting (3–8 analyst hours per deck).
**Client framing:** the organizers' client is a mid-size Indian 3PL. Frame DeckCheck
as the client's strategic-investment / corporate-venture desk screening
logistics-tech startups it may invest in, acquire or partner with. Use whatever
request the kickoff kit gives for the Investing track; the adapter (io/adapter.py)
maps it to our internal format.
**Input:** deck PDF (text-based) + company domain + deck date (fallback: PDF
metadata, flagged) + optional founder profile URLs.
**Finished result:** claim table with verdicts and dated sources, red-flag summary,
founder questions, evidence-request list, run ledger with rupee cost, and a founder
email waiting for approval.
**Pass mark (for README):** on our answer key, zero wrong Supported/Contradicted
verdicts; every non-decided claim is Cannot verify or Held with a reason; email
sent exactly once after approval, including after a kill.

## 2. Pipeline (every step checkpointed in SQLite)

```
 io/adapter  ->  1 extract  ->  2 resolve  ->  3 check (per claim)  ->  4 verdict  ->  5 report  ->  6 action
 kit format      pdf text +     company &      typed checkers call      code rules      red flags,     email draft
 to internal     LLM claims +   founders,      Crustdata / web, each    from            questions,     -> approval
                 quote check    confidence     returns Evidence         rules.yaml      ledger         -> send once
```

Run states: `created -> extracted -> resolved -> checking -> decided -> reported -> done`.
Each claim also has its own state: `pending -> checked -> decided`. On restart,
`cli.py resume <run_id>` skips everything already marked done.

## 3. Contracts (only change via DECISIONS.md)

**Claim** — id, run_id, slide, quote (exact text from slide), type
(founder_background | prior_exit | team_size | team_growth | funding | company_fact |
customer | hiring | traction | market_size | competition), subject, metric, value,
unit, as_of, state.

**Evidence** — id, claim_id, source_type (crustdata_company | crustdata_person |
crustdata_job | web_page), locator (URL or API endpoint), field_or_quote (exact field
name or exact quote), value, record_date, retrieved_at, call_id (ledger row).

**Verdict** — claim_id, label (SUPPORTED | CONTRADICTED | NOT_COMPARABLE |
CANNOT_VERIFY | HELD), reason_code, explanation (LLM-written from evidence only),
evidence_ids, confidence (high | medium | low), missing (what would settle it).

**LedgerEntry** — id, run_id, provider (crustdata | llm | web), endpoint_or_model,
credits, tokens_in, tokens_out, cost_inr, duration_ms, ok, error, ts.

**Action** — id, run_id, type (founder_email), idempotency_key = sha256(run_id +
type + recipient), recipient (test inbox only), subject, body, status (pending |
approved | rejected | sending | sent), decided_by, decided_at, sent_at.
`UNIQUE(idempotency_key)` in the DB.

**Checker interface** — `check(claim, ctx) -> CheckResult(evidence: list[Evidence],
observed: dict, comparable: bool, held_reason: str | None)`. Checkers fetch and
normalise; they never choose the verdict label.

**Exactly-once send** — sender selects actions with status `approved`, sets
`sending` in the same transaction, inserts into `inbox` with the idempotency key
(UNIQUE), then sets `sent`. On restart: any `sending` row whose key already exists
in `inbox` becomes `sent`; otherwise it is retried. A second send is impossible
because of the UNIQUE key.

**Limits** — `config/rules.yaml`: `max_cost_inr`, `max_seconds`, `max_credits`,
`per_call_timeout_s`. The runner checks the ledger total before each call.

## 4. Repo layout and lanes

| Folder | What | Lane |
|---|---|---|
| core/ (models, store, runner, log, ledger) | contracts, SQLite, state machine, resume, limits | claude-core |
| config/rules.yaml | tolerances, title levels, materiality, limits, output fields | human (finance partner) |
| io/adapter.py | kickoff-kit format to and from internal models | claude-core |
| sources/crust.py, sources/web.py | Crustdata client: rate limit, backoff, timeout to HELD, ledger, short TTL entity cache with retrieved_at; web search/fetch + quote verification | codex-a |
| extract/ (pdf.py, claims.py) | PDF to slide text; LLM structured claims; code confirms each quote is on its slide | ag-b |
| resolve/entities.py | company by domain; founders via profile URL or name+company; two-signal rule; confidence | codex-a |
| checkers/*.py | one file per claim type | codex-a (founder, exit, company, customer), ag-b (team_size, team_growth, funding, hiring, traction, market, competition) |
| verdict/engine.py | labels from CheckResult + rules.yaml | claude-verdict |
| report/ | red flags by materiality, claim table, questions, evidence requests, JSON + Markdown in kit format | claude-verdict |
| actions/ | email draft, approval, exactly-once send to test inbox | claude-core |
| ui/app.py | Streamlit: upload, live claim list, click verdict to see source, approvals page, inbox, ledger | ag |
| tests/ | fixtures, checker tests, eval runner against answer key | ag (runner), each lane (own tests) |
| docs/ | ARCHITECTURE.md + diagram, LIVE_FIX_MAP.md, ETHICS.md, BUSINESS.md | ag + humans |
| README.md | job, who pays, input, result, pass mark, data sources, how to run, credits | human, drafted by ag |

## 5. Accounts and how they rotate

- Lanes belong to modules, not to accounts. When an account hits its limit, it writes
  the HANDOFF entry; the next account of the SAME tool continues the SAME lane.
- Team budget: 2 Claude Pro, 1 ChatGPT Plus (Codex), 3 Gemini Pro (Antigravity).
  Every lane runs in its own git worktree.
- **Claude Pro A (merger's machine): lane claude-core.** Skeleton, contracts,
  runner/resume/limits, adapter, actions + exactly-once send, kill drills.
- **Claude Pro B (finance partner's machine): lane claude-verdict.** Verdict engine,
  report, hour-3 change, merge reviews (it did not write core/, so it reviews fresh).
  Before T01 lands it drafts verdict rules for founder/team_size/funding from this plan.
- The two Claude lanes back each other up: if one account hits its limit, the other
  continues that lane from its HANDOFF entry. Neither does UI or boilerplate.
- **Codex (ChatGPT Plus, finance partner's machine): lane codex-a.** Crustdata client,
  resolve, founder/exit/company/customer checkers. No second Codex account: if it runs
  out, the Gemini spare takes over codex-a.
- **Gemini 1 (merger's machine): lane ag.** UI, eval runner, diagram, README drafts.
- **Gemini 2 (finance partner's machine): lane ag-b.** Extraction and the remaining
  checkers.
- **Gemini 3 (finance partner's machine): spare.** Continues ag-b or codex-a when that
  account hits its limit.
- **Humans:** the merger merges to main, reads the kickoff kit, runs the end-to-end check
  after each merge, and owns the live fix. The finance partner owns rules.yaml, test
  decks, answer key (do T05 first, before agents need attention), founder question
  templates, ethics and business write-ups, and the demo script.
- Only the two registered team members type prompts and run the service.

## 6. Timeline

| Time | Claude-core | Claude-verdict | Codex-a | Ag-b | Ag | Humans |
|---|---|---|---|---|---|---|
| 11:00–11:30 | T01 skeleton: models, store, rules.yaml schema, runner stub, cli, adapter stub. Push. | draft verdict rules for founder, team_size, funding from PLAN (no code until T01) | probe Crustdata (MCP or curl) on Deck A company; note fields | PDF text per slide | Streamlit shell reading the DB | Finance: Deck A + answer key, rules values. Merger: read kickoff kit, fill adapter mapping in DECISIONS |
| 11:30–12:45 | runner + resume + limits | verdict engine for 3 types | crust.py + ledger + backoff + HELD; resolve | claim extraction + quote check; team_size, funding checkers | claim list, verdict detail with source link | merge at 12:15 and 12:45 (claude-verdict reviews) |
| **12:45** | **Milestone 1: Deck A runs end to end with founder, team_size, funding.** | | | | | check verdicts vs answer key |
| 12:45–13:15 | actions: draft + approval | report + founder questions | founder, company, exit checkers | team_growth, hiring checkers | approvals page + inbox | Finance: Decks B, C |
| **13:15** | **Hour-3 requirement change: claude-verdict reads it, writes DECISIONS entry, assigns it.** | | | | | |
| 13:15–15:00 | exactly-once send; kill test | requirement change | customer checker (web quote verify); namesake two-signal | traction, market, competition | eval runner: accuracy vs answer key; ledger view | kill-and-restart drill every merge |
| **15:00** | **Milestone 2: all 3 decks run; kill at random step, resume, email sent once.** | | | | | |
| 15:00–16:15 | fix runner/action failures | fix verdict failures from evals | robustness: 429s, timeouts | edge cases | ARCHITECTURE diagram, README draft | ETHICS.md, BUSINESS.md with measured cost/deck |
| 16:15 | **Feature freeze. Bug fixes only.** | | | | | |
| 16:15–17:00 | review LIVE_FIX_MAP | final merge review | — | — | final README | rehearse: 3-min demo with kill, live fix drills, design question |
| 17:00–17:15 | final commit and push | | | | | check deliverables list |

**Cut order if late:** competition, then market size, then hiring. Never cut founder,
team size, funding, customers, approvals, resume.

## 7. What screening and finals will test, and our answer

| They test | Our answer |
|---|---|
| Hidden test cases with lookalike names and unanswerable questions | two-signal identity rule; CANNOT_VERIFY names what is missing; wrong answers cost more than cannot verify, so tolerances lean cautious |
| Unseen request | adapter + no stored results; everything fetched live |
| Stop and restart; each action once | SQLite checkpoints per claim; UNIQUE idempotency key on send |
| Requirement change at hour 3 | rules.yaml and output fields are config |
| Logs, cost records, repo history | core/log.py per step; ledger table + CSV export; small commits |
| Ethics (25) | ETHICS.md: only professional fields kept for founders; contact details (emails, phones) dropped at ingest; raw person payloads not stored; namesake rule; every verdict explained; human approval for email; output is advice, not an automatic rejection |
| Finance (25) | BUSINESS.md: buyer = small Indian VC funds, angel networks, corporate venture desks; price in rupees per deck vs an analyst half-day; cost per deck measured from the ledger |
| Live fix (5 min) | LIVE_FIX_MAP.md; practise: change a tolerance, add a claim type, add an output field |
| Design question | 100x volume: queue + worker pool, shared entity cache with TTL, rate-limit budget, per-tenant ledger. Second client: tenant id on every table, rules.yaml per client |

## 8. Things in the earlier draft we changed

- "Cache the demo run" is removed. Showing a cached run as live breaks rule 5.6.
  Only short-TTL entity caching inside the client, with retrieved_at shown.
- Synthetic test decks are fine as test inputs; label them as synthetic in README.
- Added time limit next to cost limit, ethics and README pass-mark sections, and the
  kickoff-kit adapter.
