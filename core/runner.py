"""Runner: drives a run through created -> extracted -> resolved -> checking -> decided ->
reported -> done, checkpointing every step and every claim in SQLite so a killed run resumes
where it stopped, and turning limits, timeouts and errors into HELD claims.

Called by: cli.py (run, resume), ui/app.py. Calls: core/store.py, core/limits.py, core/log.py,
and the other lanes' stages through STAGES (signatures fixed in DECISIONS.md D7).
"""

from __future__ import annotations

import dataclasses
import importlib
import sqlite3
from collections.abc import Callable
from typing import Any

from core import store
from core.limits import LimitExceeded, limit_reason
from core.log import log_error, log_step
from core.models import (CheckResult, Claim, ClaimState, HeldReason, RunContext, RunState)

# stage name -> "module:function". Signatures (D7):
#   extract(ctx) -> list[Claim]                  resolve(ctx, claims) -> dict (entities)
#   check(claim, ctx) -> CheckResult             decide(claim, result, rules) -> Verdict
#   report(conn, rules, run_id) -> (dict, str)   draft(conn, rules, run_id) -> Action | None
STAGES: dict[str, str] = {
    "extract": "extract.claims:run",
    "resolve": "resolve.entities:run",
    "check": "checkers.{claim_type}:check",
    "decide": "verdict.engine:decide",
    "report": "report.builder:build",
    "draft": "actions.email:draft",
}

Stages = dict[str, Callable[..., Any]]


class StageMissing(Exception):
    """A stage's module or function is not in the repo yet (another lane has not merged it)."""


def _import(target: str) -> Callable[..., Any]:
    module_name, func_name = target.split(":")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name and module_name.startswith(e.name):
            raise StageMissing(f"{module_name} is not built yet") from e
        raise
    func = getattr(module, func_name, None)
    if func is None:
        raise StageMissing(f"{module_name}.{func_name} is not built yet")
    return func


def _default_check(claim: Claim, ctx: RunContext) -> CheckResult:
    return _import(STAGES["check"].format(claim_type=claim.type.value))(claim, ctx)


def _stage(stages: Stages | None, name: str) -> Callable[..., Any]:
    """Tests pass `stages` with fakes (fixtures live in tests/ only); runtime imports STAGES."""
    if stages and name in stages:
        return stages[name]
    if name == "check":
        return _default_check
    return _import(STAGES[name])


def claim_id(run_id: str, n: int) -> str:
    """Deterministic claim id, so a re-run of extract can never create a second copy."""
    return f"{run_id}-c{n:03d}"


# ---------- steps (each ends in one transaction that saves its output and the new state) ----

def _extract(ctx: RunContext, stages: Stages | None) -> None:
    claims = _stage(stages, "extract")(ctx)
    with store.transaction(ctx.conn):
        for n, c in enumerate(claims, start=1):
            store.insert_claim(ctx.conn, dataclasses.replace(
                c, id=claim_id(ctx.run.id, n), run_id=ctx.run.id, state=ClaimState.PENDING))
        store.set_run_state(ctx.conn, ctx.run.id, RunState.EXTRACTED)
    log_step(ctx.run.id, None, "extract", "ok", claims=len(claims))


def _resolve(ctx: RunContext, stages: Stages | None) -> None:
    claims = store.list_claims(ctx.conn, ctx.run.id)
    entities = _stage(stages, "resolve")(ctx, claims)
    with store.transaction(ctx.conn):
        store.save_resolution(ctx.conn, ctx.run.id, entities)
        store.set_run_state(ctx.conn, ctx.run.id, RunState.RESOLVED)
    log_step(ctx.run.id, None, "resolve", "ok")


def _held(reason: HeldReason, detail: str) -> CheckResult:
    return CheckResult(observed={"held_detail": detail}, comparable=False,
                       held_reason=reason.value)


def _check_one(ctx: RunContext, claim: Claim, stages: Stages | None) -> CheckResult:
    """Run one checker. Never raises for source trouble: limits, timeouts, errors -> HELD."""
    hit = limit_reason(ctx.conn, ctx.rules, ctx.run.id, ctx.run.started_at)
    if hit is not None:
        return _held(*hit)
    try:
        result = _stage(stages, "check")(claim, ctx)
    except LimitExceeded as e:
        return _held(e.reason, e.detail)
    except TimeoutError as e:
        return _held(HeldReason.TIMEOUT, str(e) or "call timed out")
    except StageMissing as e:
        return _held(HeldReason.NO_CHECKER, str(e))
    except Exception as e:  # a source or checker failure must not stop the other claims
        log_error(ctx.run.id, claim.id, f"check.{claim.type.value}", repr(e))
        return _held(HeldReason.ERROR, repr(e)[:300])
    for ev in result.evidence:
        if ev.claim_id != claim.id:
            raise ValueError(f"checker returned evidence for {ev.claim_id}, not {claim.id}")
    return result


