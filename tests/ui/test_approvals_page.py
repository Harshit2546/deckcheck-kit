"""T18 tests: the Approvals page only approves or rejects on a click with a name, then sends
through actions/email.py exactly once; nothing is sent by just opening the page.

Called by: pytest. Calls: ui/app.py (Streamlit AppTest), actions/email.py, core/store.py.
"""

from conftest import open_app

from actions import email
from core import store
from core.config import load_rules
from core.models import ActionStatus, Run, RunInput

REPORT = {"run": {"id": "run-ap", "domain": "locus.sh"},
          "founder_questions": [{"slide": 4, "question": "How do you count 300 people?"}],
          "evidence_requests": []}


def _pending(conn):
    store.insert_run(conn, Run(id="run-ap", input=RunInput("deck.pdf", "locus.sh", "2026-11-15")))
    store.save_report(conn, "run-ap", REPORT, "# r")
    return email.draft(conn, load_rules(), "run-ap")


def _button(at, key):
    return next(b for b in at.button if b.key == key)


def test_opening_the_page_sends_nothing(conn, db_path):
    a = _pending(conn)
    at = open_app(db_path, "Approvals")
    assert "300 people" in " ".join(t.value for t in at.text)
    assert store.get_action(conn, a.id).status is ActionStatus.PENDING
    assert store.list_inbox(conn) == []


def test_approve_needs_a_name(conn, db_path):
    a = _pending(conn)
    at = open_app(db_path, "Approvals")
    _button(at, f"approve-{a.id}").click().run()
    assert any("human name" in e.value for e in at.error)
    assert store.get_action(conn, a.id).status is ActionStatus.PENDING


def test_approve_click_sends_exactly_once(conn, db_path):
    a = _pending(conn)
    at = open_app(db_path, "Approvals")
    at.text_input[0].input("harshit").run()
    _button(at, f"approve-{a.id}").click().run()
    assert not at.exception
    assert store.get_action(conn, a.id).status is ActionStatus.SENT
    at.run()                                             # reloading must not send again
    assert len(store.list_inbox(conn)) == 1


def test_reject_click_never_sends(conn, db_path):
    a = _pending(conn)
    at = open_app(db_path, "Approvals")
    at.text_input[0].input("harshit").run()
    _button(at, f"reject-{a.id}").click().run()
    assert store.get_action(conn, a.id).status is ActionStatus.REJECTED
    assert store.list_inbox(conn) == []


def test_send_now_finishes_an_email_stuck_after_a_crash(conn, db_path):
    a = _pending(conn)
    email.approve(conn, load_rules(), a.id, "harshit")
    assert email._claim_for_sending(conn, a)             # crashed while `sending`
    at = open_app(db_path, "Approvals")
    next(b for b in at.button if b.label.startswith("Send now")).click().run()
    assert store.get_action(conn, a.id).status is ActionStatus.SENT
    assert len(store.list_inbox(conn)) == 1
