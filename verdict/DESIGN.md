# verdict/DESIGN.md: how `verdict/engine.py` turns a CheckResult into a label

Status: DRAFT v1 by claude-verdict (T13), written against the real T01 contracts on
`origin/lane/claude-core` (dataclasses in `core/models.py`, rules in `config/rules.yaml`).
Checker lanes (codex-a: founder_background; ag-b: team_size, funding) fill the `observed` keys below.
If you cannot fill a key, say so in your HANDOFF; do not invent a different key name.

Principle (DECISIONS D1): code decides. A wrong SUPPORTED or CONTRADICTED costs more than a
CANNOT_VERIFY, so every rule leans cautious. Absence of data is never a contradiction.

## 1. Engine interface

```python
def decide(claim: Claim, result: CheckResult, rules: dict, deck_date: str | None,
           deck_date_source: str = "input") -> Verdict
def held_verdict(claim_id: str, reason: str) -> Verdict   # for the runner: limit hit before a call
```

Pure function, no I/O, no LLM, no clock. `explanation` is a plain sentence built from the evidence
(an LLM may rewrite the wording later in report/, never the label, numbers or dates).
`evidence_ids` = ids of every Evidence in the result. `rules` is the dict from `core.config.load_rules`.

## 2. Order of checks (first match wins, same for every claim type)

| # | Condition | Label | reason_code | confidence |
|---|---|---|---|---|
| 1 | `result.held_reason` is set (timeout, error, budget, time, credits) | HELD | the held_reason itself | low |
| 2 | no evidence, or `observed` empty | CANNOT_VERIFY | `no_evidence` | low |
| 3 | `observed.identity` is `unclear`, or `identity_signals` < `identity.min_signals` | CANNOT_VERIFY | `identity_unclear` | low |
| 4 | `observed.identity` is `not_found` | CANNOT_VERIFY | `entity_not_found` | low |
| 5 | `result.comparable` is False | NOT_COMPARABLE | `observed.not_comparable_reason` (default `not_comparable`) | medium |
| 6 | claim value missing or not the type the metric needs | CANNOT_VERIFY | `claim_value_unusable` | low |
| 7 | no `observed.record_date` | CANNOT_VERIFY | `missing_record_date` | low |
| 8 | no reference date (neither `claim.as_of` as ISO date nor `deck_date`) | CANNOT_VERIFY | `no_reference_date` | low |
| 9 | `abs(record_date - reference_date)` > `tolerances.max_record_age_days` | NOT_COMPARABLE | `stale_record` | medium |
| 10 | metric rules in section 3 | SUPPORTED / CONTRADICTED / CANNOT_VERIFY / NOT_COMPARABLE | see below | see below |

Reference date = `claim.as_of` when it is an ISO date, else `deck_date`.
If `deck_date_source` is not `input` (PDF metadata or missing) every confidence is capped at `medium`.
Unknown claim type or metric: CANNOT_VERIFY, `unsupported_metric`.
`missing` (what would settle it) is always filled for every non-SUPPORTED label.

Keys every checker sets in `observed` (all types):

| key | type | meaning |
|---|---|---|
| `identity` | `"confirmed"` / `"unclear"` / `"not_found"` | did the resolver pin the right company or person |
| `identity_signals` | int | independent matching signals (two-signal rule; engine compares with `identity.min_signals`) |
| `record_date` | `YYYY-MM-DD` | the date of the data point actually used (not the fetch time) |
| `not_comparable_reason` | str, optional | set with `comparable=False`: `metric_mismatch`, `period_mismatch`, `definition_mismatch`, ... |

Checkers set `comparable=False` themselves when the claim is about something the source cannot
measure (for example "engineers only" against total headcount). They do not parse free text for the engine.

## 3. Metric rules

Notation: `tol` = `tolerances.<type>.tolerance_pct / 100`; `diff = abs(observed - claimed) / claimed`
(claimed is the denominator because the claim is what is being tested). Claimed 0: only an exact match is SUPPORTED.

### 3.1 team_size (claim.type `team_size`, metric `headcount`)

