# verdict/DESIGN.md: how `verdict/engine.py` turns a CheckResult into a label

Status: v2 by claude-verdict (T13), implemented in verdict/engine.py, written against the real T01 contracts on
`origin/lane/claude-core` (dataclasses in `core/models.py`, rules in `config/rules.yaml`).
Checker lanes (codex-a: founder_background; ag-b: team_size, funding) fill the `observed` keys below.
If you cannot fill a key, say so in your HANDOFF; do not invent a different key name.

Principle (DECISIONS D1): code decides. A wrong SUPPORTED or CONTRADICTED costs more than a
CANNOT_VERIFY, so every rule leans cautious. Absence of data is never a contradiction.

## 1. Engine interface

```python
def decide(claim: Claim, result: CheckResult, rules: dict) -> Verdict      # signature fixed by D7
def held_verdict(claim_id: str, reason: str, detail: str | None = None) -> Verdict
def check_rules(rules: dict) -> None   # raises ValueError naming every missing rules.yaml key
```

Pure function, no I/O, no LLM, no clock. `explanation` is a plain sentence built from the evidence
(an LLM may rewrite the wording later in report/, never the label, numbers or dates).
`evidence_ids` = ids of every Evidence in the result. `rules` is the dict from `core.config.load_rules`.
Every threshold is read with `core.config.rule()`; there are no code defaults, and a missing key raises
`ValueError` at the first `decide()` call (call `check_rules(rules)` at start-up to fail even earlier).

## 2. Order of checks (first match wins, same for every claim type)

