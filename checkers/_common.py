"""Shared helpers for checkers: the one way a checker fetches company data and reads identity.

Called by: checkers/*.py. Calls: sources/crust.py (lane codex-a) lazily, at check time.
A missing sources module raises ModuleNotFoundError, which core/runner.py turns into a HELD
claim (never CANNOT_VERIFY). There is no fallback or fake source at runtime (AGENTS.md).
"""

from __future__ import annotations

from typing import Any

from core.models import RunContext


def get_company(ctx: RunContext, domain: str) -> tuple[dict[str, Any] | None, str | None]:
    """Company payload and the ledger call_id for it, via sources.crust (D11 signature)."""
    from sources.crust import get_company as crust_get_company

    return crust_get_company(ctx, domain)


def company_identity(ctx: RunContext) -> dict[str, Any]:
    """Identity keys for CheckResult.observed, taken from what resolve/entities.py saved.

    Until resolve reports a company with identity and identity_signals, the identity is
    "unclear" with 0 signals, so the verdict engine stops at CANNOT_VERIFY identity_unclear.
    """
    company = (ctx.entities or {}).get("company") or {}
    return {
        "identity": company.get("identity", "unclear"),
        "identity_signals": int(company.get("identity_signals", 0)),
    }
