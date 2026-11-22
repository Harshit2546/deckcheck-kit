"""SQLite store: the DB schema (a contract) and every read/write of runs, claims, evidence,
check results, verdicts, ledger, actions, inbox and reports.

Called by: cli.py, core/runner.py, core/ledger.py, actions/, ui/app.py, tests.
Calls: sqlite3, core/models.py. Ledger and inbox rows are append-only (DB triggers refuse
UPDATE/DELETE). Change the schema only after a DECISIONS.md entry.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from core.models import (
    Action, ActionStatus, ActionType, CheckResult, Claim, ClaimState, ClaimType, Confidence,
    Evidence, InboxMessage, LedgerEntry, Provider, Run, RunInput, RunState, SourceType,
    Verdict, VerdictLabel, now_iso,
)

DEFAULT_DB = "deckcheck.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    deck_path TEXT NOT NULL,
    domain TEXT NOT NULL,
    deck_date TEXT,
    deck_date_source TEXT NOT NULL,
    founder_urls TEXT NOT NULL,              -- JSON list
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    slide INTEGER NOT NULL,
    quote TEXT NOT NULL,
    type TEXT NOT NULL,
    subject TEXT NOT NULL,
    metric TEXT,
    value TEXT,                              -- JSON so 120 stays a number and "120+" a string
    unit TEXT,
    as_of TEXT,
    state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    provider TEXT NOT NULL,
    endpoint_or_model TEXT NOT NULL,
    credits REAL NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    cost_inr REAL NOT NULL,
    duration_ms INTEGER NOT NULL,
    ok INTEGER NOT NULL,
    error TEXT,
    ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claims(id),
    source_type TEXT NOT NULL,
    locator TEXT NOT NULL,
    field_or_quote TEXT NOT NULL,
    value TEXT,                              -- JSON
    record_date TEXT,
    retrieved_at TEXT NOT NULL,
    call_id TEXT REFERENCES ledger(id)
);
CREATE TABLE IF NOT EXISTS check_results (
    claim_id TEXT PRIMARY KEY REFERENCES claims(id),
    observed TEXT NOT NULL,                  -- JSON dict
    comparable INTEGER NOT NULL,
    held_reason TEXT,
    checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verdicts (
    claim_id TEXT PRIMARY KEY REFERENCES claims(id),
    label TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    explanation TEXT NOT NULL,
    evidence_ids TEXT NOT NULL,              -- JSON list
    confidence TEXT NOT NULL,
    missing TEXT,
    decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    type TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT,
    sent_at TEXT
);
CREATE TABLE IF NOT EXISTS inbox (
    idempotency_key TEXT NOT NULL UNIQUE,
    action_id TEXT NOT NULL REFERENCES actions(id),
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    run_id TEXT PRIMARY KEY REFERENCES runs(id),
    report_json TEXT NOT NULL,
    report_md TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_run ON claims(run_id);
CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_ledger_run ON ledger(run_id);
CREATE INDEX IF NOT EXISTS idx_actions_run ON actions(run_id);
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger
    BEGIN SELECT RAISE(ABORT, 'ledger rows are append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger
    BEGIN SELECT RAISE(ABORT, 'ledger rows are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inbox_no_update BEFORE UPDATE ON inbox
    BEGIN SELECT RAISE(ABORT, 'inbox rows are append-only'); END;
CREATE TRIGGER IF NOT EXISTS inbox_no_delete BEFORE DELETE ON inbox
    BEGIN SELECT RAISE(ABORT, 'inbox rows are append-only'); END;
"""

TABLES = ["runs", "claims", "ledger", "evidence", "check_results", "verdicts", "actions",
          "inbox", "reports"]


# ---------- connection ----------

def connect(path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    """Open the DB in autocommit mode (use transaction() to group writes) and create tables."""
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create every table, index and trigger if missing. Safe to call on every start."""
    conn.executescript(SCHEMA)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """All writes inside commit together or not at all. Re-entrant: nested use joins the outer one."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def _dump(value: Any) -> str | None:
    return None if value is None else json.dumps(value)


def _load(text: str | None) -> Any:
    return None if text is None else json.loads(text)


# ---------- runs ----------

def insert_run(conn: sqlite3.Connection, run: Run) -> None:
    i = run.input
    conn.execute(
        "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (run.id, i.deck_path, i.domain, i.deck_date, i.deck_date_source,
         json.dumps(i.founder_urls), run.state.value, run.created_at, run.updated_at,
         run.started_at, run.error),
    )


def _run(row: sqlite3.Row) -> Run:
    return Run(
        id=row["id"],
        input=RunInput(row["deck_path"], row["domain"], row["deck_date"],
                       row["deck_date_source"], json.loads(row["founder_urls"])),
        state=RunState(row["state"]), created_at=row["created_at"],
        updated_at=row["updated_at"], started_at=row["started_at"], error=row["error"],
    )


def get_run(conn: sqlite3.Connection, run_id: str) -> Run | None:
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return _run(row) if row else None


def list_runs(conn: sqlite3.Connection) -> list[Run]:
    rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
    return [_run(r) for r in rows]


