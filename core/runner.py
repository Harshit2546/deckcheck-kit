"""Runner: moves a run through created -> extracted -> resolved -> checking -> decided ->
reported -> done, checkpointing each claim, and enforcing cost and time limits.

Called by: cli.py (run, resume), ui/app.py. Calls: core/store.py, core/log.py and, once
wired, extract/, resolve/, checkers/, verdict/, report/, actions/.
T01 STUB: start() and resume() only mark the run started and log. T07 implements the steps.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from core import store
from core.log import log_step


def start(conn: sqlite3.Connection, rules: dict[str, Any], run_id: str) -> None:
    """Run every step for a new run. T07 replaces the body; the signature is the contract."""
    store.mark_run_started(conn, run_id)
    log_step(run_id, None, "runner.start", "stub", note="pipeline not wired yet (T07)")


def resume(conn: sqlite3.Connection, rules: dict[str, Any], run_id: str) -> None:
    """Continue a run after a kill, skipping every step and claim already marked done."""
    run = store.get_run(conn, run_id)
    if run is None:
        raise ValueError(f"no run with id {run_id}")
    log_step(run_id, None, "runner.resume", "stub", state=run.state.value,
             note="pipeline not wired yet (T07)")
