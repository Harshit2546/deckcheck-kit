"""Kickoff-kit adapter (DECISIONS.md D3): maps a request JSON to our RunInput, and our report
plus company and founder email to the result JSON. The only place to change if the organizers
publish their own format.

Called by: cli.py / ui via core/adapter_loader.py (import io.adapter is impossible: stdlib io
owns the name). Calls: core/models.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.models import Action, RunInput

# report/builder.py field name -> D3 claim field name. Any other field keeps its name.
CLAIM_RENAMES: dict[str, str] = {"label": "verdict", "value": "claimed_value"}
SOURCE_FIELDS: list[tuple[str, str]] = [  # (our key, D3 key), in D3 order
    ("locator", "url_or_endpoint"), ("field_or_quote", "field_or_quote"), ("value", "value"),
    ("record_date", "record_date"), ("retrieved_at", "retrieved_at")]


def _date_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    datetime.strptime(str(value), "%Y-%m-%d")          # D3: YYYY-MM-DD or null
    return str(value)


def from_kit(request: dict[str, Any]) -> RunInput:
    """D3 request -> RunInput. deck_date null -> extract falls back to PDF metadata."""
    for required in ("deck_path", "company_domain"):
        if not request.get(required):
            raise ValueError(f"request is missing '{required}' (DECISIONS.md D3)")
    urls = request.get("founder_urls") or []
    if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
        raise ValueError("founder_urls must be a list of URLs (DECISIONS.md D3)")
    deck_date = _date_or_none(request.get("deck_date"))
    return RunInput(
        deck_path=str(request["deck_path"]),
        domain=str(request["company_domain"]).strip().lower(),
        deck_date=deck_date,
        deck_date_source="input" if deck_date else "missing",
        founder_urls=list(urls),
    )


def _source(src: dict[str, Any]) -> dict[str, Any]:
    return {kit: src.get(ours) for ours, kit in SOURCE_FIELDS}


def _claim(row: dict[str, Any]) -> dict[str, Any]:
    """Keep the order of rules.yaml output.fields; rename to D3 names."""
    out: dict[str, Any] = {}
    for key, value in row.items():
        if key == "sources":
            value = [_source(s) for s in value or []]
        out[CLAIM_RENAMES.get(key, key)] = value
    return out


def _company(domain: str | None, company: dict[str, Any] | None) -> dict[str, Any]:
    c = company or {}
    return {"name": c.get("name"), "domain": c.get("domain") or domain,
            "identity": c.get("identity") or c.get("confidence"),
            "source": c.get("source") or c.get("locator")}


def to_kit(report: dict[str, Any], company: dict[str, Any] | None = None,
           founder_email: Action | None = None) -> dict[str, Any]:
    """report/builder.py report -> D3 result JSON.

    company: the resolved company (store.get_resolution(conn, run_id)["company"]), if any.
    founder_email: the run's Action from store.list_actions(conn, run_id), if drafted.
    """
    run = report.get("run", {})
    ledger = report.get("ledger", {})
    return {
        "run_id": run.get("id"),
        "company": _company(run.get("domain"), company),
        "as_of": run.get("deck_date"),
        "claims": [_claim(r) for r in report.get("claims", [])],
        "red_flags": report.get("red_flags", []),
        "founder_questions": report.get("founder_questions", []),
        "evidence_requests": report.get("evidence_requests", []),
        "ledger": {"calls": ledger.get("calls", 0), "credits": ledger.get("credits", 0),
                   "cost_inr": ledger.get("cost_inr", 0),
                   "seconds": round(ledger.get("duration_ms", 0) / 1000, 1)},
        "founder_email": (None if founder_email is None else
                          {"status": founder_email.status.value,
                           "recipient": founder_email.recipient}),
    }
