"""Tests for report/builder.py and report/render.py: ordering, sections, config-driven fields, fail-fast errors.

Called by: pytest. Calls: report.builder against a temp SQLite DB filled with test data (tests only).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import copy  # noqa: E402

import pytest  # noqa: E402

from core import store  # noqa: E402
from core.config import load_rules  # noqa: E402
from core.models import (CheckResult, Claim, ClaimType, Confidence as C, Evidence, LedgerEntry, Provider, Run,  # noqa: E402
                         RunInput, SourceType, Verdict, VerdictLabel as L)
from report.builder import build  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    c = store.connect(tmp_path / "t.db")
    yield c
    c.close()


@pytest.fixture
def rules():
    return load_rules()


def seed(conn, source="input"):
    run = Run(id="r1", input=RunInput(deck_path="deck.pdf", domain="acme.example", deck_date="2026-01-15",
                                      deck_date_source=source))
    store.insert_run(conn, run)
    return run


def add(conn, cid, slide, ctype, label, conf=C.MEDIUM, reason="x", missing=None, explanation="because", evidence=True):
    claim = Claim(id=cid, run_id="r1", slide=slide, quote=f"quote {cid} | with pipe", type=ctype, subject="Acme")
    store.insert_claim(conn, claim)
    ev = []
    if evidence:
        ev = [Evidence(id="e-" + cid, claim_id=cid, source_type=SourceType.CRUSTDATA_COMPANY, locator="/company",
                       field_or_quote="headcount", value=40, record_date="2026-01-10",
                       retrieved_at="2026-01-15T10:00:00+00:00", call_id=None)]
    store.save_check_result(conn, cid, CheckResult(evidence=ev, observed={"k": 1}))
    store.save_verdict(conn, Verdict(claim_id=cid, label=label, reason_code=reason, explanation=explanation,
                                     evidence_ids=[e.id for e in ev], confidence=conf, missing=missing))


def test_red_flags_sorted_by_materiality_then_confidence_then_slide(conn, rules):
    seed(conn)
    add(conn, "a", 5, ClaimType.TEAM_SIZE, L.CONTRADICTED, C.MEDIUM)            # materiality 3
    add(conn, "b", 7, ClaimType.FUNDING, L.CONTRADICTED, C.LOW)                 # 5, low
    add(conn, "c", 2, ClaimType.FUNDING, L.CONTRADICTED, C.HIGH)                # 5, high
    add(conn, "d", 1, ClaimType.FOUNDER_BACKGROUND, L.SUPPORTED, C.HIGH)
    report, _ = build(conn, rules, "r1")
    assert [f["claim_id"] for f in report["red_flags"]] == ["c", "b", "a"]
    assert report["summary"]["by_label"]["CONTRADICTED"] == 3 and report["summary"]["by_label"]["SUPPORTED"] == 1


def test_sections_questions_requests_held(conn, rules):
    seed(conn)
    add(conn, "a", 3, ClaimType.FUNDING, L.CONTRADICTED, explanation="Deck 5M, source 20M.")
    add(conn, "b", 4, ClaimType.TEAM_SIZE, L.CANNOT_VERIFY, C.LOW, "no_evidence", "any dated record")
    add(conn, "c", 5, ClaimType.TRACTION, L.NOT_COMPARABLE, C.MEDIUM, "stale_record", "a newer record")
    add(conn, "d", 6, ClaimType.HIRING, L.HELD, C.LOW, "timeout", "Re-run this claim.", evidence=False)
    report, md = build(conn, rules, "r1")
    assert "Deck 5M, source 20M." in report["founder_questions"][0]["question"]
    assert "round announcement" in report["founder_questions"][0]["question"]   # funding template
    assert [r["claim_id"] for r in report["evidence_requests"]] == ["b", "c"]
    assert report["evidence_requests"][0]["request"].endswith("any dated record")
    assert report["held"][0]["reason_code"] == "timeout" and "timeout" in report["held"][0]["note"]
    assert any("HELD" in f for f in report["summary"]["flags"])
    for heading in ("## Summary", "## Red flags", "## Claims", "## Questions for the founders",
                    "## Evidence requests", "## Not checked (HELD)", "## Run cost"):
        assert heading in md


def test_claim_columns_follow_rules_output_fields(conn, rules):
    seed(conn)
    add(conn, "a", 3, ClaimType.FUNDING, L.SUPPORTED)
    custom = copy.deepcopy(rules)
    custom["output"]["fields"] = ["slide", "label", "materiality"]       # the hour-3 style config edit
    report, md = build(conn, custom, "r1")
    assert report["claims"] == [{"slide": 3, "label": "SUPPORTED", "materiality": 5.0}]
    assert "| slide | label | materiality |" in md


def test_unknown_output_field_fails_fast(conn, rules):
    seed(conn)
    bad = copy.deepcopy(rules)
    bad["output"]["fields"] = ["claim_id", "nonsense"]
    with pytest.raises(ValueError, match="nonsense"):
        build(conn, bad, "r1")


def test_sources_carry_locator_field_and_dates(conn, rules):
    seed(conn)
    add(conn, "a", 3, ClaimType.TEAM_SIZE, L.SUPPORTED)
    report, md = build(conn, rules, "r1")
    src = report["claims"][0]["sources"][0]
    assert (src["locator"], src["field_or_quote"], src["record_date"]) == ("/company", "headcount", "2026-01-10")
    assert src["retrieved_at"].startswith("2026-01-15") and "crustdata_company /company [headcount]" in md


def test_pipes_in_quotes_do_not_break_the_table(conn, rules):
    seed(conn)
    add(conn, "a", 3, ClaimType.TEAM_SIZE, L.SUPPORTED)
    _, md = build(conn, rules, "r1")
    assert "quote a \\| with pipe" in md


def test_pending_claim_marks_report_incomplete(conn, rules):
    seed(conn)
    store.insert_claim(conn, Claim(id="p", run_id="r1", slide=1, quote="q", type=ClaimType.FUNDING, subject="Acme"))
    report, _ = build(conn, rules, "r1")
    assert report["claims"][0]["label"] == "PENDING"
    assert any("incomplete" in f for f in report["summary"]["flags"])


def test_deck_date_from_pdf_metadata_is_flagged(conn, rules):
    seed(conn, source="pdf_metadata")
    report, md = build(conn, rules, "r1")
    assert any("pdf_metadata" in f for f in report["summary"]["flags"]) and "pdf_metadata" in md


def test_ledger_summary_by_provider(conn, rules):
    seed(conn)
    store.insert_ledger(conn, LedgerEntry(id="l1", run_id="r1", provider=Provider.CRUSTDATA, endpoint_or_model="/c",
                                          credits=2, cost_inr=2.0, duration_ms=300))
    store.insert_ledger(conn, LedgerEntry(id="l2", run_id="r1", provider=Provider.LLM, endpoint_or_model="m",
                                          tokens_in=100, tokens_out=20, cost_inr=1.5, duration_ms=700, ok=False,
                                          error="timeout"))
    led = build(conn, rules, "r1")[0]["ledger"]
    assert (led["calls"], led["failed"], led["cost_inr"], led["duration_ms"]) == (2, 1, 3.5, 1000)
    assert led["by_provider"]["llm"]["tokens_in"] == 100


def test_unknown_run_and_bad_template_placeholder(conn, rules, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="unknown run"):
        build(conn, rules, "nope")
    seed(conn)
    add(conn, "a", 3, ClaimType.FUNDING, L.CONTRADICTED)
    bad = tmp_path / "t.yaml"
    bad.write_text("founder_questions:\n  default: 'Hi {nonexistent}'\nevidence_requests:\n  default: x\nheld_notes:\n  default: x\n")
    import report.builder as b
    monkeypatch.setattr(b, "TEMPLATES_PATH", bad)
    monkeypatch.setattr(b, "_load_templates", lambda path=bad: b.yaml.safe_load(open(path)))
    with pytest.raises(ValueError, match="nonexistent"):
        build(conn, rules, "r1")


def test_report_is_deterministic_apart_from_timestamp(conn, rules):
    seed(conn)
    add(conn, "a", 3, ClaimType.FUNDING, L.CONTRADICTED)
    r1, m1 = build(conn, rules, "r1")
    r2, m2 = build(conn, rules, "r1")
    r1.pop("generated_at"), r2.pop("generated_at")
    assert r1 == r2
