# BUSINESS.md — DeckCheck Unit Economics, Commercial Model & Scale Plan

DeckCheck is an automated diligence tool tailored for the ContextCon 05 Investing Track.
It converts unstructured pitch deck factual claims into deterministic, verified verdicts
with dated sources.

---

## 1. Target Buyer

1. **Small to Mid-Sized Indian VC Funds (Seed to Series B):**
   - Typically run lean teams (2–4 investment analysts/associates) reviewing 40–80 decks a week.
   - Diligence bandwidth before the first partner meeting or term sheet is scarce.
2. **Angel Networks and Syndicates (e.g., Mumbai Angels, Indian Angel Network):**
   - Need rapid, standardized diligence checks to filter unvetted inbound pitch submissions before sharing with lead angels.
3. **Corporate Venture Capital (CVC) & Strategic Diligence Desks:**
   - E.g., a 3PL logistics corporation screening supply-chain startups for strategic partnership, investment, or acquisition.

---

## 2. What DeckCheck Replaces

Before an investor schedules a second founder meeting or issues an LOI, an analyst manually checks:
- Team size and hiring claims (LinkedIn / MCA filings / company announcements)
- Prior funding rounds, lead investors, and milestones (Tracxn / Crunchbase / press archives)
- Customer claims and quoted market-size reports

**The Status Quo Cost:**
- **Analyst Time:** 3 to 8 hours per deck.
- **Cost in Rupees:** At an average Indian junior VC analyst salary of ₹12,00,000–₹18,00,000/year (approx. ₹700–₹1,000/effective hour), an analyst spends **₹3,000 to ₹8,000 per deck** on routine factual cross-referencing.
- **Turnaround:** 1 to 3 business days, slowing deal flow and partner response times.

---

## 3. Our Cost per Deck (Measured from the Immutable Ledger)

We do not use synthetic estimates. Our cost per deck is measured directly from the SQLite run ledger:

### Baseline Live Run (Deck A — Locus, without Web Search):
- **Run ID:** `run-20261122-092339-ef3899`
- **Total Duration:** 16.5 seconds
- **Calls:** 4 external calls (Crustdata company lookup + LLM extraction via gpt-4o-mini; includes 1 failed initial call preserved in ledger)
- **Crustdata Credits:** 2.0 credits
- **Token Usage:** 1,068 tokens
- **Total Run Cost:** **₹2.79** (at ₹1.0/credit and ₹0.25/₹1.25 per 1k input/output tokens)

### Projected Run Cost (With Live Web Search & Fetch Enabled):
- **Web Search & Fetch:**
  - 1 search call per web-dependent claim (1 credit)
  - Up to 3 page fetches per claim (3 credits)
  - Estimated additional credit consumption: ~8 credits per deck
- **Total Projected Cost per Deck:** **₹10.50 to ₹14.00** (~8–10 credits + ~3,000 LLM tokens for quote extraction)
- **Turnaround:** 25 to 45 seconds per deck.

---

## 4. Pricing, Margins & Commercial Model

We offer usage-based tiers aligned with Indian VC deal-flow volume:

| Tier | Monthly Decks | Monthly Fee (INR) | Effective Price / Deck | Cost to Serve (Est. INR) | Gross Margin |
|---|---|---|---|---|---|
| **Angel / Syndicate** | 20 | ₹9,999 | ₹500 | ₹280 (20 x ₹14) | **97.2%** |
| **Boutique VC (Seed/Pre-Series A)** | 75 | ₹29,999 | ₹400 | ₹1,050 (75 x ₹14) | **96.5%** |
| **Growth Fund / CVC Desk** | 250 | ₹74,999 | ₹300 | ₹3,500 (250 x ₹14) | **95.3%** |
| **Ad-Hoc / Pay-per-deck** | 1 | ₹799 | ₹799 | ₹14 | **98.2%** |

### Value Comparison:
- **Analyst Manual Diligence:** ₹3,000 – ₹8,000 | 3–8 hours turnaround
- **DeckCheck Automated Check:** ₹400 – ₹799 | <45 seconds turnaround
- **Immediate ROI:** **>85% direct cost saving** per analyzed deck while liberating analyst capacity for deeper thesis building.

---

## 5. Scaling to 100x Volume (10,000 Decks / Month)

Scaling from 100 to 10,000 decks/month requires the following production architecture enhancements:

1. **Asynchronous Distributed Queue:**
   - Migrate local synchronous runner to Redis/Celery or AWS SQS / GCP PubSub background workers.
2. **Shared Multilevel Caching:**
   - Replace in-process run cache with a centralized Redis/Dragonfly instance. Multiple decks referencing common competitors or industry market-size reports will hit cache hits (0 additional credits).
3. **Upstream Rate Limit Management:**
   - Crustdata endpoints currently enforce 10 requests per minute (RPM) for web search/fetch and 5 RPM for company enrichments.
   - At 100x, implement token-bucket egress rate limiters and enterprise concurrent-seat Crustdata contracts.
4. **Multi-Tenant Metering & Client Ledgers:**
   - Extend `ledger` schema with `organization_id` and pre-paid rupee credit quotas to prevent run overages.

---

## 6. Business & Operating Risks

1. **Data Coverage Gaps (Early-Stage Startups):**
   - Pre-seed or stealth startups have minimal footprint on Crustdata/LinkedIn.
   - *Mitigation:* DeckCheck explicitly emits `CANNOT_VERIFY` or `HELD`, preventing false rejections, and auto-generates founder evidence requests.
2. **Provider Pricing Volatility:**
   - Shifts in third-party API or LLM token rates.
   - *Mitigation:* Abstracted pricing engine in `config/rules.yaml` (`costs.*`) allows instant repricing without code rewrites; extreme gross margins (>95%) absorb upstream fluctuations.
3. **Adversarial / Non-Standard Decks:**
   - Complex image-only slides, non-standard layouts, or ambiguous metrics.
   - *Mitigation:* Verbatim slide quote verification drops ungrounded quotes; unresolvable claims degrade gracefully to `CANNOT_VERIFY`.
