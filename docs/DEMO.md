# DEMO.md — 2-minute video script & live-fix drills

This document prepares the team for recording the hackathon demo video (due 17:30 IST)
and rehearsing live judge interactions.

---

## 1. Quick reference & demo setup

### Pre-demo checks (run in terminal):
1. Terminal 1 (Streamlit UI):
   ```bash
   streamlit run ui/app.py
   ```
2. Terminal 2 (CLI / live drills):
   ```bash
   # Ensure .env is loaded (if running live)
   set -a; . ./.env; set +a
   # Test suite verification
   python -m pytest -q
   ```
3. Request file ready:
   `tests/decks/deck_a_request.json` (Locus, domain `locus.sh`, deck date `2026-11-15`).

---

## 2. 2-Minute video script (120 seconds timed)

| Time | Screen / Action | Voiceover / Talking points | Key details |
|---|---|---|---|
| **0:00 - 0:20**<br>(20s) | **Slide / Intro + UI Launch**<br>Open UI (`http://localhost:8501`), click "Run" page. | "Pitch decks are full of numbers, funding rounds, and growth claims that take analysts 3 to 8 hours to manually verify. This is **DeckCheck**. It checks every factual claim in a startup pitch deck against live data, returning deterministic verdicts with dated sources and drafting an actionable founder follow-up." | ContextCon 05 Investing Track.<br>Replaces pre-meeting manual diligence. |
| **0:20 - 0:45**<br>(25s) | **CLI Run + Kill/Resume**<br>Run CLI command in terminal:<br>`python cli.py run --request tests/decks/deck_a_request.json --out out/result.json`<br>Hit `Ctrl+C` after step `extracted`. Then run:<br>`python cli.py resume <run_id> --out out/result.json` | "Watch our crash resilience: we trigger a live run on an 8-slide synthetic deck for Locus. Mid-run, we simulate an infrastructure crash with `Ctrl+C`. We resume with `cli.py resume`. Every step and claim is checkpointed in SQLite—it doesn't duplicate previous calls, respects limits, and finishes seamlessly." | Point out checkpoints.<br>No duplicate ledger charges. |
| **0:45 - 1:15**<br>(30s) | **Claims Table in UI**<br>Switch to UI -> "Claims" tab.<br>Expand Slide 2 (Headcount) & Slide 5 (Headcount 700). | "Here are the verdicts: code, not LLM memory, decides every result. Slide 2 claims 350 employees; Crustdata shows 349 on 2026-11-02: **SUPPORTED**. Slide 5 claims 700: **CONTRADICTED**. Funding of $50M on Slide 3 is verified against dated milestones. Every fact cites exact source URLs, fields, and record dates." | LLM only extracts quotes; code rules decide verdicts.<br>Strict date rule (D3). |
| **1:15 - 1:40**<br>(25s) | **Approvals & Local Inbox**<br>Navigate to "Approvals", enter human name, click "Approve and send". Then view "Inbox". | "Human-in-the-loop ethics: DeckCheck generates tailored founder questions for contradicted claims, but emails remain in `pending` status. Nothing is sent without human approval. We approve it now; our transactional sender guarantees exactly-once dispatch into our local audit inbox with zero real-world leak risk." | Idempotency key guarantee.<br>No unsolicited emails. |
| **1:40 - 2:00**<br>(20s) | **Ledger View & Close**<br>Navigate to "Ledger" page. Show total cost and runtime. | "Every API call writes an immutable ledger entry. This entire run used 2 Crustdata credits and cost just **₹2.79** and 16 seconds—versus thousands of rupees in analyst time. DeckCheck brings instant, factual, auditable diligence to investors." | Highlight ₹2.79 cost vs ₹3k+ analyst cost.<br>End on crisp value proposition. |

---

## 3. Crash & resume walkthrough (rehearsal steps)

### Step 1: Start run
```bash
python cli.py run --request tests/decks/deck_a_request.json --out out/result.json
```
Watch the console output for `step=runner.start`.

### Step 2: Interrupt
Immediately press `Ctrl+C` while `step=check.team_size` or during resolution.
Notice the run output indicates the run ID (e.g. `run-20261122-XXXXXX-XXXXXX`).

### Step 3: Inspect database checkpoint
Notice the run state in SQLite is `checking` or `extracted`, not lost.

### Step 4: Resume
```bash
python cli.py resume <run_id> --out out/result.json
```
The runner picks up from the last checkpointed claim. Completed claims are skipped, avoiding duplicate charges and duplicate external API calls.

---

## 4. Three live-fix drills (5-minute judge questions)

If judges ask "What if our firm has different diligence requirements or limits?", perform these drills in under 60 seconds without writing pipeline code:

### Drill 1: Change a verdict tolerance (e.g., headcount margin)
- **Judge prompt:** *"Our fund is stricter on headcount claims: we only tolerate a 5% difference, not 20%."*
- **Action:**
  1. Open `config/rules.yaml`.
  2. Locate `tolerances.team_size.tolerance_pct`: change `20` to `5`.
  3. Re-run offline eval:
     ```bash
     python tests/eval/run_eval.py
     ```
  4. Explain: Headcount claims deviating by >5% now immediately flag as `CONTRADICTED` or outside tolerance.

### Drill 2: Add an output column to the diligence report
- **Judge prompt:** *"Can we see the reason code or missing evidence requirement directly in the summary table?"*
- **Action:**
  1. Open `config/rules.yaml`.
  2. Under `output.fields`, add `- missing` or rearrange fields.
  3. Re-run CLI export:
     ```bash
     python cli.py export <run_id> --out out/result.json
     ```
  4. Inspect `out/result.md` or UI claims view: the new column renders automatically without code changes.

### Drill 3: Adjust budget / time limits to trigger safe HELD behavior
- **Judge prompt:** *"What happens if an API provider bills unexpectedly or a call stalls?"*
- **Action:**
  1. Open `config/rules.yaml`.
  2. Change `limits.max_cost_inr` to `1` (or `limits.max_credits: 1`).
  3. Run the CLI:
     ```bash
     python cli.py run --request tests/decks/deck_a_request.json --out out/result.json
     ```
  4. Point out result: Remaining claims transition to `HELD` with reason `budget`, never crashing and never fabricating a verdict.
