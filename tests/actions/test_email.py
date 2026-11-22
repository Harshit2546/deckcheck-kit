"""T19 tests: draft, approve/reject, exactly-once send (also after a real kill), and that only
the test inbox can ever receive an email.

Called by: pytest. Calls: actions/email.py, core/store.py, tests/actions/kill_child.py.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import make_run

from actions import email
from core import runner, store
from core.models import ActionStatus, InboxMessage

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _kill_child(db_path, run_id, point):
    out = subprocess.run([sys.executable, str(HERE / "kill_child.py"), str(db_path), run_id, point])
    assert out.returncode == 137


def test_draft_is_pending_to_test_inbox_and_idempotent(conn, rules):
    rid = make_run(conn)
    a1 = email.draft(conn, rules, rid)
    a2 = email.draft(conn, rules, rid)
    assert a1.id == a2.id and a1.status is ActionStatus.PENDING
    assert a1.recipient == rules["actions"]["test_inbox"]
    assert "80 employees" in a1.body and "term sheet" in a1.body
    assert len(store.list_actions(conn, rid)) == 1


def test_draft_refuses_other_recipient(conn, rules):
    rid = make_run(conn)
    with pytest.raises(email.RecipientRefused):
        email.draft(conn, rules, rid, recipient="founder@realstartup.com")
    assert store.list_actions(conn, rid) == []


def test_draft_skips_when_nothing_to_ask(conn, rules):
    rid = make_run(conn, report={"founder_questions": [], "evidence_requests": []})
    assert email.draft(conn, rules, rid) is None


def test_nothing_is_sent_without_approval(conn, rules):
    email.draft(conn, rules, make_run(conn))
    assert email.send_approved(conn, rules) == []
    assert store.list_inbox(conn) == []


def test_approve_then_send_exactly_once(conn, rules):
    a = email.draft(conn, rules, make_run(conn))
    with pytest.raises(ValueError, match="human name"):
        email.approve(conn, rules, a.id, " ")
    email.approve(conn, rules, a.id, "harshit")
    assert email.send_approved(conn, rules) == [a.id]
    assert email.send_approved(conn, rules) == []
    assert len(store.list_inbox(conn)) == 1
    sent = store.get_action(conn, a.id)
    assert sent.status is ActionStatus.SENT and sent.decided_by == "harshit" and sent.sent_at
    with pytest.raises(ValueError, match="not pending"):
        email.approve(conn, rules, a.id, "harshit")


def test_rejected_is_never_sent(conn, rules):
    a = email.draft(conn, rules, make_run(conn))
    email.reject(conn, a.id, "harshit")
    assert email.send_approved(conn, rules) == []
    assert store.list_inbox(conn) == []
    with pytest.raises(ValueError, match="not pending"):
        email.approve(conn, rules, a.id, "harshit")


@pytest.mark.parametrize("point", ["after_approve", "after_sending"])
def test_kill_between_approve_and_send_then_restart(conn, db_path, rules, point):
    rid = make_run(conn)
    _kill_child(db_path, rid, point)
    expected = ActionStatus.APPROVED if point == "after_approve" else ActionStatus.SENDING
    assert store.list_actions(conn, rid)[0].status is expected
    assert store.list_inbox(conn) == []
    email.send_approved(conn, rules)          # restart
    email.send_approved(conn, rules)          # and again, as a careless retry would
    assert len(store.list_inbox(conn)) == 1
    assert store.list_actions(conn, rid)[0].status is ActionStatus.SENT


def test_restart_when_delivered_but_not_marked_sent(conn, rules):
    a = email.draft(conn, rules, make_run(conn))
    email.approve(conn, rules, a.id, "harshit")
    assert email._claim_for_sending(conn, a)
    store.insert_inbox(conn, InboxMessage(a.idempotency_key, a.id, a.recipient, a.subject, a.body))
    assert email.reconcile(conn, rules) == [a.id]
    assert len(store.list_inbox(conn)) == 1
    assert store.get_action(conn, a.id).status is ActionStatus.SENT


def test_tampered_recipient_is_never_sent(conn, rules):
    a = email.draft(conn, rules, make_run(conn))
    email.approve(conn, rules, a.id, "harshit")
    conn.execute("UPDATE actions SET recipient = 'ceo@realstartup.com' WHERE id = ?", (a.id,))
    with pytest.raises(email.RecipientRefused):
        email.approve(conn, rules, a.id, "harshit")
    assert email.send_approved(conn, rules) == []
    assert store.list_inbox(conn) == []


def test_runner_draft_stage_is_this_function():
    target = runner.STAGES["draft"]
    assert target == "actions.email:draft"
    assert runner._import(target) is email.draft


def test_actions_uses_no_mail_or_http_client():
    banned = re.compile(r"^\s*(import|from)\s+(smtplib|email\.mime|requests|urllib|http|httpx|aiohttp)\b",
                        re.M)
    for path in (ROOT / "actions").glob("*.py"):
        assert not banned.search(path.read_text()), path
