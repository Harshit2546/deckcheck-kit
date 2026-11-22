"""SQLite storage for DeckCheck: schema, first-use table creation and small helpers for every table.

Who calls it: the runner, every lane that reads or writes a checkpoint, actions/ (send), ui/ (read only).
What it calls: sqlite3 and core.models only. The DB schema here is a contract (DECISIONS.md before changing).
Tables: runs, claims, check_results, evidence, verdicts, ledger (append-only), actions, inbox.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from core.models import (
    Action,
    ActionStatus,
    Claim,
    ClaimState,
    CheckResult,
    Evidence,
    InboxMessage,
    LedgerEntry,
    Run,
    RunState,
    Verdict,
    utcnow,
)

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id               TEXT PRIMARY KEY,
    deck_path        TEXT NOT NULL,
    company_domain   TEXT NOT NULL,
    deck_date        TEXT,
    deck_date_source TEXT NOT NULL,
    founder_urls     TEXT NOT NULL,            -- JSON list
    state            TEXT NOT NULL,
    resolved_json    TEXT,                     -- resolve lane output (professional fields only)
    active_seconds   REAL NOT NULL DEFAULT 0,  -- working time summed across resumes
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    id        TEXT PRIMARY KEY,
    run_id    TEXT NOT NULL REFERENCES runs(id),
    slide     INTEGER NOT NULL,
    quote     TEXT NOT NULL,
    type      TEXT NOT NULL,
    subject   TEXT NOT NULL,
    metric    TEXT,
    value     TEXT,                            -- JSON (keeps number vs text)
    unit      TEXT,
    as_of     TEXT,
    state     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_run ON claims(run_id);

-- What a checker returned besides evidence rows; lets a resume go checked -> decided with no new call.
CREATE TABLE IF NOT EXISTS check_results (
    claim_id     TEXT PRIMARY KEY REFERENCES claims(id),
    observed     TEXT NOT NULL,                -- JSON
    comparable   INTEGER NOT NULL,
    held_reason  TEXT,
    evidence_ids TEXT NOT NULL                 -- JSON list, in checker order
);

CREATE TABLE IF NOT EXISTS evidence (
    id             TEXT PRIMARY KEY,
    claim_id       TEXT NOT NULL REFERENCES claims(id),
    source_type    TEXT NOT NULL,
    locator        TEXT NOT NULL,
    field_or_quote TEXT NOT NULL,
    value          TEXT,                       -- JSON
    record_date    TEXT,
    retrieved_at   TEXT NOT NULL,
    call_id        TEXT
);
CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence(claim_id);

CREATE TABLE IF NOT EXISTS verdicts (
    claim_id     TEXT PRIMARY KEY REFERENCES claims(id),
    label        TEXT NOT NULL,
    reason_code  TEXT NOT NULL,
    explanation  TEXT NOT NULL,
    evidence_ids TEXT NOT NULL,                -- JSON list
    confidence   TEXT NOT NULL,
    missing      TEXT,
    decided_at   TEXT NOT NULL
);

-- Append-only: the triggers below make editing or deleting a ledger row impossible.
CREATE TABLE IF NOT EXISTS ledger (
    id                TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL,
    provider          TEXT NOT NULL,
    endpoint_or_model TEXT NOT NULL,
    credits           REAL NOT NULL,
    tokens_in         INTEGER NOT NULL,
    tokens_out        INTEGER NOT NULL,
    cost_inr          REAL NOT NULL,
    duration_ms       INTEGER NOT NULL,
    ok                INTEGER NOT NULL,
    error             TEXT,
    ts                TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ledger_run ON ledger(run_id);
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger
BEGIN SELECT RAISE(ABORT, 'ledger rows are append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger
BEGIN SELECT RAISE(ABORT, 'ledger rows are append-only'); END;

CREATE TABLE IF NOT EXISTS actions (
    id               TEXT PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES runs(id),
    type             TEXT NOT NULL,
    idempotency_key  TEXT NOT NULL UNIQUE,
    recipient        TEXT NOT NULL,
    subject          TEXT NOT NULL,
    body             TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('pending','approved','rejected','sending','sent')),
    decided_by       TEXT,
    decided_at       TEXT,
    sent_at          TEXT
);

-- The team's test inbox. UNIQUE(idempotency_key) is what makes a second send impossible.
CREATE TABLE IF NOT EXISTS inbox (
    id               TEXT PRIMARY KEY,
    idempotency_key  TEXT NOT NULL UNIQUE,
    action_id        TEXT NOT NULL REFERENCES actions(id),
    run_id           TEXT NOT NULL,
    recipient        TEXT NOT NULL,
    subject          TEXT NOT NULL,
    body             TEXT NOT NULL,
    received_at      TEXT NOT NULL
);
"""


