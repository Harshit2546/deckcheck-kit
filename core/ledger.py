"""Ledger: one row per external call (Crustdata, LLM, web), including failed calls, with the
rupee cost worked out from config/rules.yaml "costs".

Called by: sources/crust.py, sources/web.py, extract/claims.py, any LLM caller, core/runner.py.
Calls: core/store.py, core/config.py. Rows are append-only (DB trigger); never edit them.
"""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from core.config import rule
from core.models import LedgerEntry, Provider
from core.store import insert_ledger


def new_call_id() -> str:
    """Id for a ledger row; put it on Evidence.call_id for facts this call returned."""
    return "call-" + uuid.uuid4().hex[:12]


def cost_inr(rules: dict[str, Any], provider: Provider, endpoint_or_model: str,
             credits: float, tokens_in: int, tokens_out: int) -> float:
    """Rupee cost of one call from rules.yaml rates (LLM rates per model, else 'default')."""
    if provider is Provider.CRUSTDATA:
        return credits * float(rule(rules, "costs.crustdata.inr_per_credit"))
    if provider is Provider.LLM:
        models = rule(rules, "costs.llm")
        rates = models.get(endpoint_or_model, models["default"])
        return (tokens_in * float(rates["inr_per_1k_tokens_in"])
                + tokens_out * float(rates["inr_per_1k_tokens_out"])) / 1000
    return float(rule(rules, "costs.web.inr_per_call"))


def record(conn: sqlite3.Connection, rules: dict[str, Any], run_id: str, provider: Provider,
           endpoint_or_model: str, *, duration_ms: int, ok: bool, error: str | None = None,
           credits: float = 0.0, tokens_in: int = 0, tokens_out: int = 0,
           call_id: str | None = None) -> LedgerEntry:
    """Write the ledger row for one finished (or failed) call and return it.

    Call this in a finally block so failed and timed-out calls are recorded too.
    Pass call_id if you generated it earlier with new_call_id().
    """
    entry = LedgerEntry(
        id=call_id or new_call_id(), run_id=run_id, provider=provider,
        endpoint_or_model=endpoint_or_model, credits=credits, tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_inr=round(cost_inr(rules, provider, endpoint_or_model, credits, tokens_in,
                                tokens_out), 4),
        duration_ms=duration_ms, ok=ok, error=error,
    )
    insert_ledger(conn, entry)
    return entry
