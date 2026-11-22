"""Child process for the T19 kill tests: approves the run's email, then dies with os._exit
(like `kill -9`) at the point named on the command line.

Called by: tests/actions/test_email.py via subprocess. Calls: actions/email.py, core/store.py.
Usage: python tests/actions/kill_child.py <db> <run_id> after_approve|after_sending
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from actions import email  # noqa: E402
from core import store  # noqa: E402
from core.config import load_rules  # noqa: E402

if __name__ == "__main__":
    db, run_id, point = sys.argv[1:4]
    conn, rules = store.connect(db), load_rules()
    action = email.draft(conn, rules, run_id)
    email.approve(conn, rules, action.id, "harshit")
    if point == "after_approve":
        os._exit(137)
    assert email._claim_for_sending(conn, store.get_action(conn, action.id))
    os._exit(137)           # after_sending: status is `sending`, nothing in the inbox yet
