"""Tests for core/models.py, core/store.py, core/log.py and core/config.py (T01).

Who calls it: pytest. What it calls: the core package only, with an in-memory or tmp_path SQLite DB.
Fixtures here are test data and never reach the runtime path.
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from pydantic import ValidationError

from core import log as dclog
from core.adapter_loader import load_adapter
from core.config import load_rules
from core.models import (
    Action,
    ActionStatus,
    Claim,
    ClaimState,
    ClaimType,
    CheckResult,
    Evidence,
    LedgerEntry,
    Provider,
    Run,
    RunState,
    SourceType,
    Verdict,
    VerdictLabel,
    make_idempotency_key,
)
from core.store import Store


@pytest.fixture()
def store() -> Store:
    s = Store(":memory:")
    yield s
    s.close()


@pytest.fixture()
def run(store: Store) -> Run:
    return store.create_run(Run(deck_path="deck.pdf", company_domain="acme.example", deck_date="2026-01-15"))


def _claim(run_id: str, **kw) -> Claim:
    base = dict(run_id=run_id, slide=3, quote="We are 42 people", type=ClaimType.TEAM_SIZE,
                subject="Acme", metric="headcount", value=42, unit="people")
    base.update(kw)
    return Claim(**base)


def test_all_tables_created(store: Store) -> None:
    assert set(store.table_names()) >= {
        "runs", "claims", "check_results", "evidence", "verdicts", "ledger", "actions", "inbox",
    }


def test_tables_created_on_first_use_in_a_file(tmp_path) -> None:
    path = tmp_path / "sub" / "x.db"
    Store(path).close()
    assert path.exists()
    Store(path).close()  # opening again must not fail or drop data


def test_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Claim(run_id="r", slide=1, quote="q", type=ClaimType.FUNDING, subject="s", bogus=1)


def test_run_roundtrip_and_states(store: Store, run: Run) -> None:
    got = store.get_run(run.id)
    assert got is not None and got.state == RunState.CREATED and got.company_domain == "acme.example"
    store.set_run_state(run.id, RunState.EXTRACTED)
    store.set_run_resolved(run.id, {"company": {"domain": "acme.example"}})
    got = store.get_run(run.id)
    assert got.state == RunState.EXTRACTED and got.resolved == {"company": {"domain": "acme.example"}}
    assert store.add_active_seconds(run.id, 2.5) == 2.5
    assert store.add_active_seconds(run.id, 1.0) == 3.5


def test_claims_idempotent_insert_and_state(store: Store, run: Run) -> None:
    c = _claim(run.id)
    store.add_claims([c])
    store.add_claims([c])  # resume re-adds: must not duplicate or reset state
    store.set_claim_state(c.id, ClaimState.CHECKED)
    store.add_claims([c])
    claims = store.list_claims(run.id)
    assert len(claims) == 1 and claims[0].state == ClaimState.CHECKED and claims[0].value == 42
    assert store.list_claims(run.id, ClaimState.PENDING) == []


def test_claim_text_value_keeps_type(store: Store, run: Run) -> None:
    c = _claim(run.id, value="Series A", metric="round")
    store.add_claims([c])
    assert store.get_claim(c.id).value == "Series A"


def test_check_result_and_verdict_checkpoint(store: Store, run: Run) -> None:
    c = _claim(run.id)
    store.add_claims([c])
    ev = Evidence(claim_id=c.id, source_type=SourceType.CRUSTDATA_COMPANY, locator="/company",
                  field_or_quote="headcount", value=40, record_date="2026-01-10", call_id="L1")
    store.save_check_result(c.id, CheckResult(evidence=[ev], observed={"headcount": 40}))
    assert store.get_claim(c.id).state == ClaimState.CHECKED
    res = store.get_check_result(c.id)
    assert res.observed == {"headcount": 40} and res.comparable and res.evidence[0].id == ev.id
    assert res.evidence[0].field_or_quote == "headcount" and res.evidence[0].retrieved_at.tzinfo is not None

    v = Verdict(claim_id=c.id, label=VerdictLabel.SUPPORTED, reason_code="within_tolerance",
                explanation="40 vs 42", evidence_ids=[ev.id])
    store.save_verdict(v)
    store.save_verdict(v)  # resume: one verdict per claim, no duplicate
    assert store.get_claim(c.id).state == ClaimState.DECIDED
    assert store.get_verdict(c.id).label == VerdictLabel.SUPPORTED
    assert len(store.list_verdicts(run.id)) == 1


def test_held_check_result_roundtrip(store: Store, run: Run) -> None:
    c = _claim(run.id)
    store.add_claims([c])
    store.save_check_result(c.id, CheckResult(comparable=False, held_reason="timeout"))
    res = store.get_check_result(c.id)
    assert res.held_reason == "timeout" and res.comparable is False and res.evidence == []


def test_failed_save_check_result_rolls_back(store: Store, run: Run) -> None:
    c = _claim(run.id)
    store.add_claims([c])
    good = Evidence(claim_id=c.id, source_type=SourceType.WEB_PAGE, locator="u", field_or_quote="q")
    bad = Evidence(claim_id="no-such-claim", source_type=SourceType.WEB_PAGE, locator="u", field_or_quote="q")
    with pytest.raises(ValueError):
        store.save_check_result(c.id, CheckResult(evidence=[good, bad]))
    assert store.list_evidence(c.id) == []  # the good row was rolled back with the bad one
    assert store.get_claim(c.id).state == ClaimState.PENDING
    assert store.get_check_result(c.id) is None


def test_ledger_append_only_and_totals(store: Store, run: Run) -> None:
    store.add_ledger(LedgerEntry(run_id=run.id, provider=Provider.CRUSTDATA, endpoint_or_model="/company",
                                 credits=2, cost_inr=2.0, duration_ms=300))
    store.add_ledger(LedgerEntry(run_id=run.id, provider=Provider.LLM, endpoint_or_model="model-x",
                                 tokens_in=100, tokens_out=20, cost_inr=1.5, duration_ms=700,
                                 ok=False, error="timeout"))
    totals = store.ledger_totals(run.id)
    assert totals == {"cost_inr": 3.5, "credits": 2.0, "duration_ms": 1000.0, "calls": 2.0}
    assert [e.ok for e in store.list_ledger(run.id)] == [True, False]
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute("UPDATE ledger SET cost_inr = 0")
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute("DELETE FROM ledger")


def test_idempotency_key_is_deterministic_and_set(store: Store, run: Run) -> None:
    a = Action(run_id=run.id, recipient="t@x.test", subject="s", body="b")
    assert a.idempotency_key == make_idempotency_key(run.id, "founder_email", "t@x.test")
    assert a.status == ActionStatus.PENDING
    first = store.create_action(a)
    again = store.create_action(Action(run_id=run.id, recipient="t@x.test", subject="s2", body="b2"))
    assert again.id == first.id and again.subject == "s"  # same key: the draft is not duplicated
    assert len(store.list_actions(run.id)) == 1


def test_inbox_unique_idempotency_key(store: Store, run: Run) -> None:
    a = store.create_action(Action(run_id=run.id, recipient="t@x.test", subject="s", body="b"))
    row = ("i1", a.idempotency_key, a.id, run.id, a.recipient, a.subject, a.body, "2026-01-01T00:00:00+00:00")
    sql = "INSERT INTO inbox (id, idempotency_key, action_id, run_id, recipient, subject, body, received_at)" \
          " VALUES (?,?,?,?,?,?,?,?)"
    store.conn.execute(sql, row)
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(sql, ("i2",) + row[1:])
    assert len(store.list_inbox(run.id)) == 1


def test_action_status_check_constraint(store: Store, run: Run) -> None:
    a = store.create_action(Action(run_id=run.id, recipient="t@x.test", subject="s", body="b"))
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute("UPDATE actions SET status = 'bogus' WHERE id = ?", (a.id,))


def test_nested_transaction_joins_outer(store: Store, run: Run) -> None:
    with pytest.raises(RuntimeError):
        with store.transaction():
            store.set_run_state(run.id, RunState.EXTRACTED)  # nested helper opens its own transaction()
            raise RuntimeError("boom")
    assert store.get_run(run.id).state == RunState.CREATED


def test_rules_yaml_loads_and_rejects_typos(tmp_path) -> None:
    rules = load_rules()
    assert rules.limits.max_cost_inr > 0 and "team_size" in rules.tolerances
    assert rules.tolerances["team_size"]["tolerance_pct"] > 0
    bad = tmp_path / "rules.yaml"
    bad.write_text(open("config/rules.yaml", encoding="utf-8").read().replace("max_cost_inr", "max_cost_in"))
    with pytest.raises(ValueError):
        load_rules(bad)


def test_log_step_writes_one_json_line(tmp_path) -> None:
    log_file = tmp_path / "d.log"
    dclog.configure(log_file)
    rec = dclog.log_step("run_1", "extract", "ok", claim_id="c1", slides=8)
    line = log_file.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert json.loads(line)["step"] == "extract" and rec["run_id"] == "run_1" and rec["slides"] == 8


def test_adapter_loads_despite_stdlib_io_name() -> None:
    adapter = load_adapter()
    req = adapter.request_from_kit({"deck_path": "d.pdf", "company_domain": "a.example"})
    assert req.company_domain == "a.example" and req.founder_urls == []
