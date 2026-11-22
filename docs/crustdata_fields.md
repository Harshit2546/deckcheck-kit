# Crustdata fields for DeckCheck

This is the T02 field reference for the company and founder probe.
It lists the documented REST contract and the fields to inspect in Deck A responses.
The account rates are verified. Field availability still needs a live Deck A probe.

## Probe status

Reviewed the official API reference on 2026-11-22 for version `2025-11-01` at
`https://api.crustdata.com`. The authenticated account preflight succeeded.
Deck A's company and founder identifiers are pending, so the enrichment
field maps below are still based on the reference. Live entity fields,
enrichment charges, and sanitized entity fixtures are pending.

### Live account metadata

`GET /account/endpoints` returned HTTP 200 at `2026-11-22T06:33:32+00:00`.
It returned API version `2025-11-01` and `token_limit_rpm: 100`.
Each relevant endpoint was enabled. These rates came from the response.

| Endpoint | Effective requests per minute | Base credits | Relevant premium rates |
| --- | ---: | ---: | --- |
| `POST /company/enrich` | 5 | 2 per company | The requested sections have the base rate. Optional `technographics` adds 2 credits. |
| `POST /person/enrich` | 5 | 1 per person | The requested professional sections have the base rate. Contact fields were excluded from the probe plan. |
| `POST /person/search` | 5 | 0.03 per result | `experience` adds 0.1 per result when used as a filter and another 0.1 per result when requested in the response. |

The account metadata response reported no per-request credit charge. Its
ledger row (`t02-account-fa48ec8c7d`, `call-d7de68ed98cd`, 2,094 ms) records
0 credits as an estimate. Actual billing for that call is unverified.

## Endpoints and credits

