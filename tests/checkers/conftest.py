"""Test fixtures for checkers: sqlite conn, rules, mock RunContext."""

from pathlib import Path
import pytest

from core import store
from core.config import load_rules
from core.models import Run, RunContext, RunInput, RunState, now_iso


@pytest.fixture
def conn(tmp_path: Path):
    c = store.connect(tmp_path / "test.db")
    yield c
    c.close()


@pytest.fixture
def rules():
    r = load_rules()
    r["verdict"] = {"supported_margin": 0.5, "strong_margin": 2.0, "fresh_days": 90}
    return r


@pytest.fixture
def make_ctx(conn, rules):
    def _make(domain: str = "swiftroute.in", deck_date: str = "2024-05-15") -> RunContext:
        r_input = RunInput(
            deck_path="tests/decks/deck_a.pdf",
            domain=domain,
            deck_date=deck_date,
            deck_date_source="input",
        )
        r = Run(
            id="run-test-1",
            input=r_input,
            state=RunState.CHECKING,
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        store.insert_run(conn, r)
        return RunContext(conn=conn, rules=rules, run=r)

    return _make
