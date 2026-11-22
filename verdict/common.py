"""Small shared helpers for the verdict rules: number and date parsing, confidence caps, Verdict builder.

Who calls it: verdict/engine.py and the per-type rule files (team_size.py, funding.py, founder.py).
What it calls: core.models only. No I/O, no LLM, no clock: the same input always gives the same verdict.
Thresholds never live here; they are read from config/rules.yaml by the callers (core.config.rule).
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from core.models import CheckResult, Claim, ClaimType, Confidence, Verdict, VerdictLabel

_CONF_RANK = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}

# What would settle a claim, per reason code. Plain text for the evidence-request list; no numbers.
MISSING_TEXT: dict[str, str] = {
    "no_evidence": "Any dated record for this claim from a named source.",
    "identity_unclear": "A unique identifier (profile URL, registered company name) to tell the right entity from namesakes.",
    "entity_not_found": "A correct company domain or profile URL; the entity was not found.",
    "claim_value_unusable": "A clear number, unit and date for this claim from the deck.",
    "missing_record_date": "A source that states the date of the record.",
    "no_reference_date": "The date the claim refers to (slide date or deck date).",
    "unsupported_metric": "A rule for this metric; it is not checked automatically yet.",
    "source_may_be_incomplete": "A press release, filing or investor confirmation of the claimed amount.",
    "round_not_found": "The round announcement or filing for the claimed round.",
    "investor_not_listed": "A press release or filing that names the investor.",
    "employer_not_in_profile": "The founder's own profile or an article that lists this employer and title.",
    "title_unmapped": "The exact title at that employer from a profile or article.",
    "missing_dates": "Start and end dates of the role from a profile or article.",
    "stale_record": "A record dated close to the date the claim refers to.",
    "record_after_as_of": "A record dated on or before the date the claim refers to.",
    "currency_mismatch": "The figure in the same currency as the deck states it.",
    "informal_title": "A formal title from a profile or article.",
    # T29
    "metric_mismatch": "A figure for exactly the metric the deck states (same scope, same unit).",
    "observed_more_than_claimed": "The company's own count and date for this figure.",
    "growth_scale_unclear": "Audited or management accounts for both periods of the growth figure.",
    "estimate_gap_unclear": "Audited or management accounts for the period the deck refers to.",
    "founding_year_close": "The certificate of incorporation or the company registry entry.",
    "location_unclear": "The registered and operating addresses from the company registry or website.",
    "prior_company_not_checked": "The name or domain of the founder's earlier company and a deal announcement for its exit.",
    "acquirer_differs": "The deal announcement naming the acquirer.",
}


def num(value: Any) -> float | None:
    """Return value as a finite float, or None. Accepts int, float and clean numeric strings; never bool."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            value = float(value.replace(",", "").strip())
        except ValueError:
            return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def parse_date(value: Any) -> date | None:
    """Parse 'YYYY-MM-DD' (or the date part of an ISO datetime); None if it is not a date."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def rel_diff(observed: float, claimed: float) -> float:
    """abs(observed - claimed) / claimed. Claimed 0: 0 for an exact match, infinity otherwise."""
    if claimed == 0:
        return 0.0 if observed == 0 else math.inf
    return abs(observed - claimed) / abs(claimed)


def cap(conf: Confidence, ceiling: Confidence) -> Confidence:
    """Return the lower of two confidences."""
    return conf if _CONF_RANK[conf] <= _CONF_RANK[ceiling] else ceiling


def pick(high: bool, ok_conf: Confidence = Confidence.MEDIUM) -> Confidence:
    """HIGH when the condition holds, otherwise ok_conf."""
    return Confidence.HIGH if high else ok_conf


def headcount_missing(claim: Claim, result: CheckResult) -> str | None:
    """D13: for headcount claims with no dated history point, say which record would settle it; else None."""
    if claim.type not in (ClaimType.TEAM_SIZE, ClaimType.TEAM_GROWTH):
        return None
    ref = parse_date(result.observed.get("reference_date")) or parse_date(claim.as_of)
    return f"A headcount record dated on or before {ref}." if ref else "A dated headcount record."


def source_text(result: CheckResult) -> str:
    """Short, factual description of the first evidence row, for explanations."""
    if not result.evidence:
        return "the checked source"
    ev = result.evidence[0]
    return f"{ev.source_type.value} field '{ev.field_or_quote}'"


def make(claim: Claim, result: CheckResult, st: dict[str, Any] | None, label: VerdictLabel, reason: str,
         conf: Confidence, text: str, missing: str | None = None) -> Verdict:
    """Build the Verdict. Applies the confidence ceiling from `st`; `missing` defaults to MISSING_TEXT for non-SUPPORTED labels."""
    if st is not None:
        conf = cap(conf, st["ceiling"])
    if missing is None and label is not VerdictLabel.SUPPORTED:
        missing = MISSING_TEXT.get(reason, "More dated evidence from a named source.")
    return Verdict(claim_id=claim.id, label=label, reason_code=reason, explanation=text,
                   evidence_ids=[e.id for e in result.evidence], confidence=conf, missing=missing)
