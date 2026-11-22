"""Test setup for tests/ui: repo root on sys.path, test logs out of logs/, a temp DB with one
run (fixture data lives in tests/ only).

Called by: pytest. Calls: core/store.py.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DECKCHECK_LOG_DIR", tempfile.mkdtemp(prefix="deckcheck-logs-"))
# AppTest cannot run component iframes: draw the static fallbacks (ui/components MISSING path).
os.environ.setdefault("DECKCHECK_STATIC_UI", "1")

import pytest  # noqa: E402

from core import store  # noqa: E402

APP = str(Path(__file__).resolve().parents[2] / "ui" / "app.py")


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "ui.db")


@pytest.fixture
def conn(db_path):
    c = store.connect(db_path)
    yield c
    c.close()


@pytest.fixture
def deck(tmp_path):
    path = tmp_path / "deck.pdf"
    path.write_bytes(b"%PDF-1.4")
    return path


def open_app(db_path, page):
    """Render ui/app.py on one page against db_path."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    at.sidebar.text_input[0].input(db_path).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, at.exception
    return at
