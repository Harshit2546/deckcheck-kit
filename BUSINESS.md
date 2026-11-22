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

### Full live run (Deck A, Locus, with web search): the number to quote
- **Run ID:** `run-20261122-104047-1b295e` (6 PASS against the answer key)
- **Calls:** 8 (company data, web search, page fetches)
- **Crustdata credits:** 11 (2 company, 3 web search, 6 page fetch)
- **Time in calls:** 74.8 seconds
- **Total cost:** **₹11.96**

### Other measured runs
- Deck A without web search (`run-20261122-092339-ef3899`): 2 credits, **₹2.79**, 16.5 s.
- Deck A with web search, earlier runs: ₹9.72 and ₹7.79 (some web calls timed out and were held).
- Deck F, founders only (`run-20261122-111231-e7bd42`): 3 credits, **₹3.40**, 10.8 s.

**All rupee figures use placeholder rates** (`costs.*` in `config/rules.yaml`: ₹1.00 per credit and
guessed LLM prices). They are not published Crustdata prices, and the margins below depend on them.
Decks with more web claims cost more: each web claim is 1 search plus up to 3 page fetches, so
about 4 credits. Turnaround was 15 to 75 seconds.

---

## 4. Pricing, Margins & Commercial Model

We offer usage-based tiers aligned with Indian VC deal-flow volume:

| Tier | Monthly Decks | Monthly Fee (INR) | Effective Price / Deck | Cost to Serve (Est. INR) | Gross Margin |
|---|---|---|---|---|---|
| **Angel / Syndicate** | 20 | ₹9,999 | ₹500 | ₹240 (20 x ₹12) | **97.6%** |
| **Boutique VC (Seed/Pre-Series A)** | 75 | ₹29,999 | ₹400 | ₹900 (75 x ₹12) | **97.0%** |
| **Growth Fund / CVC Desk** | 250 | ₹74,999 | ₹300 | ₹3,000 (250 x ₹12) | **96.0%** |
| **Ad-Hoc / Pay-per-deck** | 1 | ₹799 | ₹799 | ₹12 | **98.5%** |

### Value Comparison:
- **Analyst Manual Diligence:** ₹3,000 – ₹8,000 | 3–8 hours turnaround
- **DeckCheck Automated Check:** ₹400 – ₹799 (price), about ₹12 of data cost | under 2 minutes turnaround
- **Immediate ROI:** **>85% direct cost saving** per analyzed deck while liberating analyst capacity for deeper thesis building.

---

## 5. Scaling to 100x Volume (10,000 Decks / Month)

Scaling from 100 to 10,000 decks/month requires the following production architecture enhancements:

1. **Asynchronous Distributed Queue:**
   - Migrate local synchronous runner to Redis/Celery or AWS SQS / GCP PubSub background workers.
2. **Shared Multilevel Caching:**
   - Replace in-process run cache with a centralized Redis/Dragonfly instance. Multiple decks referencing common competitors or industry market-size reports will hit cache hits (0 additional credits).
3. **Upstream Rate Limit Management:**
   - Crustdata's pacing limits are read live from its `GET /account/endpoints` call, not fixed in our code. Web search and page fetch were the slowest calls in our runs (up to 28 s for one fetch).
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
   - *Mitigation:* Abstracted pricing engine in `config/rules.yaml` (`costs.*`) allows instant repricing without code rewrites; extreme gross margins (about 95% or more at placeholder rates) absorb upstream fluctuations.
3. **Adversarial / Non-Standard Decks:**
   - Complex image-only slides, non-standard layouts, or ambiguous metrics.
   - *Mitigation:* Verbatim slide quote verification drops ungrounded quotes; unresolvable claims degrade gracefully to `CANNOT_VERIFY`.
