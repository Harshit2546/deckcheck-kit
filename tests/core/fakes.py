"""Fake pipeline stages for runner tests (fixtures live in tests/ only, never at runtime).

Called by: tests/core/test_runner.py, tests/core/kill_child.py. Calls: core/ledger.py, core/store.py.
Each fake check writes one ledger row, like a real checker's Crustdata call.
"""

from __future__ import annotations

import os
import uuid
from collections import Counter
from typing import Any

from core import ledger, store
from core.models import (Action, ActionType, CheckResult, Claim, ClaimType, Confidence,
                         Evidence, Provider, SourceType, Verdict, VerdictLabel,
                         make_idempotency_key, now_iso)

CHECK_CALLS: Counter[str] = Counter()


def extract(ctx) -> list[Claim]:
    def c(slide: int, t: ClaimType, value: Any) -> Claim:
        return Claim(id="tmp", run_id=ctx.run.id, slide=slide, quote=f"quote {slide}", type=t,
                     subject="Example", metric="m", value=value)
    return [c(1, ClaimType.TEAM_SIZE, 120), c(2, ClaimType.FUNDING, 5_000_000),
            c(3, ClaimType.TEAM_GROWTH, 40)]


def resolve(ctx, claims: list[Claim]) -> dict[str, Any]:
    return {"company": {"id": "co-1", "confidence": "high"}}


def check(claim: Claim, ctx) -> CheckResult:
    if os.environ.get("FAKE_KILL_AT") == claim.id:      # kill_child.py: die like `kill -9`
        os._exit(137)
    CHECK_CALLS[claim.id] += 1
    call = ledger.record(ctx.conn, ctx.rules, ctx.run.id, Provider.CRUSTDATA,
                         f"/fake/{claim.id}", duration_ms=1, ok=True, credits=1)
    ev = Evidence(id="ev-" + uuid.uuid4().hex[:8], claim_id=claim.id,
                  source_type=SourceType.CRUSTDATA_COMPANY, locator=f"/fake/{claim.id}",
                  field_or_quote="value", value=claim.value, record_date="2026-11-01",
                  retrieved_at=now_iso(), call_id=call.id)
    return CheckResult(evidence=[ev], observed={"value": claim.value})


def decide(claim: Claim, result: CheckResult, rules: dict[str, Any]) -> Verdict:
    if result.held_reason:
        return Verdict(claim.id, VerdictLabel.HELD, result.held_reason, "held", [])
    return Verdict(claim.id, VerdictLabel.SUPPORTED, "match", "matches",
                   [e.id for e in result.evidence], Confidence.HIGH)


def report(conn, rules: dict[str, Any], run_id: str) -> tuple[dict[str, Any], str]:
    return {"run_id": run_id, "verdicts": len(store.list_verdicts(conn, run_id))}, "# report"


def draft(conn, rules: dict[str, Any], run_id: str) -> Action:
    to = rules["actions"]["test_inbox"]
    key = make_idempotency_key(run_id, ActionType.FOUNDER_EMAIL.value, to)
    return store.insert_action(conn, Action("act-" + run_id, run_id, ActionType.FOUNDER_EMAIL,
                                            key, to, "Questions", "body"))


STAGES = {"extract": extract, "resolve": resolve, "check": check, "decide": decide,
          "report": report, "draft": draft}
