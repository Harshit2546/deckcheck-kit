"""Builders for hand-made Claim and CheckResult fixtures used by tests/verdict (test data only, never runtime).

Called by: tests/verdict/*.py. Calls: core/models.py.
"""

from core.models import CheckResult, Claim, ClaimType, Evidence, SourceType

REF = "2026-01-15"      # the date the claims refer to
FRESH = "2026-01-10"    # 5 days from REF: fresh


def make_claim(ctype: ClaimType, metric: str | None, value, unit: str | None = None, **kw) -> Claim:
    return Claim(id="c1", run_id="r1", slide=3, quote="q", type=ctype, subject=kw.pop("subject", "Acme"),
                 metric=metric, value=value, unit=unit, as_of=kw.pop("as_of", REF), **kw)


def make_result(observed: dict, source: SourceType = SourceType.CRUSTDATA_COMPANY, **kw) -> CheckResult:
    """A comparable, confirmed, fresh result unless the test overrides it."""
    base = {"identity": "confirmed", "identity_signals": 2, "record_date": FRESH, "reference_date": REF}
    base.update(observed)
    ev = Evidence(id="e1", claim_id="c1", source_type=source, locator="/api", field_or_quote="field",
                  value=None, record_date=base.get("record_date"), retrieved_at="2026-01-15T10:00:00+00:00",
                  call_id="L1")
    return CheckResult(evidence=kw.pop("evidence", [ev]), observed=base, **kw)
