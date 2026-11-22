"""DeckCheck motion components (route tracker, slide strip, value gauge, exactly-once send) for ui/app.py.

Called by: ui/app.py. Calls: streamlit.components.v1 (one declared component served from ./frontend,
plain HTML/JS, no build step and no CDN script). Payloads are built in ui/data.py.
`motion(kind, payload, key)` returns the component's value, or MISSING when components are off
(DECKCHECK_STATIC_UI=1, used by tests/ui because AppTest cannot run iframes) or failed to load;
the caller then draws the static HTML version from ui/theme.py so the data is always on screen.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.log import log_step

FRONTEND = Path(__file__).resolve().parent / "frontend"
MISSING = object()

try:
    import streamlit.components.v1 as _components
    _component = _components.declare_component("deckcheck_motion", path=str(FRONTEND))
except Exception as exc:  # noqa: BLE001 - any failure means: draw the static version instead
    _component = None
    log_step(None, None, "ui.motion", "unavailable", error=str(exc))


def enabled() -> bool:
    return _component is not None and os.environ.get("DECKCHECK_STATIC_UI") != "1"


def motion(kind: str, payload: dict[str, Any], key: str, default: Any = None) -> Any:
    """Render one motion component. Returns its value, or MISSING if the caller must draw the fallback."""
    if not enabled():
        return MISSING
    if "key" in payload or "default" in payload:   # reserved by Streamlit's component call
        raise ValueError(f"motion payload for {kind} must not use the reserved names 'key' or 'default'")
    try:
        return _component(kind=kind, key=key, default=default, **payload)
    except Exception as exc:  # noqa: BLE001
        log_step(None, None, f"ui.motion.{kind}", "failed", error=str(exc))
        return MISSING
