"""T01 tests: tables exist, rows round-trip, ledger/inbox are append-only, keys are unique.

Called by: pytest. Calls: core/store.py, core/ledger.py, core/models.py.
"""

import sqlite3

import pytest

from core import ledger, store
from core.models import (Action, ActionType, CheckResult, Claim, ClaimState, ClaimType,
                         Confidence, Evidence, InboxMessage, Provider, Run, RunInput,
                         SourceType, Verdict, VerdictLabel, make_idempotency_key, now_iso)


def _run(conn) -> Run:
    run = Run(id="run-1", input=RunInput("deck.pdf", "example.com", "2026-10-01"))
    store.insert_run(conn, run)
    return run


def _claim(conn, value=120) -> Claim:
    c = Claim(id="run-1-c1", run_id="run-1", slide=3, quote="We are 120 people",
              type=ClaimType.TEAM_SIZE, subject="Example", metric="headcount", value=value,
              unit="people")
    store.insert_claim(conn, c)
    return c


def test_all_tables_created(conn):
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(store.TABLES) <= names


def test_run_and_claim_round_trip(conn):
    run = _run(conn)
    assert store.get_run(conn, run.id) == run
    c = _claim(conn)
    assert store.get_claim(conn, c.id) == c
    assert isinstance(store.get_claim(conn, c.id).value, int)
    store.set_claim_state(conn, c.id, ClaimState.CHECKED)
    assert store.list_claims(conn, "run-1", ClaimState.CHECKED)[0].id == c.id


def test_check_result_and_verdict_checkpoint(conn, rules):
    _run(conn)
    c = _claim(conn)
    call = ledger.record(conn, rules, "run-1", Provider.CRUSTDATA, "/company/enrich",
                         duration_ms=120, ok=True, credits=2)
    ev = Evidence(id="ev-1", claim_id=c.id, source_type=SourceType.CRUSTDATA_COMPANY,
                  locator="/company/enrich", field_or_quote="headcount.total", value=118,
                  record_date="2026-10-15", retrieved_at=now_iso(), call_id=call.id)
    store.save_check_result(conn, c.id, CheckResult(evidence=[ev], observed={"headcount": 118}))
    got = store.get_check_result(conn, c.id)
    assert got.observed == {"headcount": 118} and got.evidence == [ev]
    assert store.get_claim(conn, c.id).state is ClaimState.CHECKED

    v = Verdict(claim_id=c.id, label=VerdictLabel.SUPPORTED, reason_code="within_tolerance",
                explanation="x", evidence_ids=["ev-1"], confidence=Confidence.HIGH)
    store.save_verdict(conn, v)
    assert store.get_verdict(conn, c.id) == v
    assert store.get_claim(conn, c.id).state is ClaimState.DECIDED


def test_failed_checkpoint_rolls_back(conn):
    _run(conn)
    c = _claim(conn)
    bad = Evidence(id="ev-x", claim_id=c.id, source_type=SourceType.WEB_PAGE, locator="u",
                   field_or_quote="q", value=None, record_date=None, retrieved_at=now_iso(),
                   call_id="call-does-not-exist")
    with pytest.raises(sqlite3.IntegrityError):
        store.save_check_result(conn, c.id, CheckResult(evidence=[bad]))
    assert store.get_check_result(conn, c.id) is None
    assert store.get_claim(conn, c.id).state is ClaimState.PENDING


def test_ledger_totals_and_append_only(conn, rules):
    _run(conn)
    ledger.record(conn, rules, "run-1", Provider.CRUSTDATA, "/x", duration_ms=5, ok=True, credits=3)
    ledger.record(conn, rules, "run-1", Provider.LLM, "some-model", duration_ms=5, ok=False,
                  error="timeout", tokens_in=1000, tokens_out=1000)
    t = store.ledger_totals(conn, "run-1")
    assert t["calls"] == 2 and t["failed"] == 1 and t["credits"] == 3
    assert t["cost_inr"] > 0
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE ledger SET cost_inr = 0")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM ledger")


def test_action_idempotency_key_is_unique(conn, rules):
    _run(conn)
    to = rules["actions"]["test_inbox"]
    key = make_idempotency_key("run-1", "founder_email", to)
    a1 = store.insert_action(conn, Action("a1", "run-1", ActionType.FOUNDER_EMAIL, key, to, "s", "b"))
    a2 = store.insert_action(conn, Action("a2", "run-1", ActionType.FOUNDER_EMAIL, key, to, "s2", "b2"))
    assert a1.id == a2.id == "a1"
    assert len(store.list_actions(conn, "run-1")) == 1


def test_inbox_key_unique_and_append_only(conn):
    _run(conn)
    conn.execute("INSERT INTO actions VALUES ('a1','run-1','founder_email','k','t','s','b','sent',NULL,NULL,NULL)")
    m = InboxMessage("k", "a1", "t", "s", "b")
    conn.execute("INSERT INTO inbox VALUES (?,?,?,?,?,?)",
                 (m.idempotency_key, m.action_id, m.recipient, m.subject, m.body, m.received_at))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO inbox VALUES (?,?,?,?,?,?)",
                     (m.idempotency_key, m.action_id, m.recipient, m.subject, m.body, m.received_at))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM inbox")
    assert len(store.list_inbox(conn)) == 1
