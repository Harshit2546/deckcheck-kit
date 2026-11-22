"""Contracts: every dataclass and enum DeckCheck passes between modules (PLAN.md section 3).

Called by: every module. Calls: nothing (stdlib only).
Change anything here only after a DECISIONS.md entry; other lanes code against these shapes.
Times are ISO-8601 UTC strings; dates are ISO 'YYYY-MM-DD' strings.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RunState(str, Enum):
    CREATED = "created"
    EXTRACTED = "extracted"
    RESOLVED = "resolved"
    CHECKING = "checking"
    DECIDED = "decided"
    REPORTED = "reported"
    DONE = "done"
    FAILED = "failed"


RUN_ORDER: list[RunState] = [
    RunState.CREATED, RunState.EXTRACTED, RunState.RESOLVED, RunState.CHECKING,
    RunState.DECIDED, RunState.REPORTED, RunState.DONE,
]


class ClaimState(str, Enum):
    PENDING = "pending"
    CHECKED = "checked"
    DECIDED = "decided"


class ClaimType(str, Enum):
    FOUNDER_BACKGROUND = "founder_background"
    PRIOR_EXIT = "prior_exit"
    TEAM_SIZE = "team_size"
    TEAM_GROWTH = "team_growth"
    FUNDING = "funding"
    COMPANY_FACT = "company_fact"
    CUSTOMER = "customer"
    HIRING = "hiring"
    TRACTION = "traction"
    MARKET_SIZE = "market_size"
    COMPETITION = "competition"


class SourceType(str, Enum):
    CRUSTDATA_COMPANY = "crustdata_company"
    CRUSTDATA_PERSON = "crustdata_person"
    CRUSTDATA_JOB = "crustdata_job"
    WEB_PAGE = "web_page"


class VerdictLabel(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    CANNOT_VERIFY = "CANNOT_VERIFY"
    HELD = "HELD"


class HeldReason(str, Enum):
    """Why a claim is HELD. Timeouts and errors are HELD, never CANNOT_VERIFY."""
    BUDGET = "budget"         # max_cost_inr or max_credits reached
    TIME = "time"             # max_seconds since the run first started
    TIMEOUT = "timeout"       # a call took longer than per_call_timeout_s
    ERROR = "error"           # a source or checker failed
    NO_CHECKER = "no_checker" # no checker module exists for this claim type (cut or not built)


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Provider(str, Enum):
    CRUSTDATA = "crustdata"
    LLM = "llm"
    WEB = "web"


class ActionType(str, Enum):
    FOUNDER_EMAIL = "founder_email"


class ActionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENDING = "sending"
    SENT = "sent"


def now_iso() -> str:
    """Current UTC time as an ISO string (seconds precision)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_idempotency_key(run_id: str, action_type: str, recipient: str) -> str:
    """sha256(run_id + type + recipient), the UNIQUE key that makes a send happen once."""
    return hashlib.sha256(f"{run_id}{action_type}{recipient}".encode()).hexdigest()


@dataclass
class RunInput:
    """What one run is asked to check, after io adapter mapping."""
    deck_path: str
    domain: str
    deck_date: str | None = None          # None -> extract reads PDF metadata and flags it
    deck_date_source: str = "input"       # input | pdf_metadata | missing
    founder_urls: list[str] = field(default_factory=list)


@dataclass
class Run:
    id: str
    input: RunInput
    state: RunState = RunState.CREATED
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    started_at: str | None = None         # first start; max_seconds is measured from here
    error: str | None = None


@dataclass
class Claim:
    id: str
    run_id: str
    slide: int
    quote: str                            # exact text from the slide, verified by extract/
    type: ClaimType
    subject: str                          # company or person the claim is about
    metric: str | None = None             # e.g. "headcount", "total_raised"
    value: float | str | None = None
    unit: str | None = None               # e.g. "people", "INR", "USD"
    as_of: str | None = None              # date the claim refers to
    state: ClaimState = ClaimState.PENDING


@dataclass
class Evidence:
    id: str
    claim_id: str
    source_type: SourceType
    locator: str                          # URL or API endpoint
    field_or_quote: str                   # exact field name or exact quote
    value: float | str | None
    record_date: str | None               # the record's own date
    retrieved_at: str                     # when we fetched it
    call_id: str | None                   # LedgerEntry.id of the call that fetched it


@dataclass
class CheckResult:
    """What a checker returns. Checkers fetch and normalise; they never choose the label."""
    evidence: list[Evidence] = field(default_factory=list)
    observed: dict[str, Any] = field(default_factory=dict)
    comparable: bool = True
    held_reason: str | None = None        # timeout | error | budget | time | ...


@dataclass
class RunContext:
    """Handed to every stage: extract, resolve, each checker (the `ctx` in check(claim, ctx)).
    `entities` is what resolve returned (company/founder ids + confidence), checkpointed."""
    conn: Any                             # sqlite3.Connection
    rules: dict[str, Any]
    run: Run
    entities: dict[str, Any] = field(default_factory=dict)


@dataclass
class Verdict:
    claim_id: str
    label: VerdictLabel
    reason_code: str
    explanation: str                      # LLM-written from evidence only
    evidence_ids: list[str] = field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    missing: str | None = None            # what would settle it


@dataclass
class LedgerEntry:
    id: str
    run_id: str
    provider: Provider
    endpoint_or_model: str
    credits: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_inr: float = 0.0
    duration_ms: int = 0
    ok: bool = True
    error: str | None = None
    ts: str = field(default_factory=now_iso)


@dataclass
class Action:
    id: str
    run_id: str
    type: ActionType
    idempotency_key: str
    recipient: str                        # test inbox only
    subject: str
    body: str
    status: ActionStatus = ActionStatus.PENDING
    decided_by: str | None = None
    decided_at: str | None = None
    sent_at: str | None = None


@dataclass
class InboxMessage:
    """Row in the test inbox. UNIQUE(idempotency_key) is what stops a second send."""
    idempotency_key: str
    action_id: str
    recipient: str
    subject: str
    body: str
    received_at: str = field(default_factory=now_iso)
