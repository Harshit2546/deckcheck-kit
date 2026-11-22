"""The single home of every DeckCheck contract (PLAN.md section 3) and the rules.yaml schema.

Who calls it: every lane imports from here (store, runner, checkers, verdict, report, actions, ui).
What it calls: nothing but pydantic and the standard library.
Changing any field here is a contract change and needs a DECISIONS.md entry first (AGENTS.md section 3).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    """Return a fresh opaque id (32 hex chars). Ids are strings so a row can be referenced before insert."""
    return uuid.uuid4().hex


def utcnow() -> datetime:
    """Return the current time as an aware UTC datetime (used for retrieved_at, ts, decided_at)."""
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- enums


class RunState(StrEnum):
    """Run states, in the only order a run may move through them (PLAN.md section 2)."""

    CREATED = "created"
    EXTRACTED = "extracted"
    RESOLVED = "resolved"
    CHECKING = "checking"
    DECIDED = "decided"
    REPORTED = "reported"
    DONE = "done"


RUN_STATE_ORDER: list[RunState] = list(RunState)


class ClaimState(StrEnum):
    """Per-claim checkpoint: pending -> checked (evidence saved) -> decided (verdict saved)."""

    PENDING = "pending"
    CHECKED = "checked"
    DECIDED = "decided"


class ClaimType(StrEnum):
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


class SourceType(StrEnum):
    CRUSTDATA_COMPANY = "crustdata_company"
    CRUSTDATA_PERSON = "crustdata_person"
    CRUSTDATA_JOB = "crustdata_job"
    WEB_PAGE = "web_page"


class VerdictLabel(StrEnum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    CANNOT_VERIFY = "CANNOT_VERIFY"
    HELD = "HELD"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Provider(StrEnum):
    CRUSTDATA = "crustdata"
    LLM = "llm"
    WEB = "web"


class ActionType(StrEnum):
    FOUNDER_EMAIL = "founder_email"


class ActionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENDING = "sending"
    SENT = "sent"


class HeldReason(StrEnum):
    """Standard reason codes for a HELD verdict. Timeouts and errors are HELD, never CANNOT_VERIFY."""

    BUDGET = "budget"
    TIME = "time"
    CREDITS = "credits"
    TIMEOUT = "timeout"
    ERROR = "error"
    IDENTITY_UNCLEAR = "identity_unclear"


# --------------------------------------------------------------------------- contracts


class _Model(BaseModel):
    """Base for all contracts: unknown fields are rejected so a typo cannot slip through silently."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class RunRequest(_Model):
    """What a user (or the kickoff-kit adapter) hands to `cli.py run`."""

    deck_path: str
    company_domain: str
    deck_date: str | None = None  # ISO date YYYY-MM-DD; None means "use PDF metadata, flagged"
    founder_urls: list[str] = Field(default_factory=list)


class Run(_Model):
    """One checking run. `resolved` holds the resolve lane's output (company + founders), set at state RESOLVED."""

    id: str = Field(default_factory=lambda: "run_" + new_id()[:10])
    deck_path: str
    company_domain: str
    deck_date: str | None = None
    deck_date_source: str = "given"  # given | pdf_metadata | missing
    founder_urls: list[str] = Field(default_factory=list)
    state: RunState = RunState.CREATED
    resolved: dict[str, Any] | None = None
    active_seconds: float = 0.0  # time spent working, summed across resumes (used for max_seconds)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Claim(_Model):
    """One factual statement from a slide. `quote` is the exact slide text (code-checked by the extract lane).

    `value` is the number or text the deck states; `as_of` is the date or period the deck gives (ISO date
    when the deck gives one, otherwise the deck's own words such as "Q3 2024"); checkers normalise it.
    """

    id: str = Field(default_factory=new_id)
    run_id: str
    slide: int
    quote: str
    type: ClaimType
    subject: str
    metric: str | None = None
    value: float | str | None = None
    unit: str | None = None
    as_of: str | None = None
    state: ClaimState = ClaimState.PENDING


class Evidence(_Model):
    """One sourced fact. No source, no fact: locator, field_or_quote, record_date and retrieved_at are the audit trail."""

    id: str = Field(default_factory=new_id)
    claim_id: str
    source_type: SourceType
    locator: str  # URL or API endpoint
    field_or_quote: str  # exact field name or exact quote
    value: Any = None
    record_date: str | None = None  # the record's own date (ISO date), None only if the source gives none
    retrieved_at: datetime = Field(default_factory=utcnow)
    call_id: str | None = None  # LedgerEntry.id of the call that fetched it


