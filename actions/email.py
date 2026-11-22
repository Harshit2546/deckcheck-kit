"""Founder email: draft from the run's report, human approve/reject, and the exactly-once send.

Called by: core/runner.py (draft, after the report), ui/app.py (approve, reject, send), tests.
Calls: core/store.py, core/config.py, core/log.py.
"Send" only inserts into the local `inbox` table, and only to rules.yaml actions.test_inbox.
No mail or HTTP client is used here, on purpose. Never wrap send in a plain retry: the
`sending` state + UNIQUE(idempotency_key) on inbox is what makes it happen once.
"""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from core import store
from core.config import rule
from core.log import log_error, log_step
from core.models import (Action, ActionStatus, ActionType, InboxMessage, make_idempotency_key,
                         now_iso)


class RecipientRefused(ValueError):
    """Raised for any recipient other than rules.yaml actions.test_inbox."""


def check_recipient(rules: dict[str, Any], recipient: str) -> None:
    allowed = str(rule(rules, "actions.test_inbox")).strip().lower()
    if recipient.strip().lower() != allowed:
        raise RecipientRefused(f"recipient {recipient!r} is not the test inbox")


def _body(report: dict[str, Any]) -> str | None:
    """Plain-text email from the report's founder questions and evidence requests."""
    questions = report.get("founder_questions") or []
    requests = report.get("evidence_requests") or []
    if not questions and not requests:
        return None
    lines = ["Hello,", "", "Thank you for sharing your deck. Before our next meeting we would "
             "like to check a few points.", ""]
    if questions:
        lines += ["Questions:"] + [f"{i}. (slide {q['slide']}) {q['question']}"
                                   for i, q in enumerate(questions, 1)] + [""]
    if requests:
        lines += ["Could you share:"] + [f"- (slide {r['slide']}) {r['request']}"
                                         for r in requests] + [""]
    lines += ["Best regards,", "Investment team"]
    return "\n".join(lines)


def draft(conn: sqlite3.Connection, rules: dict[str, Any], run_id: str,
          recipient: str | None = None) -> Action | None:
    """Create the founder email as `pending` (idempotent: one per run and recipient).
    Returns None when the report has nothing to ask."""
    to = recipient if recipient is not None else str(rule(rules, "actions.test_inbox"))
    check_recipient(rules, to)
    saved = store.get_report(conn, run_id)
    if saved is None:
        raise ValueError(f"run {run_id} has no report yet")
    body = _body(saved[0])
    if body is None:
        log_step(run_id, None, "actions.draft", "skipped", note="no questions to ask")
        return None
    key = make_idempotency_key(run_id, ActionType.FOUNDER_EMAIL.value, to)
    action = store.insert_action(conn, Action(
        id="act-" + uuid.uuid4().hex[:12], run_id=run_id, type=ActionType.FOUNDER_EMAIL,
        idempotency_key=key, recipient=to,
        subject=f"Questions on your deck ({saved[0].get('run', {}).get('domain', run_id)})",
        body=body))
    log_step(run_id, None, "actions.draft", action.status.value, action=action.id)
    return action


def _decide(conn: sqlite3.Connection, action_id: str, decided_by: str,
            new: ActionStatus) -> Action:
    if not decided_by.strip():
        raise ValueError("a human name is required to approve or reject")
    if not store.set_action_status(conn, action_id, ActionStatus.PENDING, new,
                                   decided_by=decided_by, decided_at=now_iso()):
        current = store.get_action(conn, action_id)
        raise ValueError(f"action {action_id} is "
                         f"{current.status.value if current else 'missing'}, not pending")
    action = store.get_action(conn, action_id)
    log_step(action.run_id, None, f"actions.{new.value}", "ok", action=action_id, by=decided_by)
    return action


def approve(conn: sqlite3.Connection, rules: dict[str, Any], action_id: str,
            decided_by: str) -> Action:
    """Human click: pending -> approved. Refuses a non-test recipient."""
    action = store.get_action(conn, action_id)
    if action is None:
        raise ValueError(f"no action {action_id}")
    check_recipient(rules, action.recipient)
    return _decide(conn, action_id, decided_by, ActionStatus.APPROVED)


def reject(conn: sqlite3.Connection, action_id: str, decided_by: str) -> Action:
    """Human click: pending -> rejected. A rejected email is never sent."""
    return _decide(conn, action_id, decided_by, ActionStatus.REJECTED)


def _claim_for_sending(conn: sqlite3.Connection, action: Action) -> bool:
    """Step 1 (own commit): approved -> sending. False if another sender got it first."""
    return store.set_action_status(conn, action.id, ActionStatus.APPROVED, ActionStatus.SENDING)


def _deliver(conn: sqlite3.Connection, action: Action) -> None:
    """Step 2 (one transaction): inbox row with the UNIQUE key, then sending -> sent."""
    with store.transaction(conn):
        store.insert_inbox(conn, InboxMessage(action.idempotency_key, action.id,
                                              action.recipient, action.subject, action.body))
        store.set_action_status(conn, action.id, ActionStatus.SENDING, ActionStatus.SENT,
                                sent_at=now_iso())


def reconcile(conn: sqlite3.Connection, rules: dict[str, Any]) -> list[str]:
    """After a restart: finish every action stuck in `sending`. If its key is already in the
    inbox it was delivered, so only mark it sent; otherwise deliver it now (once)."""
    done = []
    for action in store.list_actions(conn, status=ActionStatus.SENDING):
        try:
            check_recipient(rules, action.recipient)
        except RecipientRefused as e:
            log_error(action.run_id, None, "actions.reconcile", str(e), action=action.id)
            continue
        if store.inbox_has_key(conn, action.idempotency_key):
            store.set_action_status(conn, action.id, ActionStatus.SENDING, ActionStatus.SENT,
                                    sent_at=now_iso())
            result = "already_delivered"
        else:
            _deliver(conn, action)
            result = "delivered"
        log_step(action.run_id, None, "actions.reconcile", result, action=action.id)
        done.append(action.id)
    return done


def send_approved(conn: sqlite3.Connection, rules: dict[str, Any]) -> list[str]:
    """Send every approved email exactly once. Safe to call any number of times, also after
    a kill: it reconciles `sending` rows first. Returns ids of actions sent by this call."""
    sent = reconcile(conn, rules)
    for action in store.list_actions(conn, status=ActionStatus.APPROVED):
        try:
            check_recipient(rules, action.recipient)
        except RecipientRefused as e:
            log_error(action.run_id, None, "actions.send", str(e), action=action.id)
            continue
        if not _claim_for_sending(conn, action):
            continue
        _deliver(conn, action)
        log_step(action.run_id, None, "actions.send", "sent", action=action.id,
                 to=action.recipient)
        sent.append(action.id)
    return sent
