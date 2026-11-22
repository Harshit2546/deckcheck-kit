"""T07 tests: full run, kill and resume with no repeated calls, limits/timeouts/errors -> HELD,
missing stages wait instead of failing.

Called by: pytest. Calls: core/runner.py, core/store.py, tests/core/fakes.py, kill_child.py.
"""

import copy
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import fakes
from core import runner, store
from core.models import ClaimState, Run, RunInput, RunState, VerdictLabel

HERE = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def _reset_calls():
    fakes.CHECK_CALLS.clear()


def _new_run(conn, run_id="run-t") -> str:
    store.insert_run(conn, Run(id=run_id, input=RunInput("deck.pdf", "example.com", "2026-10-01")))
    return run_id


def _labels(conn, run_id):
    return {v.claim_id: (v.label, v.reason_code) for v in store.list_verdicts(conn, run_id)}


def test_full_run_reaches_done(conn, rules):
    rid = _new_run(conn)
    assert runner.start(conn, rules, rid, stages=fakes.STAGES) is True
    assert store.get_run(conn, rid).state is RunState.DONE
    assert all(l is VerdictLabel.SUPPORTED for l, _ in _labels(conn, rid).values())
    assert store.get_report(conn, rid)[0]["verdicts"] == 3
    assert len(store.list_actions(conn, rid)) == 1
    assert store.get_resolution(conn, rid) == {"company": {"id": "co-1", "confidence": "high"}}


def test_kill_mid_check_then_resume_repeats_no_call(conn, rules, tmp_path):
    db = tmp_path / "kill.db"
    c = store.connect(db)
    rid = _new_run(c)
    env = {**os.environ, "FAKE_KILL_AT": runner.claim_id(rid, 2)}
    child = subprocess.run([sys.executable, str(HERE / "kill_child.py"), str(db), rid], env=env)
    assert child.returncode == 137
    assert store.get_run(c, rid).state is RunState.CHECKING
    states = [cl.state for cl in store.list_claims(c, rid)]
    assert states == [ClaimState.DECIDED, ClaimState.PENDING, ClaimState.PENDING]
    assert store.ledger_totals(c, rid)["calls"] == 1

    assert runner.resume(c, rules, rid, stages=fakes.STAGES) is True
    assert fakes.CHECK_CALLS[runner.claim_id(rid, 1)] == 0       # not re-checked
    endpoints = [e.endpoint_or_model for e in store.list_ledger(c, rid)]
    assert len(endpoints) == len(set(endpoints)) == 3            # one call per claim, ever
    assert len(store.list_actions(c, rid)) == 1


def test_resume_after_kill_inside_extract_step(conn, rules):
    rid = _new_run(conn)

    def dying_report(*a):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        runner.start(conn, rules, rid, stages={**fakes.STAGES, "report": dying_report})
    assert store.get_run(conn, rid).state is RunState.DECIDED
    assert runner.resume(conn, rules, rid, stages=fakes.STAGES) is True
    assert sum(fakes.CHECK_CALLS.values()) == 3


def test_budget_limit_holds_remaining_claims(conn, rules):
    r = copy.deepcopy(rules)
    r["limits"]["max_credits"] = 1           # first check spends 1 credit
    rid = _new_run(conn)
    runner.start(conn, r, rid, stages=fakes.STAGES)
    labels = list(_labels(conn, rid).values())
    assert labels[0][0] is VerdictLabel.SUPPORTED
    assert labels[1:] == [(VerdictLabel.HELD, "budget")] * 2
    assert store.ledger_totals(conn, rid)["calls"] == 1


def test_time_limit_holds_claims(conn, rules):
    rid = _new_run(conn)
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    conn.execute("UPDATE runs SET started_at = ? WHERE id = ?", (past, rid))
    runner.start(conn, rules, rid, stages=fakes.STAGES)
    assert {v for v in _labels(conn, rid).values()} == {(VerdictLabel.HELD, "time")}
    assert store.ledger_totals(conn, rid)["calls"] == 0


@pytest.mark.parametrize("exc, reason", [(TimeoutError("slow"), "timeout"),
                                         (RuntimeError("boom"), "error")])
def test_timeouts_and_errors_become_held(conn, rules, exc, reason):
    rid = _new_run(conn)

    def bad_check(claim, ctx):
        raise exc
    runner.start(conn, rules, rid, stages={**fakes.STAGES, "check": bad_check})
    assert {v for v in _labels(conn, rid).values()} == {(VerdictLabel.HELD, reason)}
    assert store.get_run(conn, rid).state is RunState.DONE


def test_missing_checker_module_is_held(conn, rules):
    rid = _new_run(conn)
    stages = {k: v for k, v in fakes.STAGES.items() if k != "check"}   # no checkers/ yet
    runner.start(conn, rules, rid, stages=stages)
    assert {v for v in _labels(conn, rid).values()} == {(VerdictLabel.HELD, "no_checker")}


def test_missing_stage_waits_then_resumes(conn, rules):
    rid = _new_run(conn)
    assert runner.start(conn, rules, rid) is False          # extract/ not built yet
    run = store.get_run(conn, rid)
    assert run.state is RunState.CREATED and "not built yet" in run.error
    assert runner.resume(conn, rules, rid, stages=fakes.STAGES) is True


def test_resume_done_run_does_nothing(conn, rules):
    rid = _new_run(conn)
    runner.start(conn, rules, rid, stages=fakes.STAGES)
    assert runner.resume(conn, rules, rid, stages=fakes.STAGES) is True
    assert sum(fakes.CHECK_CALLS.values()) == 3