Checker fills (`observed`):
- `headcount`: int, total company headcount at `record_date` (from `crustdata_company`).
- `headcount_range`: `[low, high]` optional, when the source gives a band instead of a number (then `headcount` may be absent).
- plus the common keys above.

Claim: `value` = number of people (absolute, int-like), `unit` = `people`.

| Case | Label | reason_code | Confidence |
|---|---|---|---|
| exact number: `diff <= tol` | SUPPORTED | `within_tolerance` | high if `diff <= supported_margin * tol` and the record is fresh, else medium |
| exact number: `diff > tol` | CONTRADICTED | `outside_tolerance` | medium at most (headcount is a derived estimate, never high), low if the record is not fresh |
| band: claim inside `[low, high]` widened by `tol` | SUPPORTED | `within_band` | medium |
| band: claim outside the widened band | CONTRADICTED | `outside_band` | low |

"Fresh" = record within `verdict.fresh_days` of the reference date (new key, see section 6).

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
lowercased title. Level order, high to low: `c_level`, `vp`, `director`, `manager`, `ic`.
Observed tenure months = months from `start_date` to `end_date` (or `record_date` when current).
Never CONTRADICTED because an employer is missing from a profile.

## 4. Reason codes the report lane can rely on

HELD: `timeout`, `error`, `budget`, `time`, `credits`. CANNOT_VERIFY: `no_evidence`, `identity_unclear`, `entity_not_found`,
`claim_value_unusable`, `missing_record_date`, `no_reference_date`, `unsupported_metric`, `source_may_be_incomplete`,
`round_not_found`, `investor_not_listed`, `employer_not_in_profile`, `title_unmapped`, `missing_dates`.
NOT_COMPARABLE: `stale_record`, `currency_mismatch`, `informal_title`, plus any checker-given `not_comparable_reason`.
SUPPORTED: `within_tolerance`, `within_tolerance_undated_rounds`, `within_band`, `investor_listed`, `employer_listed`,
`title_level_met`, `tenure_within_tolerance`. CONTRADICTED: `outside_tolerance`, `outside_band`, `observed_higher`,
`title_level_lower`, `tenure_outside_tolerance`.

## 5. Asks for other lanes

- ag-b (extract/claims.py): `claim.value` must be absolute major units with no "M", "k" or "Cr" multiplier;
  `claim.unit` an ISO currency code or `people`; `claim.metric` one of `headcount`, `total_raised`, `round_amount`,
  `investor`, `past_employer`, `title`, `tenure_years` for these three types.
- codex-a (resolve): set `identity_signals` as the count of independent signals matched (name, employer overlap, profile URL, domain).
  Row 3 applies to company claims too, so say in your HANDOFF how many signals a company matched by exact domain gets
  (if one signal is enough for a company, the checker must report at least `identity.min_signals`, or the engine will stop at `identity_unclear`).
- Checkers: set `observed.record_date` to the date of the data point, never to the fetch time.

## 6. rules.yaml keys the engine reads

Existing: `tolerances.team_size.tolerance_pct`, `tolerances.funding.tolerance_pct`,
`tolerances.founder_background.min_title_level`, `tolerances.founder_background.tenure_tolerance_months`,
`tolerances.max_record_age_days`, `title_levels.*`, `identity.min_signals`.

NEW keys requested (claude-core owns the schema, finance partner owns the values). Until they exist the engine
falls back to these defaults and logs that it did, so nothing breaks:

```yaml
verdict:
  supported_margin: 0.5   # diff <= 0.5 * tolerance counts as a clearly close match
  strong_margin: 2.0      # diff >= 2 * tolerance counts as a clearly wrong number
  fresh_days: 90          # a record this close to the reference date is "fresh"
```

Open questions for the finance partner:
1. `min_title_level` reading: I use it as "the lowest claimed level at which a lower observed title is CONTRADICTED;
   below it the title is too informal to contradict". Is that the intent?
2. `tolerances.max_record_age_days` sits next to the claim types (not inside one). I read it as global.
3. Is it right that a funding total lower than the deck is CANNOT_VERIFY, not CONTRADICTED? (Cautious choice; the
   alternative catches more inflated claims but risks wrong CONTRADICTED when the database misses a round.)
