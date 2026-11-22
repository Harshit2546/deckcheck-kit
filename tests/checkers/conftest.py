"""Patch the source calls for checker tests (fixtures in tests/ only).

Called by: pytest for tests/checkers. Calls: checker_fakes.py.
"""

from __future__ import annotations

from pathlib import Path
import sys
import types

import pytest

# Ensure tests/checkers is on sys.path so checker_fakes can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))

import checker_fakes
from checkers import _common


@pytest.fixture(autouse=True)
def fake_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_common, "get_company", checker_fakes.fake_get_company)
    web = types.ModuleType("sources.web")
    web.search_market_data = checker_fakes.fake_search_market_data
    monkeypatch.setitem(sys.modules, "sources", sys.modules.get("sources") or types.ModuleType("sources"))
    monkeypatch.setitem(sys.modules, "sources.web", web)
