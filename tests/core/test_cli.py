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


# ---------- D3 request / --out (fixtures in tests only) ----------

import json  # noqa: E402

import fakes  # noqa: E402
from core import runner  # noqa: E402

# Fakes for extract/resolve/check/decide; the real report/builder.py and actions/email.py run.
CLI_STAGES = {k: v for k, v in fakes.STAGES.items() if k in ("extract", "resolve", "check", "decide")}


def _request(tmp_path, **over):
    (tmp_path / "decks").mkdir()
    (tmp_path / "decks" / "deck.pdf").write_bytes(b"%PDF-1.4")
    req = {"request": "Check this synthetic deck.", "deck_path": "decks/deck.pdf",
           "company_domain": "Example.in", "deck_date": "2026-10-01", "founder_urls": [], **over}
    path = tmp_path / "request.json"
    path.write_text(json.dumps(req))
    return path


@pytest.fixture
def fake_stages(monkeypatch):
    real_start, real_resume = runner.start, runner.resume
    state = {"stages": dict(CLI_STAGES)}
    monkeypatch.setattr(runner, "start", lambda c, r, rid: real_start(c, r, rid, stages=state["stages"]))
    monkeypatch.setattr(runner, "resume", lambda c, r, rid: real_resume(c, r, rid, stages=state["stages"]))
    return state


def test_run_request_writes_d3_json_and_markdown(tmp_path, fake_stages):
    db, out = tmp_path / "d.db", tmp_path / "out" / "result.json"
    rc = cli.main(["--db", str(db), "run", "--request", str(_request(tmp_path)), "--out", str(out)])
    assert rc == 0
    result = json.loads(out.read_text())
    assert result["company"]["domain"] == "example.in" and result["as_of"] == "2026-10-01"
    assert len(result["claims"]) == 3
    assert {c["verdict"] for c in result["claims"]} == {"SUPPORTED"}
    assert "claimed_value" in result["claims"][0] and "url_or_endpoint" in result["claims"][0]["sources"][0]
    assert result["ledger"]["calls"] == 3
    assert out.with_suffix(".md").read_text().strip()
    run = store.list_runs(store.connect(db))[0]
    assert run.input.deck_path == str((tmp_path / "decks" / "deck.pdf").resolve())


def test_resume_with_out_after_a_failed_step(tmp_path, fake_stages):
    db, out = tmp_path / "d.db", tmp_path / "result.json"
    fakes.CHECK_CALLS.clear()

    def broken_report(*a):
        raise RuntimeError("report crashed")
    fake_stages["stages"]["report"] = broken_report
    assert cli.main(["--db", str(db), "run", "--request", str(_request(tmp_path)), "--out", str(out)]) == 1
    assert not out.exists()
    run_id = store.list_runs(store.connect(db))[0].id

    del fake_stages["stages"]["report"]
    assert cli.main(["--db", str(db), "resume", run_id, "--out", str(out)]) == 0
    assert json.loads(out.read_text())["run_id"] == run_id
    assert sum(fakes.CHECK_CALLS.values()) == 3          # resume re-checked nothing


def test_run_request_rejects_bad_request(tmp_path):
    req = _request(tmp_path, deck_date="tomorrow")
    assert cli.main(["--db", str(tmp_path / "d.db"), "run", "--request", str(req)]) == 2


def test_run_needs_request_or_deck_and_domain(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["--db", str(tmp_path / "d.db"), "run", "--deck", "x.pdf"])
    with pytest.raises(SystemExit):
        cli.main(["--db", str(tmp_path / "d.db"), "run", "--request", "r.json", "--domain", "x.com"])