def _check_and_decide(ctx: RunContext, stages: Stages | None) -> None:
    store.set_run_state(ctx.conn, ctx.run.id, RunState.CHECKING)
    for claim in store.list_claims(ctx.conn, ctx.run.id):
        if claim.state is ClaimState.PENDING:
            result = _check_one(ctx, claim, stages)
            store.save_check_result(ctx.conn, claim.id, result)
            log_step(ctx.run.id, claim.id, f"check.{claim.type.value}",
                     result.held_reason and f"held:{result.held_reason}" or "ok",
                     evidence=len(result.evidence))
            claim.state = ClaimState.CHECKED
        if claim.state is ClaimState.CHECKED:
            result = store.get_check_result(ctx.conn, claim.id)
            verdict = _stage(stages, "decide")(claim, result, ctx.rules)
            store.save_verdict(ctx.conn, verdict)
            log_step(ctx.run.id, claim.id, "decide", verdict.label.value,
                     reason=verdict.reason_code)
    store.set_run_state(ctx.conn, ctx.run.id, RunState.DECIDED)


def _report(ctx: RunContext, stages: Stages | None) -> None:
    report_json, report_md = _stage(stages, "report")(ctx.conn, ctx.rules, ctx.run.id)
    with store.transaction(ctx.conn):
        store.save_report(ctx.conn, ctx.run.id, report_json, report_md)
        store.set_run_state(ctx.conn, ctx.run.id, RunState.REPORTED)
    log_step(ctx.run.id, None, "report", "ok")


def _draft(ctx: RunContext, stages: Stages | None) -> None:
    _stage(stages, "draft")(ctx.conn, ctx.rules, ctx.run.id)   # idempotent: UNIQUE key
    store.set_run_state(ctx.conn, ctx.run.id, RunState.DONE)
    log_step(ctx.run.id, None, "draft", "ok", note="founder email pending approval")


STEPS: dict[RunState, Callable[[RunContext, Stages | None], None]] = {
    RunState.CREATED: _extract,
    RunState.EXTRACTED: _resolve,
    RunState.RESOLVED: _check_and_decide,
    RunState.CHECKING: _check_and_decide,     # resume mid-check: finished claims are skipped
    RunState.DECIDED: _report,
    RunState.REPORTED: _draft,
}


def _drive(conn: sqlite3.Connection, rules: dict[str, Any], run_id: str,
           stages: Stages | None) -> bool:
    """Run every remaining step. Returns True when the run reaches DONE."""
    while True:
        run = store.get_run(conn, run_id)
        if run is None:
            raise ValueError(f"no run with id {run_id}")
        if run.state is RunState.DONE:
            log_step(run_id, None, "runner", "done")
            return True
        step = STEPS.get(run.state)
        if step is None:
            log_error(run_id, None, "runner", f"cannot continue from state {run.state.value}")
            return False
        ctx = RunContext(conn, rules, run, store.get_resolution(conn, run_id) or {})
        try:
            step(ctx, stages)
        except StageMissing as e:
            store.set_run_state(conn, run_id, run.state, error=str(e))
            log_step(run_id, None, f"runner.{run.state.value}", "waiting", error=str(e))
            return False
        except Exception as e:
            store.set_run_state(conn, run_id, run.state, error=repr(e)[:300])
            log_error(run_id, None, f"runner.{run.state.value}", repr(e))
            return False


def start(conn: sqlite3.Connection, rules: dict[str, Any], run_id: str,
          stages: Stages | None = None) -> bool:
    """Run a new run from the beginning. Returns True when it reaches DONE."""
    store.mark_run_started(conn, run_id)
    log_step(run_id, None, "runner.start", "ok")
    return _drive(conn, rules, run_id, stages)


def resume(conn: sqlite3.Connection, rules: dict[str, Any], run_id: str,
           stages: Stages | None = None) -> bool:
    """Continue after a kill: every step and claim already checkpointed is skipped."""
    run = store.get_run(conn, run_id)
    if run is None:
        raise ValueError(f"no run with id {run_id}")
    store.mark_run_started(conn, run_id)   # no-op if it already started: max_seconds holds
    log_step(run_id, None, "runner.resume", "ok", state=run.state.value)
    return _drive(conn, rules, run_id, stages)
