"""Test setup for tests/actions: repo root on sys.path, test logs out of logs/, a fresh DB,
and a run with a saved report (fixture data lives in tests/ only).

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
from core.models import Run, RunInput  # noqa: E402

REPORT = {
    "run": {"id": "run-a", "domain": "example.com"},
    "founder_questions": [{"claim_id": "run-a-c001", "slide": 3,
                           "question": "Our data shows 80 employees; how do you count 120?"}],
    "evidence_requests": [{"claim_id": "run-a-c002", "slide": 5,
                           "request": "A term sheet or bank record for the seed round."}],
}


def make_run(conn, run_id="run-a", report=REPORT):
    store.insert_run(conn, Run(id=run_id, input=RunInput("deck.pdf", "example.com", "2026-10-01")))
    store.save_report(conn, run_id, report, "# report")
    return run_id


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "actions.db"


@pytest.fixture
def conn(db_path):
    c = store.connect(db_path)
    yield c
    c.close()


@pytest.fixture
def rules():
    return load_rules()
