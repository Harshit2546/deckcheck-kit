"""UI data helpers: everything ui/app.py shows or does, as plain functions (no Streamlit here),
so the pages stay thin and tests can call these directly.

Called by: ui/app.py, tests/ui/. Calls: core/store.py, core/adapter_loader.py (io/adapter.py),
actions/email.py, cli.py (as a background process to run or resume a run).
Never writes claims, evidence or verdicts: only a new run row, and email approval through actions/.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import store
from core.adapter_loader import load_adapter
from core.models import ActionStatus, Run, RunInput

ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path(tempfile.gettempdir()) / "deckcheck-uploads"


# ---------- Run page ----------

def request_files() -> list[Path]:
    """D3 request files in the repo the demo can pick (real decks first)."""
    found = sorted((ROOT / "tests" / "decks").glob("*_request.json"))
    return found + sorted((ROOT / "tests" / "requests").glob("*.json"))


def save_upload(name: str, data: bytes) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}-{Path(name).name}"
    path.write_bytes(data)
    return path


def input_from_request(request: dict[str, Any], base_dir: Path,
                       deck_override: Path | None = None) -> RunInput:
    """D3 request -> RunInput (io/adapter.from_kit). A relative deck_path is read from base_dir,
    as cli.py does; an uploaded deck replaces it."""
    run_input = load_adapter().from_kit(request)
    if deck_override is not None:
        run_input.deck_path = str(deck_override)
    elif not Path(run_input.deck_path).is_absolute():
        run_input.deck_path = str((base_dir / run_input.deck_path).resolve())
    return run_input


def input_from_request_file(path: Path) -> RunInput:
    return input_from_request(json.loads(path.read_text(encoding="utf-8")), path.parent)


def input_from_form(deck_path: Path, domain: str, deck_date: str | None,
                    founder_urls: list[str]) -> RunInput:
    """Deck + domain + date form -> RunInput, through the same D3 adapter."""
    return input_from_request({"deck_path": str(deck_path), "company_domain": domain,
                               "deck_date": deck_date or None, "founder_urls": founder_urls},
                              ROOT)


def create_run(conn: sqlite3.Connection, run_input: RunInput) -> str:
    """Insert the run row (state created). The pipeline itself runs in launch()."""
    if not Path(run_input.deck_path).is_file():
        raise ValueError(f"deck not found: {run_input.deck_path}")
    run_id = ("run-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
              + "-" + uuid.uuid4().hex[:6])
    store.insert_run(conn, Run(id=run_id, input=run_input))
    return run_id


def launch(db_path: str, run_id: str) -> subprocess.Popen:
    """Run (or resume) a run in its own process with `python cli.py resume`, so the page stays
    responsive and a killed run resumes exactly like from the terminal."""
    log_dir = Path(os.environ.get("DECKCHECK_LOG_DIR", ROOT / "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    out = open(log_dir / "ui_runs.log", "a", encoding="utf-8")
    return subprocess.Popen([sys.executable, str(ROOT / "cli.py"), "--db", db_path, "resume", run_id],
                            cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)


def run_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = []
    for run in store.list_runs(conn):
        totals = store.ledger_totals(conn, run.id)
        rows.append({"run_id": run.id, "state": run.state.value, "domain": run.input.domain,
                     "deck_date": run.input.deck_date, "deck_date_source": run.input.deck_date_source,
                     "claims": len(store.list_claims(conn, run.id)),
                     "cost_inr": round(totals["cost_inr"], 2), "created_at": run.created_at,
                     "error": run.error})
    return rows


# ---------- Claims page ----------

def _is_url(text: str) -> bool:
    return text.startswith(("http://", "https://"))


def claim_rows(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    """Each claim with its verdict and sources, read only from the store."""
    rows = []
    for claim in store.list_claims(conn, run_id):
        v = store.get_verdict(conn, claim.id)
        sources = [{"url_or_endpoint": e.locator, "is_url": _is_url(e.locator),
                    "field_or_quote": e.field_or_quote, "value": e.value,
                    "record_date": e.record_date, "retrieved_at": e.retrieved_at}
                   for e in store.list_evidence(conn, claim.id)]
        rows.append({"claim_id": claim.id, "slide": claim.slide, "type": claim.type.value,
                     "quote": claim.quote, "claimed_value": claim.value, "unit": claim.unit,
                     "state": claim.state.value,
                     "verdict": v.label.value if v else "PENDING",
                     "confidence": v.confidence.value if v else None,
                     "reason_code": v.reason_code if v else None,
                     "explanation": v.explanation if v else None,
                     "missing": v.missing if v else None, "sources": sources})
    return rows


# ---------- Approvals and Inbox pages ----------

def emails(conn: sqlite3.Connection, status: ActionStatus | None = None) -> list[Any]:
    return store.list_actions(conn, status=status)


def inbox_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [{"received_at": m.received_at, "to": m.recipient, "subject": m.subject,
             "action_id": m.action_id, "body": m.body} for m in store.list_inbox(conn)]


# ---------- Ledger page ----------

def ledger_summary(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    entries = store.list_ledger(conn, run_id)
    totals = store.ledger_totals(conn, run_id)
    return {"calls": int(totals["calls"]), "failed": int(totals["failed"]),
            "credits": totals["credits"], "cost_inr": round(totals["cost_inr"], 2),
            "seconds": round(sum(e.duration_ms for e in entries) / 1000, 1),
            "rows": [{"ts": e.ts, "provider": e.provider.value, "endpoint_or_model": e.endpoint_or_model,
                      "credits": e.credits, "tokens_in": e.tokens_in, "tokens_out": e.tokens_out,
                      "cost_inr": e.cost_inr, "ms": e.duration_ms, "ok": e.ok, "error": e.error}
                     for e in entries]}