def _ts(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _j(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


class Store:
    """One SQLite connection. Tables are created on first use. Use `transaction()` for multi-row changes."""

    def __init__(self, path: str | Path = "data/deckcheck.db") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None: we issue BEGIN/COMMIT ourselves in transaction(); reads autocommit.
        self.conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(_SCHEMA)
        self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._depth = 0

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """BEGIN IMMEDIATE ... COMMIT (ROLLBACK on error). Nested use joins the outer transaction."""
        if self._depth > 0:
            self._depth += 1
            try:
                yield self.conn
            finally:
                self._depth -= 1
            return
        self.conn.execute("BEGIN IMMEDIATE")
        self._depth = 1
        try:
            yield self.conn
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")
        finally:
            self._depth = 0

    def table_names(self) -> list[str]:
        rows = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        return [r["name"] for r in rows]

    # ------------------------------------------------------------------ runs

    def create_run(self, run: Run) -> Run:
        with self.transaction() as c:
            c.execute(
                "INSERT INTO runs (id, deck_path, company_domain, deck_date, deck_date_source, founder_urls,"
                " state, resolved_json, active_seconds, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run.id, run.deck_path, run.company_domain, run.deck_date, run.deck_date_source,
                    _j(run.founder_urls), run.state.value,
                    _j(run.resolved) if run.resolved is not None else None,
                    run.active_seconds, _ts(run.created_at), _ts(run.updated_at),
                ),
            )
        return run

    def get_run(self, run_id: str) -> Run | None:
        row = self.conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return Run(
            id=row["id"], deck_path=row["deck_path"], company_domain=row["company_domain"],
            deck_date=row["deck_date"], deck_date_source=row["deck_date_source"],
            founder_urls=json.loads(row["founder_urls"]), state=RunState(row["state"]),
            resolved=json.loads(row["resolved_json"]) if row["resolved_json"] else None,
            active_seconds=row["active_seconds"],
            created_at=_dt(row["created_at"]), updated_at=_dt(row["updated_at"]),
        )

    def list_runs(self) -> list[Run]:
        ids = [r["id"] for r in self.conn.execute("SELECT id FROM runs ORDER BY created_at DESC, id")]
        return [r for r in (self.get_run(i) for i in ids) if r is not None]

    def set_run_state(self, run_id: str, state: RunState) -> None:
        with self.transaction() as c:
            c.execute("UPDATE runs SET state = ?, updated_at = ? WHERE id = ?", (state.value, _ts(utcnow()), run_id))

    def set_run_resolved(self, run_id: str, resolved: dict[str, Any]) -> None:
        with self.transaction() as c:
            c.execute(
                "UPDATE runs SET resolved_json = ?, updated_at = ? WHERE id = ?", (_j(resolved), _ts(utcnow()), run_id)
            )

    def set_run_deck_date(self, run_id: str, deck_date: str, source: str) -> None:
        with self.transaction() as c:
            c.execute(
                "UPDATE runs SET deck_date = ?, deck_date_source = ?, updated_at = ? WHERE id = ?",
                (deck_date, source, _ts(utcnow()), run_id),
            )

    def add_active_seconds(self, run_id: str, seconds: float) -> float:
        """Add working time to the run and return the new total (the runner compares it with max_seconds)."""
        with self.transaction() as c:
            c.execute(
                "UPDATE runs SET active_seconds = active_seconds + ?, updated_at = ? WHERE id = ?",
                (seconds, _ts(utcnow()), run_id),
            )
            row = c.execute("SELECT active_seconds FROM runs WHERE id = ?", (run_id,)).fetchone()
        return float(row["active_seconds"])

    # ------------------------------------------------------------------ claims

    @staticmethod
    def _claim_from_row(row: sqlite3.Row) -> Claim:
        return Claim(
            id=row["id"], run_id=row["run_id"], slide=row["slide"], quote=row["quote"], type=row["type"],
            subject=row["subject"], metric=row["metric"],
            value=json.loads(row["value"]) if row["value"] is not None else None,
            unit=row["unit"], as_of=row["as_of"], state=ClaimState(row["state"]),
        )

    def add_claims(self, claims: list[Claim]) -> None:
        """Insert claims in one transaction. A claim id that already exists is left untouched (safe on resume)."""
        with self.transaction() as c:
            for cl in claims:
                c.execute(
                    "INSERT OR IGNORE INTO claims (id, run_id, slide, quote, type, subject, metric, value, unit,"
                    " as_of, state) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        cl.id, cl.run_id, cl.slide, cl.quote, cl.type.value, cl.subject, cl.metric,
                        _j(cl.value) if cl.value is not None else None, cl.unit, cl.as_of, cl.state.value,
                    ),
                )

    def get_claim(self, claim_id: str) -> Claim | None:
        row = self.conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        return self._claim_from_row(row) if row else None

    def list_claims(self, run_id: str, state: ClaimState | None = None) -> list[Claim]:
        sql, args = "SELECT * FROM claims WHERE run_id = ?", [run_id]
        if state is not None:
            sql, args = sql + " AND state = ?", args + [state.value]
        rows = self.conn.execute(sql + " ORDER BY slide, rowid", args).fetchall()
        return [self._claim_from_row(r) for r in rows]

    def set_claim_state(self, claim_id: str, state: ClaimState) -> None:
        with self.transaction() as c:
            c.execute("UPDATE claims SET state = ? WHERE id = ?", (state.value, claim_id))

    # ------------------------------------------------------------------ check results and evidence

    def save_check_result(self, claim_id: str, result: CheckResult) -> None:
        """Checkpoint a finished check: evidence + check_results row + claim state 'checked', all or nothing."""
        with self.transaction() as c:
            for ev in result.evidence:
                if ev.claim_id != claim_id:
                    raise ValueError(f"evidence {ev.id} belongs to claim {ev.claim_id}, not {claim_id}")
                c.execute(
                    "INSERT OR REPLACE INTO evidence (id, claim_id, source_type, locator, field_or_quote, value,"
                    " record_date, retrieved_at, call_id) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        ev.id, claim_id, ev.source_type.value, ev.locator, ev.field_or_quote, _j(ev.value),
                        ev.record_date, _ts(ev.retrieved_at), ev.call_id,
                    ),
                )
            c.execute(
                "INSERT OR REPLACE INTO check_results (claim_id, observed, comparable, held_reason, evidence_ids)"
                " VALUES (?,?,?,?,?)",
                (claim_id, _j(result.observed), int(result.comparable), result.held_reason,
                 _j([e.id for e in result.evidence])),
            )
            c.execute("UPDATE claims SET state = ? WHERE id = ?", (ClaimState.CHECKED.value, claim_id))

    def get_check_result(self, claim_id: str) -> CheckResult | None:
        row = self.conn.execute("SELECT * FROM check_results WHERE claim_id = ?", (claim_id,)).fetchone()
        if row is None:
            return None
        by_id = {e.id: e for e in self.list_evidence(claim_id)}
        ordered = [by_id[i] for i in json.loads(row["evidence_ids"]) if i in by_id]
        return CheckResult(
            evidence=ordered, observed=json.loads(row["observed"]), comparable=bool(row["comparable"]),
            held_reason=row["held_reason"],
        )

    @staticmethod
    def _evidence_from_row(row: sqlite3.Row) -> Evidence:
        return Evidence(
            id=row["id"], claim_id=row["claim_id"], source_type=row["source_type"], locator=row["locator"],
            field_or_quote=row["field_or_quote"], value=json.loads(row["value"]) if row["value"] else None,
            record_date=row["record_date"], retrieved_at=_dt(row["retrieved_at"]), call_id=row["call_id"],
        )

    def list_evidence(self, claim_id: str) -> list[Evidence]:
        rows = self.conn.execute("SELECT * FROM evidence WHERE claim_id = ? ORDER BY rowid", (claim_id,)).fetchall()
        return [self._evidence_from_row(r) for r in rows]

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        row = self.conn.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
        return self._evidence_from_row(row) if row else None

    # ------------------------------------------------------------------ verdicts

    def save_verdict(self, verdict: Verdict) -> None:
        """Checkpoint a verdict and move the claim to 'decided' in one transaction (one verdict per claim)."""
        with self.transaction() as c:
            c.execute(
                "INSERT OR REPLACE INTO verdicts (claim_id, label, reason_code, explanation, evidence_ids,"
                " confidence, missing, decided_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    verdict.claim_id, verdict.label.value, verdict.reason_code, verdict.explanation,
                    _j(verdict.evidence_ids), verdict.confidence.value, verdict.missing, _ts(utcnow()),
                ),
            )
            c.execute("UPDATE claims SET state = ? WHERE id = ?", (ClaimState.DECIDED.value, verdict.claim_id))

    def get_verdict(self, claim_id: str) -> Verdict | None:
        row = self.conn.execute("SELECT * FROM verdicts WHERE claim_id = ?", (claim_id,)).fetchone()
        if row is None:
            return None
        return Verdict(
            claim_id=row["claim_id"], label=row["label"], reason_code=row["reason_code"],
            explanation=row["explanation"], evidence_ids=json.loads(row["evidence_ids"]),
            confidence=row["confidence"], missing=row["missing"],
        )

    def list_verdicts(self, run_id: str) -> list[Verdict]:
        rows = self.conn.execute(
            "SELECT v.claim_id FROM verdicts v JOIN claims c ON c.id = v.claim_id WHERE c.run_id = ?"
            " ORDER BY c.slide, c.rowid", (run_id,),
        ).fetchall()
        return [v for v in (self.get_verdict(r["claim_id"]) for r in rows) if v is not None]

    # ------------------------------------------------------------------ ledger (append-only)

    def add_ledger(self, entry: LedgerEntry) -> LedgerEntry:
        """Write one ledger row. Call this for EVERY external call, including failed ones."""
        with self.transaction() as c:
            c.execute(
                "INSERT INTO ledger (id, run_id, provider, endpoint_or_model, credits, tokens_in, tokens_out,"
                " cost_inr, duration_ms, ok, error, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    entry.id, entry.run_id, entry.provider.value, entry.endpoint_or_model, entry.credits,
                    entry.tokens_in, entry.tokens_out, entry.cost_inr, entry.duration_ms, int(entry.ok),
                    entry.error, _ts(entry.ts),
                ),
            )
        return entry

    def list_ledger(self, run_id: str) -> list[LedgerEntry]:
        rows = self.conn.execute("SELECT * FROM ledger WHERE run_id = ? ORDER BY ts, rowid", (run_id,)).fetchall()
        return [
            LedgerEntry(
                id=r["id"], run_id=r["run_id"], provider=r["provider"], endpoint_or_model=r["endpoint_or_model"],
                credits=r["credits"], tokens_in=r["tokens_in"], tokens_out=r["tokens_out"], cost_inr=r["cost_inr"],
                duration_ms=r["duration_ms"], ok=bool(r["ok"]), error=r["error"], ts=_dt(r["ts"]),
            )
            for r in rows
        ]

    def ledger_totals(self, run_id: str) -> dict[str, float]:
        """Totals the runner compares with config limits before every external call."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(cost_inr),0) AS cost_inr, COALESCE(SUM(credits),0) AS credits,"
            " COALESCE(SUM(duration_ms),0) AS duration_ms, COUNT(*) AS calls FROM ledger WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return {k: float(row[k]) for k in ("cost_inr", "credits", "duration_ms", "calls")}

    # ------------------------------------------------------------------ actions and inbox

    @staticmethod
    def _action_from_row(row: sqlite3.Row) -> Action:
        return Action(
            id=row["id"], run_id=row["run_id"], type=row["type"], idempotency_key=row["idempotency_key"],
            recipient=row["recipient"], subject=row["subject"], body=row["body"],
            status=ActionStatus(row["status"]), decided_by=row["decided_by"],
            decided_at=_dt(row["decided_at"]), sent_at=_dt(row["sent_at"]),
        )

    def create_action(self, action: Action) -> Action:
        """Insert an action. If the idempotency key already exists, return the existing row (no duplicate draft)."""
        with self.transaction() as c:
            c.execute(
                "INSERT OR IGNORE INTO actions (id, run_id, type, idempotency_key, recipient, subject, body,"
                " status, decided_by, decided_at, sent_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    action.id, action.run_id, action.type.value, action.idempotency_key, action.recipient,
                    action.subject, action.body, action.status.value, action.decided_by,
                    _ts(action.decided_at), _ts(action.sent_at),
                ),
            )
        existing = self.get_action_by_key(action.idempotency_key)
        assert existing is not None
        return existing

    def get_action(self, action_id: str) -> Action | None:
        row = self.conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
        return self._action_from_row(row) if row else None

    def get_action_by_key(self, idempotency_key: str) -> Action | None:
        row = self.conn.execute("SELECT * FROM actions WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
        return self._action_from_row(row) if row else None

    def list_actions(self, run_id: str | None = None, status: ActionStatus | None = None) -> list[Action]:
        sql, args, where = "SELECT * FROM actions", [], []
        if run_id is not None:
            where.append("run_id = ?")
            args.append(run_id)
        if status is not None:
            where.append("status = ?")
            args.append(status.value)
        if where:
            sql += " WHERE " + " AND ".join(where)
        rows = self.conn.execute(sql + " ORDER BY rowid", args).fetchall()
        return [self._action_from_row(r) for r in rows]

    def list_inbox(self, run_id: str | None = None) -> list[InboxMessage]:
        sql, args = "SELECT * FROM inbox", []
        if run_id is not None:
            sql, args = sql + " WHERE run_id = ?", [run_id]
        rows = self.conn.execute(sql + " ORDER BY rowid", args).fetchall()
        return [
            InboxMessage(
                id=r["id"], idempotency_key=r["idempotency_key"], action_id=r["action_id"], run_id=r["run_id"],
                recipient=r["recipient"], subject=r["subject"], body=r["body"], received_at=_dt(r["received_at"]),
            )
            for r in rows
        ]