class Verdict(_Model):
    """The decision for one claim. Label and reason_code come from code (verdict/engine.py), never the LLM."""

    claim_id: str
    label: VerdictLabel
    reason_code: str
    explanation: str  # LLM-written from evidence only
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.LOW
    missing: str | None = None  # what would settle it


class LedgerEntry(_Model):
    """One external call (success or failure). Append-only."""

    id: str = Field(default_factory=new_id)
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
    ts: datetime = Field(default_factory=utcnow)


def make_idempotency_key(run_id: str, action_type: ActionType | str, recipient: str) -> str:
    """sha256 of run_id, type and recipient, joined with '|' so different field splits cannot collide."""
    raw = f"{run_id}|{ActionType(action_type).value}|{recipient}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Action(_Model):
    """An outward step (the founder email). Starts `pending`; only a human moves it to `approved`."""

    id: str = Field(default_factory=new_id)
    run_id: str
    type: ActionType = ActionType.FOUNDER_EMAIL
    idempotency_key: str = ""
    recipient: str  # the team's test inbox only
    subject: str
    body: str
    status: ActionStatus = ActionStatus.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None
    sent_at: datetime | None = None

    def model_post_init(self, __context: Any) -> None:
        """Fill idempotency_key from run_id + type + recipient when the caller did not give one."""
        if not self.idempotency_key:
            self.idempotency_key = make_idempotency_key(self.run_id, self.type, self.recipient)


class InboxMessage(_Model):
    """A row in the team's test inbox. UNIQUE(idempotency_key) in the DB makes a second send impossible."""

    id: str = Field(default_factory=new_id)
    idempotency_key: str
    action_id: str
    run_id: str
    recipient: str
    subject: str
    body: str
    received_at: datetime = Field(default_factory=utcnow)


class CheckContext(_Model):
    """What a checker receives next to the claim. `company` and `founders` are the resolve lane's output.

    OPEN QUESTION (HANDOFF): resolve/entities.py should ask for typed company/founder models via DECISIONS.md;
    until then they travel as plain dicts. Only professional fields may be kept (ETHICS).
    """

    run_id: str
    company_domain: str
    deck_date: str | None = None
    company: dict[str, Any] | None = None
    founders: list[dict[str, Any]] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)


class CheckResult(_Model):
    """What a checker returns: facts only. The checker never chooses the verdict label."""

    evidence: list[Evidence] = Field(default_factory=list)
    observed: dict[str, Any] = Field(default_factory=dict)  # normalised values the engine compares with the claim
    comparable: bool = True
    held_reason: str | None = None  # a HeldReason value when the call timed out, errored or hit a limit


# --------------------------------------------------------------------------- rules.yaml schema


class _Rules(BaseModel):
    """Base for rules.yaml sections: typos in keys fail loudly at load time, so live edits cannot silently no-op."""

    model_config = ConfigDict(extra="forbid")


class Limits(_Rules):
    max_cost_inr: float
    max_seconds: float
    max_credits: float
    per_call_timeout_s: float


class Pricing(_Rules):
    """Rupee conversion used by sources/ when writing ledger rows."""

    inr_per_credit: float
    inr_per_1k_tokens_in: float
    inr_per_1k_tokens_out: float


class ActionsConfig(_Rules):
    test_inbox_recipient: str  # the only address the founder email may go to
    email_subject_template: str


class Rules(_Rules):
    """The whole of config/rules.yaml. Owned by the finance partner; values here are not code."""

    version: int
    limits: Limits
    pricing: Pricing
    actions: ActionsConfig
    # claim type -> named tolerance, e.g. team_size: {tolerance_pct: 20}. Keys are free-form per claim type.
    tolerances: dict[str, dict[str, float]]
    # title keyword -> seniority level (higher = more senior); used by the founder / hiring checkers
    title_levels: dict[str, int]
    # claim type -> materiality weight used to rank red flags
    materiality_weights: dict[str, float]
    # output name -> ordered list of fields to include (the hour-3 requirement change lands here)
    output_fields: dict[str, list[str]]
