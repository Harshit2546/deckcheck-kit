"""Test setup for tests/core: put the repo root on sys.path, keep test logs out of logs/,
and give each test a fresh DB.

Called by: pytest. Calls: core/store.py, core/config.py.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("DECKCHECK_LOG_DIR", tempfile.mkdtemp(prefix="deckcheck-logs-"))

import pytest  # noqa: E402

from core import store  # noqa: E402
from core.config import load_rules  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    c = store.connect(tmp_path / "test.db")
    yield c
    c.close()


@pytest.fixture
def rules():
    return load_rules()
