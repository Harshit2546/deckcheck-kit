"""Test-only fakes for checker tests: a real RunContext plus recorded source payloads.

Called by: tests/checkers/conftest.py and the checker tests. Calls: core/models.py.
Recorded payloads live here in tests/ only; the runtime path never sees them.
"""

from __future__ import annotations

from typing import Any

from core.models import Run, RunContext, RunInput

COMPANY_PAYLOADS: dict[str, Any] = {}   # run_id -> recorded Crustdata company payload
MARKET_PAYLOADS: dict[str, Any] = {}    # run_id -> recorded web market result


def make_ctx(run_id: str = "run_1", company_domain: str = "example.in",
             company: dict[str, Any] | None = None, extras: dict[str, Any] | None = None,
             identity: str = "confirmed", identity_signals: int = 2,
             deck_date: str | None = "2024-06-01") -> RunContext:
    """RunContext as the runner builds it, with resolve's company entry already filled."""
    COMPANY_PAYLOADS[run_id] = company
    MARKET_PAYLOADS[run_id] = (extras or {}).get("market_data")
    run = Run(id=run_id, input=RunInput("deck.pdf", company_domain, deck_date))
    entities = {"company": {"id": "co-test", "identity": identity,
                            "identity_signals": identity_signals, "confidence": "high"}}
    if extras and "competitors" in extras:
        entities["competitors"] = extras["competitors"]
    return RunContext(conn=None, rules={}, run=run, entities=entities)


def fake_get_company(ctx: RunContext, domain: str) -> tuple[dict[str, Any] | None, str | None]:
    return COMPANY_PAYLOADS.get(ctx.run.id), "call-test"


def fake_search_market_data(ctx: RunContext, query: str) -> dict[str, Any] | None:
    return MARKET_PAYLOADS.get(ctx.run.id)
