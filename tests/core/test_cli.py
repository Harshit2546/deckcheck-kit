"""T01 tests: CLI help works, `run` creates a run row, `resume` rejects unknown ids, rules load.

Called by: pytest. Calls: cli.py, core/store.py, core/config.py.
"""

import subprocess
import sys
from pathlib import Path

import pytest

import cli
from core import store
from core.config import load_rules

ROOT = Path(__file__).resolve().parents[2]


def test_run_help_works():
    out = subprocess.run([sys.executable, "cli.py", "run", "--help"], cwd=ROOT,
                         capture_output=True, text=True)
    assert out.returncode == 0 and "--deck" in out.stdout


def test_run_creates_run_row(tmp_path):
    deck = tmp_path / "deck.pdf"
    deck.write_bytes(b"%PDF-1.4")
    db = tmp_path / "d.db"
    # exit 1: run created but not finished, extract/ is not built yet (runner waits)
    assert cli.main(["--db", str(db), "run", "--deck", str(deck), "--domain", "Example.com"]) == 1
    runs = store.list_runs(store.connect(db))
    assert "not built yet" in runs[0].error
    assert len(runs) == 1
    assert runs[0].input.domain == "example.com"
    assert runs[0].input.deck_date_source == "missing"
    assert runs[0].started_at is not None


def test_run_rejects_missing_deck(tmp_path):
    assert cli.main(["--db", str(tmp_path / "d.db"), "run", "--deck", "nope.pdf",
                     "--domain", "x.com"]) == 2


def test_resume_unknown_run(tmp_path):
    assert cli.main(["--db", str(tmp_path / "d.db"), "resume", "run-missing"]) == 2


def test_rules_missing_key_fails_fast(tmp_path):
    bad = tmp_path / "rules.yaml"
    bad.write_text("limits:\n  max_cost_inr: 1\n")
    with pytest.raises(ValueError, match="max_seconds"):
        load_rules(bad)
