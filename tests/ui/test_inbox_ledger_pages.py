"""T18 tests: Inbox page shows local inbox rows with the "no real email" notice; Ledger page
shows calls, credits, rupees and seconds per run. Plus: the UI never writes verdicts.

Called by: pytest. Calls: ui/app.py (Streamlit AppTest), ui/data.py, core/store.py, actions/email.py.
"""

import re
from pathlib import Path

from conftest import open_app
from test_claims_page import make_decided_run

from actions import email
from core import store
from core.config import load_rules
from core.models import Run, RunInput
from ui import data

ROOT = Path(__file__).resolve().parents[2]


def test_inbox_page_shows_sent_email(conn, db_path):
    rules = load_rules()
    store.insert_run(conn, Run(id="run-in", input=RunInput("deck.pdf", "locus.sh", "2026-11-15")))
    store.save_report(conn, "run-in", {"run": {"domain": "locus.sh"},
                                       "founder_questions": [{"slide": 2, "question": "Q?"}]}, "#")
    a = email.draft(conn, rules, "run-in")
    email.approve(conn, rules, a.id, "harshit")
    email.send_approved(conn, rules)
    at = open_app(db_path, "Inbox")
    assert any("no real email" in w.value for w in at.warning)
    assert at.dataframe[0].value["to"].tolist() == [rules["actions"]["test_inbox"]]


def test_empty_inbox(db_path):
    at = open_app(db_path, "Inbox")
    assert any("empty" in i.value for i in at.info)


def test_ledger_summary_and_page(conn, db_path):
    rid = make_decided_run(conn, load_rules())
    s = data.ledger_summary(conn, rid)
    assert (s["calls"], s["credits"], s["seconds"]) == (2, 2.0, 2.0)
    assert s["cost_inr"] == round(store.ledger_totals(conn, rid)["cost_inr"], 2)
    at = open_app(db_path, "Ledger")
    labels = {m.label: m.value for m in at.metric}
    assert labels["Calls"] == "2" and labels["Seconds in calls"] == "2.0"
    assert len(at.dataframe[0].value) == 2


def test_ui_never_writes_pipeline_rows():
    banned = re.compile(r"\b(save_verdict|save_check_result|insert_claim|insert_evidence|"
                        r"insert_ledger|set_claim_state|set_run_state|insert_inbox|"
                        r"INSERT|UPDATE|DELETE)\b")
    for path in (ROOT / "ui").glob("*.py"):
        assert not banned.search(path.read_text()), path
