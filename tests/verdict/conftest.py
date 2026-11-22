"""Test setup for tests/verdict: repo root on sys.path, a rules fixture that includes the `verdict:` block,
and builders for hand-made CheckResult fixtures (test data only; never used at runtime).

Called by: pytest. Calls: core/config.py, core/models.py.
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

from core.config import load_rules  # noqa: E402


@pytest.fixture
def rules() -> dict:
    """Real rules.yaml plus the verdict block requested in DECISIONS D8 (until claude-core adds it)."""
    r = copy.deepcopy(load_rules())
    r["verdict"] = {"supported_margin": 0.5, "strong_margin": 2.0, "fresh_days": 90}
    return r