def set_run_state(conn: sqlite3.Connection, run_id: str, state: RunState,
                  error: str | None = None) -> None:
    conn.execute("UPDATE runs SET state = ?, error = ?, updated_at = ? WHERE id = ?",
                 (state.value, error, now_iso(), run_id))


def update_run_input(conn: sqlite3.Connection, run_id: str, deck_date: str | None,
                     deck_date_source: str) -> None:
    """Used by extract when the deck date falls back to PDF metadata."""
    conn.execute("UPDATE runs SET deck_date = ?, deck_date_source = ?, updated_at = ? "
                 "WHERE id = ?", (deck_date, deck_date_source, now_iso(), run_id))


def mark_run_started(conn: sqlite3.Connection, run_id: str) -> None:
    """Set started_at once; a resume keeps the original start so max_seconds still holds."""
    conn.execute("UPDATE runs SET started_at = COALESCE(started_at, ?) WHERE id = ?",
                 (now_iso(), run_id))


# ---------- claims ----------

def insert_claim(conn: sqlite3.Connection, claim: Claim) -> None:
    conn.execute(
        "INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (claim.id, claim.run_id, claim.slide, claim.quote, claim.type.value, claim.subject,
         claim.metric, _dump(claim.value), claim.unit, claim.as_of, claim.state.value),
    )


def _claim(row: sqlite3.Row) -> Claim:
    return Claim(
        id=row["id"], run_id=row["run_id"], slide=row["slide"], quote=row["quote"],
        type=ClaimType(row["type"]), subject=row["subject"], metric=row["metric"],
        value=_load(row["value"]), unit=row["unit"], as_of=row["as_of"],
        state=ClaimState(row["state"]),
    )


def get_claim(conn: sqlite3.Connection, claim_id: str) -> Claim | None:
    row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    return _claim(row) if row else None


def list_claims(conn: sqlite3.Connection, run_id: str,
                state: ClaimState | None = None) -> list[Claim]:
    sql, args = "SELECT * FROM claims WHERE run_id = ?", [run_id]
    if state is not None:
        sql, args = sql + " AND state = ?", args + [state.value]
    rows = conn.execute(sql + " ORDER BY slide, id", args).fetchall()
    return [_claim(r) for r in rows]


def set_claim_state(conn: sqlite3.Connection, claim_id: str, state: ClaimState) -> None:
    conn.execute("UPDATE claims SET state = ? WHERE id = ?", (state.value, claim_id))


# ---------- evidence and check results ----------

def insert_evidence(conn: sqlite3.Connection, ev: Evidence) -> None:
    conn.execute(
        "INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?)",
        (ev.id, ev.claim_id, ev.source_type.value, ev.locator, ev.field_or_quote,
         _dump(ev.value), ev.record_date, ev.retrieved_at, ev.call_id),
    )


def _evidence(row: sqlite3.Row) -> Evidence:
    return Evidence(
        id=row["id"], claim_id=row["claim_id"], source_type=SourceType(row["source_type"]),
        locator=row["locator"], field_or_quote=row["field_or_quote"],
        value=_load(row["value"]), record_date=row["record_date"],
        retrieved_at=row["retrieved_at"], call_id=row["call_id"],
    )


def list_evidence(conn: sqlite3.Connection, claim_id: str) -> list[Evidence]:
    rows = conn.execute("SELECT * FROM evidence WHERE claim_id = ? ORDER BY id",
                        (claim_id,)).fetchall()
    return [_evidence(r) for r in rows]


def save_check_result(conn: sqlite3.Connection, claim_id: str, result: CheckResult) -> None:
    """Checkpoint one claim's check: evidence + result + claim state 'checked', atomically."""
    with transaction(conn):
        for ev in result.evidence:
            insert_evidence(conn, ev)
        conn.execute("INSERT INTO check_results VALUES (?,?,?,?,?)",
                     (claim_id, json.dumps(result.observed), int(result.comparable),
                      result.held_reason, now_iso()))
        set_claim_state(conn, claim_id, ClaimState.CHECKED)


def get_check_result(conn: sqlite3.Connection, claim_id: str) -> CheckResult | None:
    row = conn.execute("SELECT * FROM check_results WHERE claim_id = ?",
                       (claim_id,)).fetchone()
    if row is None:
        return None
    return CheckResult(evidence=list_evidence(conn, claim_id),
                       observed=json.loads(row["observed"]),
                       comparable=bool(row["comparable"]), held_reason=row["held_reason"])


# ---------- verdicts ----------

def save_verdict(conn: sqlite3.Connection, v: Verdict) -> None:
    """Checkpoint one claim's verdict and mark the claim 'decided', atomically."""
    with transaction(conn):
        conn.execute(
            "INSERT INTO verdicts VALUES (?,?,?,?,?,?,?,?)",
            (v.claim_id, v.label.value, v.reason_code, v.explanation,
             json.dumps(v.evidence_ids), v.confidence.value, v.missing, now_iso()),
        )
        set_claim_state(conn, v.claim_id, ClaimState.DECIDED)