| # | Condition | Label | reason_code | confidence |
|---|---|---|---|---|
| 1 | `result.held_reason` is set (`budget`, `time`, `timeout`, `error`, `no_checker`) | HELD | the held_reason itself | low |
| 2 | no evidence or `observed` empty, unless the checker set `comparable=False` with an explicit `not_comparable_reason` | CANNOT_VERIFY | `no_evidence` | low |
| 3 | `observed.identity` is `unclear` | CANNOT_VERIFY | `identity_unclear` | low |
| 4 | `observed.identity` is `not_found` | CANNOT_VERIFY | `entity_not_found` | low |
| 5 | `result.comparable` is False | NOT_COMPARABLE | `observed.not_comparable_reason` (default `not_comparable`) | medium |
| 5b | `identity` is not `confirmed`, or `identity_signals` < `identity.min_signals` (a missing key counts as not confirmed). T33: for claim.type `market_size` only, `identity == "not_applicable"` passes this row (a market is not an entity, D16) | CANNOT_VERIFY | `identity_unclear` | low |
| 6 | no `observed.record_date` (or not a date) and the D17 undated fallback does not apply (section 2.1) | CANNOT_VERIFY | `missing_record_date`; `missing` says why (fallback off, deck older than the limit, deck after retrieval) | low |
| 7 | no reference date | CANNOT_VERIFY | `no_reference_date` | low |
| 7b | `record_date` is AFTER the reference date (D3: no fact from after the as-of date may support or contradict a claim; one day after is enough) | NOT_COMPARABLE | `record_after_as_of`; `missing` = "A record dated on or before <reference date>." | high |
| 8 | record date more than `tolerances.<claim type>.max_record_age_days` (if that key exists, else the global `tolerances.max_record_age_days`) BEFORE the reference date | NOT_COMPARABLE | `stale_record` | medium |
| 9 | metric rules in section 3 (they also return `claim_value_unusable` when the claim's value is not a usable number) | any | see section 3 | see section 3 |

### 2.1 Undated fallback (D17, T34)

When `observed.record_date` is missing, the engine still decides if ALL hold: `verdict.undated_fallback` is true (a
missing key counts as off); the evidence has a `retrieved_at` (the latest one is used); and the reference date is 0 to
`verdict.undated_max_deck_age_days` days BEFORE that retrieval date. Then rows 7b and 8 are skipped (there is no record
date), `st` gets `undated=True`, `rec=None`, `gap=None`, `fresh=False`, ceiling `low`, and the per-type rule runs as usual.
`make()` then appends `_undated` to the reason code (e.g. `within_tolerance_undated`, `metric_mismatch_undated`), forces
confidence `low`, prefixes the explanation with "No dated record was found; this uses an undated source retrieved on
<YYYY-MM-DD>. " and appends MISSING_TEXT `undated` ("A record with its own date on or before <ref>...") to `missing`.
`no_evidence` never gets the suffix (nothing was used). A dated record always wins: the fallback never runs when
`record_date` is a date. Rules that need the record date handle `rec=None`: founder tenure ends an open role at the
reference date; team_growth returns `period_mismatch_undated` (the window end is unknown).
Web items (market_size, customer; `verdict/web_common.select`): dated items that pass the date filter always win; only
when none pass, and the guard holds, items with `published_date: None` are used, and that verdict is `_undated` too.

Reference date = `observed.reference_date` (the checker sets it to `claim.as_of` when that is an ISO date, else the run's
`deck_date`; `decide()` has no access to the run, D7), and if that is absent, `claim.as_of` when it is an ISO date.
If `observed.reference_date_source` is `pdf_metadata` or `missing` (deck date not given by the user) every confidence is
capped at `medium`. A checker that omits the key is treated as `input`.
Unknown claim type or metric: CANNOT_VERIFY, `unsupported_metric`.
`missing` (what would settle it) is always filled for every non-SUPPORTED label.

Keys every checker sets in `observed` (all types):

| key | type | meaning |
|---|---|---|
| `identity` | `"confirmed"` / `"unclear"` / `"not_found"` | did the resolver pin the right company or person |
| `identity_signals` | int | independent matching signals (two-signal rule; engine compares with `identity.min_signals`) |
| `record_date` | `YYYY-MM-DD` | the date of the data point actually used (not the fetch time) |
| `reference_date` | `YYYY-MM-DD` | the date the claim refers to: `claim.as_of` if ISO, else `ctx.run.input.deck_date` |
| `reference_date_source` | `input` / `pdf_metadata` / `missing` | copy of `ctx.run.input.deck_date_source` |
| `not_comparable_reason` | str, optional | set with `comparable=False`: `metric_mismatch`, `period_mismatch`, `definition_mismatch`, ... |

Checkers set `comparable=False` themselves when the claim is about something the source cannot
measure (for example "engineers only" against total headcount). They do not parse free text for the engine.

## 3. Metric rules

Notation: `tol` = `tolerances.<type>.tolerance_pct / 100`; `diff = abs(observed - claimed) / claimed`
(claimed is the denominator because the claim is what is being tested). Claimed 0: only an exact match is SUPPORTED.

### 3.1 team_size (claim.type `team_size`, metric `headcount`)

Where the number comes from (D13, on top of D3): the checker must NOT use the undated snapshot (`headcount.total`, `employee_count_range`,
`updated_at`: Crustdata gives only a refresh date for them). It reads the dated history `headcount.timeseries[]` and takes the latest point
dated on or before the reference date. Evidence `field_or_quote` is `headcount.timeseries[<date>].employee_count`.

Checker fills (`observed`):
- `headcount`: int, `employee_count` of that dated point.
- `record_date`: the date of that point (never the refresh date, never the fetch time).
- `headcount_range`: `[low, high]`, only if the band itself comes from a dated point; Crustdata's `employee_count_range` is a snapshot band, so do not use it.
- `reference_date`, `reference_date_source` and the identity keys, as in section 2.
- No point dated on or before the reference date: return no evidence (keep `reference_date` in `observed`). The engine answers CANNOT_VERIFY
  `no_evidence` with `missing` = "A headcount record dated on or before <reference date>." A point dated after the reference date is
  `record_after_as_of` (NOT_COMPARABLE) if it is passed on, but D13 says checkers drop such points instead.
- team_growth is not decided by this engine yet; D13 says it uses two dated points on or before the reference date, growth computed by code.

Claim: `value` = number of people (absolute, int-like), `unit` = `people`.

| Case | Label | reason_code | Confidence |
|---|---|---|---|
| exact number: `diff <= tol` | SUPPORTED | `within_tolerance` | high if `diff <= supported_margin * tol` and the record is fresh, else medium |
| exact number: `diff > tol` | CONTRADICTED | `outside_tolerance` | medium at most (headcount is a derived estimate, never high), low if the record is not fresh |
| band: claim inside `[low, high]` widened by `tol` | SUPPORTED | `within_band` | medium, low if not fresh |
| band: claim outside the widened band | CONTRADICTED | `outside_band` | low |

"Fresh" = record within `verdict.fresh_days` of the reference date (new key, see section 6 and D8).

### 3.2 funding (claim.type `funding`)

Claim `metric` decides the rule. `claim.value` must be in absolute major units (5000000, not "5M"; that is the
extraction lane's job, see section 5). `claim.unit` = ISO currency (`USD`, `INR`). The engine never converts
currencies (no FX source we may cite): a unit that differs from `observed.currency` is NOT_COMPARABLE, `currency_mismatch`.

Checker fills (`observed`):
- `currency`: ISO code of the figures below.
- `total_raised`: float, sum of rounds dated on or before the reference date.
- `excluded_later_rounds`: int, rounds dropped because they are after the reference date.
- `undated_rounds`: int, rounds with no date (these are NOT in the total).
- `matched_round`: `{stage, amount, currency, date, investors[]}` or `null`, the one round the checker matched
  to the claim (by stage and date). The checker, not the engine, does the matching.
- `investors_found`: list[str], normalised investor names across rounds up to the reference date.
- `record_date`: date of the newest round used.

| Metric | Case | Label | reason_code | Confidence |
|---|---|---|---|---|
| `total_raised` | `diff <= tol`, `undated_rounds == 0` | SUPPORTED | `within_tolerance` | high if fresh and `diff <= supported_margin * tol`, else medium |
| `total_raised` | `diff <= tol`, `undated_rounds > 0` | SUPPORTED | `within_tolerance_undated_rounds` | low |
| `total_raised` | observed > claimed by more than `tol` (deck understates) | CONTRADICTED | `observed_higher` | medium, low if `undated_rounds > 0` |
| `total_raised` | observed < claimed by more than `tol` | CANNOT_VERIFY | `source_may_be_incomplete` | low. Funding databases miss rounds, so a lower number does not prove inflation. `missing`: press release, filing or investor confirmation of the claimed amount. The explanation still states the gap. |
| `round_amount` | `matched_round` is null | CANNOT_VERIFY | `round_not_found` | low |
| `round_amount` | matched, `diff <= tol` | SUPPORTED | `within_tolerance` | high if fresh and within `supported_margin * tol`, else medium |
| `round_amount` | matched, `diff > tol` | CONTRADICTED | `outside_tolerance` | medium, high only when `diff >= strong_margin * tol` and fresh |
| `investor` | claim.value found in `investors_found` | SUPPORTED | `investor_listed` | medium |
| `investor` | not found | CANNOT_VERIFY | `investor_not_listed` | low (absence is not proof) |

Other funding metrics (stage names, valuation): CANNOT_VERIFY `unsupported_metric` until someone adds a rule here.

### 3.3 founder_background (claim.type `founder_background`)

`claim.subject` = the person. Metrics handled: `past_employer`, `title`, `tenure_years`.
The resolver must pin the person with two signals (`identity_signals >= identity.min_signals`) or the engine stops at row 3.
Checker keeps only professional fields (no emails, phones, raw payloads) and fills:
- `employer_found`: bool, a position at the claimed employer exists (name normalised by the checker).
- `positions`: list of `{employer, title, start_date, end_date}` for the matched employer only (`end_date` null = current).
- `title_observed`: str or null, the title at the matched employer (the one overlapping the claimed period if there are several).
- `record_date`: date of the profile snapshot.

| Metric | Case | Label | reason_code | Confidence |
|---|---|---|---|---|
| `past_employer` | `employer_found` true | SUPPORTED | `employer_listed` | high if fresh, else medium |
| `past_employer` | false | CANNOT_VERIFY | `employer_not_in_profile` | low (profiles omit jobs) |
| `title` | no matched position | CANNOT_VERIFY | `employer_not_in_profile` | low |
| `title` | claimed or observed title has no keyword in `title_levels` | CANNOT_VERIFY | `title_unmapped` | low |
| `title` | observed level >= claimed level | SUPPORTED | `title_level_met` | high if same level and fresh, else medium |
| `title` | observed level < claimed level and claimed level >= `min_title_level` | CONTRADICTED | `title_level_lower` | medium (high if the gap is two levels or more and fresh) |
| `title` | observed level < claimed level and claimed level < `min_title_level` | NOT_COMPARABLE | `informal_title` | low |
| `tenure_years` | no start date | CANNOT_VERIFY | `missing_dates` | low |
| `tenure_years` | `abs(observed_months - claimed_months) <= tenure_tolerance_months` | SUPPORTED | `tenure_within_tolerance` | medium |
| `tenure_years` | gap larger | CONTRADICTED | `tenure_outside_tolerance` | medium |

Level of a title = the highest level whose keyword list (`title_levels.<level>`) has a keyword contained in the
lowercased title. Seniority order = the order of the keys in `title_levels` in rules.yaml (first = most senior: today `c_level`, `vp`, `director`, `manager`, `ic`); `min_title_level` must be one of those keys. Keywords match whole words only ("lead" does not match "leader").
Observed tenure months = months from `start_date` to `end_date` (or `record_date` when current).
Never CONTRADICTED because an employer is missing from a profile.

### 3.4 hiring (claim.type `hiring`; T29)

Observed: `openings_count`, `growth_percent`. Tolerance `tolerances.hiring.tolerance_pct`.
- A count claim whose unit names a subset (anything other than empty, people, roles, openings, jobs, positions, hires;
  e.g. Deck A slide 8 "engineers") -> NOT_COMPARABLE `metric_mismatch`: total openings can never support it.
- Metric containing "growth" needs unit `%` and compares with `growth_percent`; otherwise `metric_mismatch`.
- Within tolerance -> SUPPORTED `within_tolerance`, medium when close and fresh, else low (never high).
- Fewer openings than claimed -> CANNOT_VERIFY `source_may_be_incomplete` (job indexes undercount); more than claimed ->
  CANNOT_VERIFY `observed_more_than_claimed`. **Never CONTRADICTED.**

### 3.5 traction (claim.type `traction`; T29)

Observed: `revenue`, `arr` (USD estimates), `growth_rate`. Tolerance `tolerances.traction.tolerance_pct`.
- Like with like only: revenue/annual_revenue/turnover -> `revenue`, arr -> `arr`. GMV, bookings, run rate, MRR, monthly,
  orders, profit and any other metric -> NOT_COMPARABLE `metric_mismatch`.
- Growth claims -> CANNOT_VERIFY `growth_scale_unclear` (the checker does not say whether growth_rate is a fraction or a
  percent, or its period).
- Unit not `USD` (including none) -> NOT_COMPARABLE `currency_mismatch`.
- diff <= tol -> SUPPORTED (medium when close and fresh, else low); tol < diff < strong_margin x tol -> CANNOT_VERIFY
  `estimate_gap_unclear`; diff >= strong_margin x tol -> CONTRADICTED `outside_tolerance`, medium if fresh else low. Never high.

### 3.6 company_fact (claim.type `company_fact`; T29)

Observed: `year_founded`, `headquarters` (string or dict with city/name).
- Founded year (metric contains "year" or "found"): exact -> SUPPORTED high (capped by the date ceiling); gap up to
  `tolerances.company_fact.year_gap_cannot_verify` -> CANNOT_VERIFY `founding_year_close` (incorporation vs launch);
  larger -> CONTRADICTED `outside_tolerance` medium.
- Headquarters (metric contains "headquarter", "hq" or "location"): first comma part, lower-cased, aliases
  (Bangalore=Bengaluru, Gurgaon=Gurugram, Bombay=Mumbai, New Delhi=Delhi, Madras=Chennai, Calcutta=Kolkata, Poona=Pune);
  equal -> SUPPORTED medium, anything else -> CANNOT_VERIFY `location_unclear`. **Never CONTRADICTED.**
- Other metrics -> `unsupported_metric`. Note: while the company record is a snapshot dated today, most of these stop
  earlier at `record_after_as_of` (section 2).

### 3.7 prior_exit (claim.type `prior_exit`; T29)

Guard, right after the identity check: unless `observed.prior_company_checked is True` -> CANNOT_VERIFY
`prior_company_not_checked`. Today's checker fetches the deck's OWN company (Locus shows acquired_by Ingka), so every
prior_exit claim stops here. Once the flag is set: acquirer (metric with "acquir", "buyer", "exit", "sold") matched with
`resolve.names.company_names_match` -> SUPPORTED `acquirer_matches` medium, different -> CANNOT_VERIFY `acquirer_differs`,
none -> `source_may_be_incomplete`; amount (metric with "amount", "value", "price") in USD within
`tolerances.prior_exit.tolerance_pct` -> SUPPORTED medium, outside -> CANNOT_VERIFY `estimate_gap_unclear`, missing ->
`source_may_be_incomplete`, other currency -> `currency_mismatch`. **Never CONTRADICTED.**

### 3.8 team_growth (claim.type `team_growth`; T29)

Needs `observed.baseline_date` and a yearly metric (yoy, year, annual, 12m); the window record_date - baseline_date must be
365 +- `tolerances.team_growth.window_tolerance_days`. Otherwise NOT_COMPARABLE `period_mismatch` (today's checker: always).
Then unit `%` required (else `metric_mismatch`); within `tolerances.team_growth.tolerance_pct` -> SUPPORTED medium,
outside -> CANNOT_VERIFY `estimate_gap_unclear`. **Never CONTRADICTED.**

### 3.9 competition (claim.type `competition`; T29)

Always CANNOT_VERIFY `competition_not_judged`; the competitors the source names stay in the evidence. Not in
`_TYPES_WITH_RULES` (it has no `tolerance_pct`).

### 3.10 market_size (claim.type `market_size`; T33, D16 web source)

Observed: `estimates: [{value, currency, url, domain, quote, published_date, evidence_id}]`, `identity: "not_applicable"`.
Rows 6-8 use `record_date` (newest estimate); then each estimate is kept only if its own `published_date` is on or before
the reference date and within `tolerances.market_size.max_record_age_days` (D3, D14), and its value is a positive number.
Tolerance = `tolerances.market_size.tolerance_pct`, diff = |estimate - claim| / claim.

| Condition (in order) | Label | reason_code | confidence |
|---|---|---|---|
| claim value not a positive number | CANNOT_VERIFY | `claim_value_unusable` | low |
| no kept estimate | CANNOT_VERIFY | `no_evidence` | low |
| no kept estimate in `claim.unit`'s currency (other currencies are ignored, never converted) | NOT_COMPARABLE | `currency_mismatch` | medium |
| any same-currency estimate within tolerance | SUPPORTED | `within_tolerance` | medium if diff <= supported_margin x tol, else low |
| all same-currency estimates outside tolerance, from >= `min_agreeing_sources` distinct domains, and every pair within tolerance of each other | CONTRADICTED | `sources_agree_otherwise` | medium if fresh, else low |
| anything else (one disagreeing source, same domain twice, sources that disagree with each other) | CANNOT_VERIFY | `source_may_be_incomplete` (market-specific `missing`) | low |

Never high: published estimates differ by method, so one rule cannot be sure.

### 3.11 customer (claim.type `customer`; T33, D16 web source)

Observed: company identity as usual (two-signal rule), `customer_name`, `mentions: [{url, domain, quote,
published_date, independent, evidence_id}]`. Mentions are kept by the same date rule as 3.10
(`tolerances.customer.max_record_age_days`). Route-only: not in `_TYPES_WITH_RULES` (no `tolerance_pct`).

| Condition | Label | reason_code | confidence |
|---|---|---|---|
| no kept mention | CANNOT_VERIFY | `no_evidence` | low |
| a kept mention with `independent is True` (the boolean, not a truthy string) | SUPPORTED | `independent_mention` | medium |
| only self-published mentions | CANNOT_VERIFY | `self_reported_only`; `missing` = "A page from the customer or a news outlet naming the customer." | low |

Never CONTRADICTED: not finding a customer on the web is not evidence that they are not a customer.

## 4. Reason codes the report lane can rely on

HELD: `timeout`, `error`, `budget`, `time`, `no_checker` (core `HeldReason`). CANNOT_VERIFY: `no_evidence`, `identity_unclear`, `entity_not_found`,
`claim_value_unusable`, `missing_record_date`, `no_reference_date`, `unsupported_metric`, `source_may_be_incomplete`,
`round_not_found`, `investor_not_listed`, `employer_not_in_profile`, `title_unmapped`, `missing_dates`,
T29: `observed_more_than_claimed`, `growth_scale_unclear`, `estimate_gap_unclear`, `founding_year_close`, `location_unclear`,
`prior_company_not_checked`, `acquirer_differs`, `competition_not_judged`, T33: `self_reported_only`.
T34 (D17): any rule reason above except `no_evidence` may carry the suffix `_undated` (low confidence) when it was decided from an undated source; the report lane should match on the base code with `reason_code.removesuffix("_undated")`.
NOT_COMPARABLE: `record_after_as_of`, `stale_record`, `currency_mismatch`, `informal_title`, T29: `metric_mismatch`, `period_mismatch`,
plus any checker-given `not_comparable_reason`.
SUPPORTED: `within_tolerance`, `within_tolerance_undated_rounds`, `within_band`, `investor_listed`, `employer_listed`,
`title_level_met`, `tenure_within_tolerance`, T29: `acquirer_matches`, T33: `independent_mention`. CONTRADICTED: `outside_tolerance`, `outside_band`, `observed_higher`,
`title_level_lower`, `tenure_outside_tolerance`, T33: `sources_agree_otherwise` (market_size only).

## 5. Asks for other lanes

- ag-b (extract/claims.py): `claim.value` must be absolute major units with no "M", "k" or "Cr" multiplier;
  `claim.unit` an ISO currency code or `people`; `claim.metric` one of `headcount` (or empty for team_size), `total_raised`, `round_amount`,
  `investor`, `past_employer`, `title`, `tenure_years` for these three types.
- codex-a (resolve): set `identity_signals` as the count of independent signals matched (name, employer overlap, profile URL, domain).
  Row 3 applies to company claims too, so say in your HANDOFF how many signals a company matched by exact domain gets
  (if one signal is enough for a company, the checker must report at least `identity.min_signals`, or the engine will stop at `identity_unclear`).
- Checkers: set `observed.record_date` to the date of the data point, never to the fetch time.
  D3 consequence: a live snapshot (for example a company record refreshed today) is dated today, so against an older deck date it is
  `record_after_as_of`, never SUPPORTED or CONTRADICTED. Where a source has its own dated events (funding rounds with a date, a role with
  a start date), use only those dated on or before the reference date and set `record_date` to the newest of them. Test decks must carry a
  deck date on or after the date of the data they are checked against.

- T29, codex-a (checkers/prior_exit.py): fetch the founder's EARLIER company (from the claim subject or the founder's
  profile), not `ctx.run.input.domain`, and set `observed["prior_company_checked"] = True` only then. Exit records are old,
  so also add `tolerances.prior_exit.max_record_age_days` (e.g. 3650, like funding) to rules.yaml when this is enabled.
- T29, ag-b (checkers/team_growth.py): choose the baseline point from the claim's period (one year before the newest
  point for "YoY"/"in the last year") instead of the first history point, and expose it as `observed["baseline_date"]`
  (do not hide it only in `field_or_quote`).
- T29, checkers/traction.py: say whether `growth_rate` is a fraction or a percent and over which period
  (e.g. `observed["growth_rate_pct_yoy"]`); until then traction growth claims stay `growth_scale_unclear`.
- T29, ag-b (extract): for hiring, put the role family in `unit` ("engineers", "sales") so subset claims are caught.
- T33, extract: for market_size put the ISO currency in `claim.unit` and the value in absolute major units; a missing
  unit makes every estimate `currency_mismatch`. For customer put the customer's name in `claim.value`.
- T34/T35 (D17), checkers: when a value has no date of its own, send `observed.record_date: None` and Evidence
  `record_date=None` (not the fetch date, not `updated_at` of a live snapshot), and keep `retrieved_at` real; web items
  keep `published_date: None`. The hiring checker today sets `record_date` from `updated_at`; Deck A's recorded fixture
  has no `hiring` block, so offline slide 8 stays `no_evidence`.
- T33, web checkers (D16): `independent` must be a real boolean; `domain` must be the registrable domain (sub-pages
  of one site count as one source for CONTRADICTED); every estimate/mention needs its own `published_date`.

## 6. rules.yaml keys the engine reads

T29 (read inside each rule, not in REQUIRED_KEYS): `tolerances.hiring.tolerance_pct`, `tolerances.traction.tolerance_pct`,
`tolerances.prior_exit.tolerance_pct`, `tolerances.team_growth.tolerance_pct`, `tolerances.company_fact.tolerance_pct`
(read by _prepare, unused), NEW `tolerances.company_fact.year_gap_cannot_verify` (PLACEHOLDER 1),
NEW `tolerances.team_growth.window_tolerance_days` (PLACEHOLDER 45).

T34 (D17, read by `_undated_guard`, optional: absent means the fallback is off): `verdict.undated_fallback`
(PLACEHOLDER true), `verdict.undated_max_deck_age_days` (PLACEHOLDER 90).

T33 (already in rules.yaml, read inside each rule): `tolerances.market_size.tolerance_pct`,
`tolerances.market_size.min_agreeing_sources`, `tolerances.market_size.max_record_age_days`,
`tolerances.customer.max_record_age_days`. `tolerances.customer.require_exact_quote` is for the checker, not the engine.

Existing: `tolerances.team_size.tolerance_pct`, `tolerances.funding.tolerance_pct`,
`tolerances.founder_background.min_title_level`, `tolerances.founder_background.tenure_tolerance_months`,
`tolerances.max_record_age_days` (global), optional `tolerances.<claim type>.max_record_age_days` (overrides the global one for that type; D14), `title_levels.*`, `identity.min_signals`.

NEW keys the engine requires (DECISIONS D8; claude-core adds them to rules.yaml and `REQUIRED_KEYS`, the finance partner
sets the values). The engine has NO fallback: until they exist `decide()` raises ValueError naming them.

```yaml
verdict:
  supported_margin: 0.5   # diff <= supported_margin * tolerance counts as a clearly close match (high confidence)
  strong_margin: 2.0      # diff >= strong_margin * tolerance counts as a clearly wrong number (high confidence)
  fresh_days: 90          # a record within this many days of the reference date is "fresh"
```

Open questions for the finance partner:
1. `min_title_level` reading: I use it as "the lowest claimed level at which a lower observed title is CONTRADICTED;
   below it the title is too informal to contradict". Is that the intent?
2. `tolerances.max_record_age_days` sits next to the claim types (not inside one). I read it as global.
3. Is it right that a funding total lower than the deck is CANNOT_VERIFY, not CONTRADICTED? (Cautious choice; the
   alternative catches more inflated claims but risks wrong CONTRADICTED when the database misses a round.)