Use bearer authentication and the `x-api-version: 2025-11-01` header. Published
rates are per returned record or result as shown below. A batched request can
use multiple credits. Use the verified account rates above to estimate this probe. [Crustdata pricing](https://docs.crustdata.com/general/pricing)

| Method and path | Use in the probe | Published credit cost |
| --- | --- | --- |
| `GET /account/endpoints` | Check `status`, `effective_rate_limit_rpm`, `base_credits`, and premium filter and field pricing for the team's token. | Account metadata. The public pricing table does not list a charge. |
| `POST /company/enrich` | Submit Deck A's domain in `domains` with `exact_match: true`. Request `basic_info`, `people`, `locations`, `headcount`, `funding`, `revenue`, and `hiring` explicitly. Use the same endpoint for a prior company when the claim requires it. | 2 per company record for these sections. |
| `POST /person/enrich` | Submit founder profile URLs in `professional_network_profile_urls`. Request `basic_profile`, `social_handles.professional_network_identifier.profile_url`, `experience`, and `education`. | 1 per person record for these fields. |
| `POST /person/search` | Use when a founder URL is unavailable. Filter by `basic_profile.name` and a current or past employer identifier, such as `experience.employment_details.current.company_id`. Request the corresponding employer fields to inspect the returned candidate. | 0.03 base per returned result, plus 0.1 for an experience filter and 0.1 for returned experience fields at the published rates. With those two charges and no other premium groups, 0.23 per result. |

The enrichment docs show match candidates under `matches[]` with
`confidence_score`. The person endpoint also reports `match_status`. Search
returns `profiles[]`, `next_cursor`, and `total_count`. Use returned profile and
employer identifiers to corroborate identity before using candidate evidence.
[Company enrichment reference](https://docs.crustdata.com/company-docs/enrichment/reference)
[Person enrichment reference](https://docs.crustdata.com/person-docs/enrichment/reference)
[Person search reference](https://docs.crustdata.com/person-docs/search/reference)

## Company response fields

Paths below are relative to `matches[].company_data`.

| Claim or decision | Fields to inspect | Date available in the reference |
| --- | --- | --- |
| Company identity and facts | `crustdata_company_id`, `basic_info.name`, `basic_info.primary_domain`, `basic_info.all_domains`, `basic_info.website`, `basic_info.professional_network_url`, `basic_info.company_type`, `basic_info.status`, `locations.headquarters` | `updated_at` is the nullable record refresh timestamp. `indexed_at` is the nullable index timestamp. |
| Founding year | `basic_info.year_founded` | Year precision. |
| Founder affiliation | `people.founders[].crustdata_person_id`, `people.founders[].basic_profile.name`, `people.founders[].basic_profile.current_title` | Company `updated_at` dates the record refresh. Use the person's employment record for role dates. |
| Team size and growth | `headcount.total`, `basic_info.employee_count_range`, `headcount.growth_percent`, `headcount.growth_absolute` | Growth keys describe trailing windows. `updated_at` dates the company record refresh. The documented `headcount` fields do not give a separate measurement date. |
| Funding | `funding.total_investment_usd`, `funding.last_round_amount_usd`, `funding.last_round_type`, `funding.funding_rounds` | `funding.last_fundraise_date` dates the last round. Inspect any dates on individual rounds in the live payload. |
| Prior exit | `revenue.acquisition_status`, `funding.acquisitions` | Inspect transaction date and the buyer/target direction in the live record. The public field table names the sections but does not specify the nested date and party paths. Verify the founder's affiliation and the transaction separately. |
| Hiring | `hiring.openings_count`, `hiring.openings_growth_percent`, `hiring.recent_openings` | Company `updated_at` dates the record refresh. Inspect the returned openings for posting dates. |

A named customer relationship needs a dated web page and an exact quote that
ties the companies to that relationship. The company enrichment field
reference does not list a named customers section.
[Company enrichment reference](https://docs.crustdata.com/company-docs/enrichment/reference)
[Company response examples](https://docs.crustdata.com/company-docs/enrichment/introduction)

## Person response fields

Paths below are relative to `matches[].person_data`. Search exposes similar
sections under `profiles[]`. Its employer filter alias `company_id` is returned
as `crustdata_company_id` in the role.

| Claim or decision | Fields to inspect | Date available in the reference |
| --- | --- | --- |
| Founder identity | `crustdata_person_id`, `basic_profile.name`, `social_handles.professional_network_identifier.profile_url`, employer `crustdata_company_id` and `name` from the applicable role | `updated_at` is the nullable profile refresh timestamp. `basic_profile.last_updated` is the basic profile update field. |
| Current or past employment | `experience.employment_details.current[]` and `experience.employment_details.past[]`, with role `name`, `title`, and `crustdata_company_id` | `start_date` is documented for roles. Inspect past roles for an end date and preserve the precision actually returned. |
| Education | `education.schools[].school`, `education.schools[].degree`, `education.schools[].field_of_study` | The documented example has no education dates. Inspect the live school records before relying on an attendance or graduation date. |

Keep `retrieved_at` as the time DeckCheck received the response. Preserve
event dates, profile refresh dates, and index dates as distinct fields.
Use the actual event date or its available precision for an event claim
and describe any missing dates explicitly.
[Person enrichment examples](https://docs.crustdata.com/person-docs/enrichment/introduction)
[Person enrichment reference](https://docs.crustdata.com/person-docs/enrichment/reference)
[Person search reference](https://docs.crustdata.com/person-docs/search/reference)

## Finish the Deck A probe

1. Look up the company by exact domain and fetch the founders by profile URL.
   Use the
   limited name and employer search only where a URL is missing.
2. Log each probe attempt, including failures, with its run ID, endpoint,
   status, duration, timestamp, credits, and INR cost. Label estimated costs
   and disclose missing billing data. Check which fields are present, empty,
   or permission-gated. Record event and refresh dates separately.
3. Save sanitized response bodies only under `tests/fixtures/crustdata/`.
   Remove contact fields recursively, including from nested employment
   records. Scan the serialized content for emails, phones, and secrets
   before staging it. Add the observed fields, date availability, and credit
   accounting to this document.