def _verdict(row: sqlite3.Row) -> Verdict:
    return Verdict(
        claim_id=row["claim_id"], label=VerdictLabel(row["label"]),
        reason_code=row["reason_code"], explanation=row["explanation"],
        evidence_ids=json.loads(row["evidence_ids"]),
        confidence=Confidence(row["confidence"]), missing=row["missing"],
    )


def get_verdict(conn: sqlite3.Connection, claim_id: str) -> Verdict | None:
    row = conn.execute("SELECT * FROM verdicts WHERE claim_id = ?", (claim_id,)).fetchone()
    return _verdict(row) if row else None


def list_verdicts(conn: sqlite3.Connection, run_id: str) -> list[Verdict]:
    rows = conn.execute(
        "SELECT v.* FROM verdicts v JOIN claims c ON c.id = v.claim_id "
        "WHERE c.run_id = ? ORDER BY c.slide, c.id", (run_id,)).fetchall()
    return [_verdict(r) for r in rows]


# ---------- ledger ----------

def insert_ledger(conn: sqlite3.Connection, e: LedgerEntry) -> None:
    conn.execute(
        "INSERT INTO ledger VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (e.id, e.run_id, e.provider.value, e.endpoint_or_model, e.credits, e.tokens_in,
         e.tokens_out, e.cost_inr, e.duration_ms, int(e.ok), e.error, e.ts),
    )


def list_ledger(conn: sqlite3.Connection, run_id: str) -> list[LedgerEntry]:
    rows = conn.execute("SELECT * FROM ledger WHERE run_id = ? ORDER BY ts, id",
                        (run_id,)).fetchall()
    return [LedgerEntry(
        id=r["id"], run_id=r["run_id"], provider=Provider(r["provider"]),
        endpoint_or_model=r["endpoint_or_model"], credits=r["credits"],
        tokens_in=r["tokens_in"], tokens_out=r["tokens_out"], cost_inr=r["cost_inr"],
        duration_ms=r["duration_ms"], ok=bool(r["ok"]), error=r["error"], ts=r["ts"],
    ) for r in rows]


def ledger_totals(conn: sqlite3.Connection, run_id: str) -> dict[str, float]:
    """Spend so far for one run: cost_inr, credits, calls, failed. The runner checks this
    against config limits before every external call."""
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_inr),0) AS cost_inr, COALESCE(SUM(credits),0) AS credits, "
        "COUNT(*) AS calls, COALESCE(SUM(1-ok),0) AS failed FROM ledger WHERE run_id = ?",
        (run_id,)).fetchone()
    return {k: row[k] for k in ("cost_inr", "credits", "calls", "failed")}


# ---------- actions and inbox ----------

def insert_action(conn: sqlite3.Connection, a: Action) -> Action:
    """Insert unless an action with the same idempotency key exists; return the stored one."""
    conn.execute(
        "INSERT OR IGNORE INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (a.id, a.run_id, a.type.value, a.idempotency_key, a.recipient, a.subject, a.body,
         a.status.value, a.decided_by, a.decided_at, a.sent_at),
    )
    row = conn.execute("SELECT * FROM actions WHERE idempotency_key = ?",
                       (a.idempotency_key,)).fetchone()
    return _action(row)


def _action(row: sqlite3.Row) -> Action:
    return Action(
        id=row["id"], run_id=row["run_id"], type=ActionType(row["type"]),
        idempotency_key=row["idempotency_key"], recipient=row["recipient"],
        subject=row["subject"], body=row["body"], status=ActionStatus(row["status"]),
        decided_by=row["decided_by"], decided_at=row["decided_at"], sent_at=row["sent_at"],
    )


def get_action(conn: sqlite3.Connection, action_id: str) -> Action | None:
    row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    return _action(row) if row else None


def list_actions(conn: sqlite3.Connection, run_id: str | None = None,
                 status: ActionStatus | None = None) -> list[Action]:
    sql, args = "SELECT * FROM actions WHERE 1=1", []
    if run_id is not None:
        sql, args = sql + " AND run_id = ?", args + [run_id]
    if status is not None:
        sql, args = sql + " AND status = ?", args + [status.value]
    return [_action(r) for r in conn.execute(sql + " ORDER BY id", args).fetchall()]


def list_inbox(conn: sqlite3.Connection) -> list[InboxMessage]:
    rows = conn.execute("SELECT * FROM inbox ORDER BY received_at").fetchall()
    return [InboxMessage(r["idempotency_key"], r["action_id"], r["recipient"], r["subject"],
                         r["body"], r["received_at"]) for r in rows]


# ---------- reports ----------

def save_report(conn: sqlite3.Connection, run_id: str, report_json: dict[str, Any],
                report_md: str) -> None:
    conn.execute("INSERT OR REPLACE INTO reports VALUES (?,?,?,?)",
                 (run_id, json.dumps(report_json), report_md, now_iso()))


def get_report(conn: sqlite3.Connection, run_id: str) -> tuple[dict[str, Any], str] | None:
    row = conn.execute("SELECT * FROM reports WHERE run_id = ?", (run_id,)).fetchone()
    return (json.loads(row["report_json"]), row["report_md"]) if row else None
