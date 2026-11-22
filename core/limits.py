"""Run limits: compares ledger spend and elapsed time with config/rules.yaml `limits`.

Called by: core/runner.py before every claim, and by sources/ (crust.py, web.py) and LLM
callers before every external call via ensure_within(). Calls: core/store.py, core/config.py.
A hit limit raises LimitExceeded; the runner turns it into a HELD claim (budget or time).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from core import store
from core.config import rule
from core.models import HeldReason, RunContext


class LimitExceeded(Exception):
    """Raised before an external call that would break a run limit."""

    def __init__(self, reason: HeldReason, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


def elapsed_seconds(started_at: str | None) -> float:
    if started_at is None:
        return 0.0
    return (datetime.now(timezone.utc) - datetime.fromisoformat(started_at)).total_seconds()


def limit_reason(conn: sqlite3.Connection, rules: dict[str, Any], run_id: str,
                 started_at: str | None) -> tuple[HeldReason, str] | None:
    """Return (reason, detail) if the run is at or over a limit, else None."""
    totals = store.ledger_totals(conn, run_id)
    if totals["cost_inr"] >= float(rule(rules, "limits.max_cost_inr")):
        return HeldReason.BUDGET, f"cost_inr {totals['cost_inr']:.2f} >= max_cost_inr"
    if totals["credits"] >= float(rule(rules, "limits.max_credits")):
        return HeldReason.BUDGET, f"credits {totals['credits']} >= max_credits"
    seconds = elapsed_seconds(started_at)
    if seconds >= float(rule(rules, "limits.max_seconds")):
        return HeldReason.TIME, f"elapsed {seconds:.0f}s >= max_seconds"
    return None


def ensure_within(ctx: RunContext) -> None:
    """Call right before any external call. Raises LimitExceeded if a limit is reached."""
    hit = limit_reason(ctx.conn, ctx.rules, ctx.run.id, ctx.run.started_at)
    if hit is not None:
        raise LimitExceeded(*hit)
