"""Loads io/adapter.py by file path, because `import io.adapter` cannot work (Python's
built-in io module already owns the name).

Called by: cli.py, report/, ui/ (anything that needs the kickoff-kit mapping).
Calls: importlib; the loaded module imports core.models.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ADAPTER_PATH = Path(__file__).resolve().parent.parent / "io" / "adapter.py"
_cache: ModuleType | None = None


def load_adapter() -> ModuleType:
    """Return the io/adapter.py module (from_kit, to_kit), loaded once per process."""
    global _cache
    if _cache is None:
        spec = importlib.util.spec_from_file_location("deckcheck_io_adapter", ADAPTER_PATH)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load adapter from {ADAPTER_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _cache = module
    return _cache
