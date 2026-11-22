"""Test setup for tests/resolve: repo root and this folder on sys.path, plus the `rules` and `crust` fixtures.

Called by: pytest. Calls: core/config.py, resolve_fakes.py (test data only, never imported by runtime code).
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

from core.config import load_rules  # noqa: E402
from resolve_fakes import FakeCrust  # noqa: E402


@pytest.fixture
def rules() -> dict:
    return copy.deepcopy(load_rules())


@pytest.fixture
def crust(monkeypatch: pytest.MonkeyPatch) -> FakeCrust:
    """Installs a fake `sources.crust` for the test and returns it so the test can script and inspect calls."""
    fake = FakeCrust()
    fake.install(monkeypatch)
    return fake
