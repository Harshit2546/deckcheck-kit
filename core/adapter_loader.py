"""Loads io/adapter.py by file path, because `import io.adapter` is impossible (stdlib `io` wins the name).

Who calls it: cli.py and report/ (anything that needs the kickoff-kit mapping).
What it calls: importlib only; the loaded module imports core.models and core.log.
If the folder is ever renamed (see HANDOFF open question), only ADAPTER_PATH here changes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ADAPTER_PATH = Path(__file__).resolve().parent.parent / "io" / "adapter.py"

_cache: ModuleType | None = None


def load_adapter() -> ModuleType:
    """Return the adapter module (request_from_kit, result_to_kit). Loaded once per process."""
    global _cache
    if _cache is None:
        spec = importlib.util.spec_from_file_location("deckcheck_kit_adapter", ADAPTER_PATH)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load adapter from {ADAPTER_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _cache = module
    return _cache
