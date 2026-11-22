"""Maps the kickoff kit's request and result format to and from DeckCheck's internal models.

Who calls it: cli.py (input side) and report/ (output side), both through core/adapter_loader.py,
because a top-level package named `io` cannot be imported (it clashes with the stdlib `io` module).
What it calls: core.models and core.log only.
TODO(DECISIONS D3, written by the merger after reading the kickoff kit): replace the placeholder mapping below.
"""

from __future__ import annotations

from typing import Any

from core.log import log_step
from core.models import RunRequest


def request_from_kit(payload: dict[str, Any]) -> RunRequest:
    """Kit request -> RunRequest.

    PLACEHOLDER: assumes the kit already uses our field names (deck_path, company_domain, deck_date,
    founder_urls). TODO(DECISIONS D3): map the real kit field names once the merger has recorded them.
    """
    log_step(None, "adapter.request_from_kit", "placeholder_mapping_used")
    return RunRequest(
        deck_path=payload["deck_path"],
        company_domain=payload["company_domain"],
        deck_date=payload.get("deck_date"),
        founder_urls=list(payload.get("founder_urls", [])),
    )


def result_to_kit(run_id: str, internal_result: dict[str, Any]) -> dict[str, Any]:
    """Internal report dict -> kit result format.

    TODO(DECISIONS D3): not implemented; the report lane needs the kit's output format first.
    """
    raise NotImplementedError("kit output format unknown: see HANDOFF open questions / DECISIONS D3")
