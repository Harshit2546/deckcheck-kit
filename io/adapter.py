"""Kickoff-kit adapter: maps the organizers' Investing request to our RunInput, and our report
back to the kit's output format.

Called by: cli.py / ui via core/adapter_loader.py (import io.adapter is impossible: stdlib io
owns the name). Calls: core/models.py.
TODO(T06): field names below are provisional; replace them with the kit format the merger
records in DECISIONS.md D3.
"""

from __future__ import annotations

from typing import Any

from core.models import RunInput

# TODO(T06, DECISIONS.md D3): kit field name -> our field name. Provisional guesses.
INPUT_FIELDS: dict[str, str] = {
    "deck_path": "deck_path",
    "company_domain": "domain",
    "deck_date": "deck_date",
    "founder_profile_urls": "founder_urls",
}


def from_kit(request: dict[str, Any]) -> RunInput:
    """Kickoff-kit request dict -> RunInput. Missing deck date is flagged for PDF fallback."""
    mapped = {ours: request[kit] for kit, ours in INPUT_FIELDS.items() if kit in request}
    for required in ("deck_path", "domain"):
        if required not in mapped:
            raise ValueError(f"kit request has no field for '{required}' (see DECISIONS.md D3)")
    deck_date = mapped.get("deck_date") or None
    return RunInput(
        deck_path=str(mapped["deck_path"]),
        domain=str(mapped["domain"]).strip().lower(),
        deck_date=deck_date,
        deck_date_source="input" if deck_date else "missing",
        founder_urls=list(mapped.get("founder_urls") or []),
    )


def to_kit(report: dict[str, Any]) -> dict[str, Any]:
    """Our report dict -> kickoff-kit output. TODO(T06, D3): rename fields to the kit format."""
    return dict(report)
