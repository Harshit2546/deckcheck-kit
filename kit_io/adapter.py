"""Kickoff-kit adapter: maps the organizers' Investing request to RunInput, and our report
back to their output format. (Folder is kit_io/, not io/, see DECISIONS.md D4.)

Called by: cli.py / ui/app.py once the kit format is known; report/ for output.
Calls: core/models.py. T01 STUB: the mapping waits for T06 (kit format, DECISIONS.md D3).
"""

from __future__ import annotations

from typing import Any

from core.models import RunInput


def from_kit(request: dict[str, Any]) -> RunInput:
    """Kickoff-kit request -> RunInput. Fill in from DECISIONS.md D3."""
    raise NotImplementedError("kit input format not recorded yet (T06 / DECISIONS.md D3)")


def to_kit(report: dict[str, Any]) -> dict[str, Any]:
    """Our report dict -> kickoff-kit output. Fill in from DECISIONS.md D3."""
    raise NotImplementedError("kit output format not recorded yet (T06 / DECISIONS.md D3)")
