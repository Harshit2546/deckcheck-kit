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
| 5b | `identity` is not `confirmed`, or `identity_signals` < `identity.min_signals` (a missing key counts as not confirmed) | CANNOT_VERIFY | `identity_unclear` | low |
| 6 | no `observed.record_date` (or not a date) | CANNOT_VERIFY | `missing_record_date` | low |
| 7 | no reference date | CANNOT_VERIFY | `no_reference_date` | low |
| 7b | `record_date` is AFTER the reference date (D3: no fact from after the as-of date may support or contradict a claim; one day after is enough) | NOT_COMPARABLE | `record_after_as_of`; `missing` = "A record dated on or before <reference date>." | high |
| 8 | record date more than `tolerances.<claim type>.max_record_age_days` (if that key exists, else the global `tolerances.max_record_age_days`) BEFORE the reference date | NOT_COMPARABLE | `stale_record` | medium |
| 9 | metric rules in section 3 (they also return `claim_value_unusable` when the claim's value is not a usable number) | any | see section 3 | see section 3 |

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

## 4. Reason codes the report lane can rely on

HELD: `timeout`, `error`, `budget`, `time`, `no_checker` (core `HeldReason`). CANNOT_VERIFY: `no_evidence`, `identity_unclear`, `entity_not_found`,
`claim_value_unusable`, `missing_record_date`, `no_reference_date`, `unsupported_metric`, `source_may_be_incomplete`,
`round_not_found`, `investor_not_listed`, `employer_not_in_profile`, `title_unmapped`, `missing_dates`.
NOT_COMPARABLE: `record_after_as_of`, `stale_record`, `currency_mismatch`, `informal_title`, plus any checker-given `not_comparable_reason`.
SUPPORTED: `within_tolerance`, `within_tolerance_undated_rounds`, `within_band`, `investor_listed`, `employer_listed`,
`title_level_met`, `tenure_within_tolerance`. CONTRADICTED: `outside_tolerance`, `outside_band`, `observed_higher`,
`title_level_lower`, `tenure_outside_tolerance`.

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

## 6. rules.yaml keys the engine reads

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
