"""UI data helpers: everything ui/app.py shows or does, as plain functions (no Streamlit here),
so the pages stay thin and tests can call these directly.

Called by: ui/app.py, tests/ui/. Calls: core/store.py, core/adapter_loader.py (io/adapter.py),
report/builder.py (ROW_FIELDS only), cli.py (as a background process to run or resume a run).
Never writes claims, evidence or verdicts: only a new run row, and email approval through actions/.
"""

from __future__ import annotations

import csv
import io
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
from core.config import rule
from core.models import RUN_ORDER, ActionStatus, ClaimState, Run, RunInput, RunState
from report.builder import ROW_FIELDS

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
        # Beside the request first, then from the repo root (repo-relative paths such as
        # tests/decks/deck_a.pdf), the same lookup cli.py uses (INCIDENTS A2).
        beside = base_dir / run_input.deck_path
        from_root = ROOT / run_input.deck_path
        chosen = beside if beside.is_file() or not from_root.is_file() else from_root
        run_input.deck_path = str(chosen.resolve())
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


def claim_rows(conn: sqlite3.Connection, run_id: str,
               rules: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Each claim with its verdict, sources and check result, read only from the store.
    Also carries every report field (report/builder.py ROW_FIELDS) so rules.yaml output.fields
    can pick the Claims-table columns."""
    rows = []
    for claim in store.list_claims(conn, run_id):
        v = store.get_verdict(conn, claim.id)
        evidence = store.list_evidence(conn, claim.id)
        sources = [{"source_type": e.source_type.value, "url_or_endpoint": e.locator,
                    "is_url": _is_url(e.locator), "field_or_quote": e.field_or_quote, "value": e.value,
                    "record_date": e.record_date, "retrieved_at": e.retrieved_at, "call_id": e.call_id}
                   for e in evidence]
        result = store.get_check_result(conn, claim.id)
        materiality = None
        if rules is not None:
            materiality = (rules.get("materiality") or {}).get(claim.type.value)
        rows.append({"claim_id": claim.id, "slide": claim.slide, "type": claim.type.value,
                     "subject": claim.subject, "metric": claim.metric, "as_of": claim.as_of,
                     "quote": claim.quote, "claimed_value": claim.value, "value": claim.value,
                     "unit": claim.unit, "state": claim.state.value,
                     "verdict": v.label.value if v else "PENDING",
                     "label": v.label.value if v else "PENDING",
                     "confidence": v.confidence.value if v else None,
                     "reason_code": v.reason_code if v else None,
                     "explanation": v.explanation if v else None,
                     "missing": v.missing if v else None, "sources": sources,
                     "evidence_ids": list(v.evidence_ids) if v else [], "materiality": materiality,
                     "checked": result is not None,
                     "observed": result.observed if result else {},
                     "comparable": result.comparable if result else None,
                     "held_reason": result.held_reason if result else None})
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
    by_provider: dict[str, dict[str, Any]] = {}
    for e in entries:
        p = by_provider.setdefault(e.provider.value, {"provider": e.provider.value, "calls": 0, "failed": 0,
                                                      "credits": 0.0, "cost_inr": 0.0, "seconds": 0.0})
        p["calls"] += 1
        p["failed"] += 0 if e.ok else 1
        p["credits"] += e.credits
        p["cost_inr"] = round(p["cost_inr"] + e.cost_inr, 2)
        p["seconds"] = round(p["seconds"] + e.duration_ms / 1000, 1)
    return {"calls": int(totals["calls"]), "failed": int(totals["failed"]),
            "credits": totals["credits"], "cost_inr": round(totals["cost_inr"], 2),
            "seconds": round(sum(e.duration_ms for e in entries) / 1000, 1),
            "by_provider": sorted(by_provider.values(), key=lambda p: p["provider"]),
            "rows": [{"call_id": e.id, "ts": e.ts, "provider": e.provider.value,
                      "endpoint_or_model": e.endpoint_or_model,
                      "credits": e.credits, "tokens_in": e.tokens_in, "tokens_out": e.tokens_out,
                      "cost_inr": e.cost_inr, "ms": e.duration_ms, "ok": e.ok, "error": e.error}
                     for e in entries]}


def ledger_csv(conn: sqlite3.Connection, run_id: str) -> str:
    """Every ledger row of a run as CSV (PLAN section 7: ledger table + CSV export)."""
    rows = ledger_summary(conn, run_id)["rows"]
    out = io.StringIO()
    fields = ["call_id", "ts", "provider", "endpoint_or_model", "credits", "tokens_in", "tokens_out",
              "cost_inr", "ms", "ok", "error"]
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def limits_used(rules: dict[str, Any], summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Ledger totals next to the rules.yaml limits the runner enforces."""
    lim = rules.get("limits") or {}
    out = []
    for label, key, used in (("Cost (INR)", "max_cost_inr", summary["cost_inr"]),
                             ("Credits", "max_credits", summary["credits"])):
        if key in lim and lim[key]:
            out.append({"limit": label, "used": used, "max": lim[key],
                        "share": min(1.0, float(used) / float(lim[key]))})
    return out


# ---------- Run progress ----------

def run_progress(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    """Where a run is: its state in RUN_ORDER and how many claims reached each claim state."""
    run = store.get_run(conn, run_id)
    if run is None:
        raise ValueError(f"unknown run {run_id}")
    claims = store.list_claims(conn, run_id)
    by_state = {s.value: sum(1 for c in claims if c.state == s) for s in ClaimState}
    order = [s.value for s in RUN_ORDER]
    return {"state": run.state.value, "order": order,
            "index": order.index(run.state.value) if run.state.value in order else -1,
            "failed": run.state == RunState.FAILED, "error": run.error,
            "claims": len(claims), "claims_by_state": by_state,
            "finished": run.state == RunState.DONE}


# ---------- Report page ----------

def report_view(conn: sqlite3.Connection, run_id: str) -> tuple[dict[str, Any], str] | None:
    """The report the runner stored at its `report` stage (report/builder.py), or None if not built yet.
    The UI shows the stored report as is; it never rebuilds it. Missing sections (an older or partial
    report) are filled with empty defaults so a page never fails on a stored report's shape."""
    found = store.get_report(conn, run_id)
    if found is None:
        return None
    report, markdown = dict(found[0] or {}), found[1] or ""
    run = store.get_run(conn, run_id)
    report.setdefault("run", {})
    for key, value in (("id", run_id), ("domain", run.input.domain if run else ""),
                       ("deck_date", run.input.deck_date if run else None),
                       ("deck_date_source", run.input.deck_date_source if run else "unknown")):
        report["run"].setdefault(key, value)
    report.setdefault("generated_at", "")
    summary = report.setdefault("summary", {})
    summary.setdefault("by_label", {})
    summary.setdefault("flags", [])
    summary.setdefault("claims", sum(summary["by_label"].values()))
    for key in ("red_flags", "claims", "founder_questions", "evidence_requests", "held"):
        report.setdefault(key, [])
    led = report.setdefault("ledger", {})
    for key, value in (("calls", 0), ("failed", 0), ("credits", 0.0), ("cost_inr", 0.0),
                       ("duration_ms", 0), ("by_provider", {})):
        led.setdefault(key, value)
    return report, markdown


# ---------- Entities ----------

_ENTITY_FIELDS = ("name", "id", "identity", "confidence", "identity_signals", "signals", "reason",
                  "profile_url", "call_id")


def entities_view(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    """What resolve/entities.py matched: the company and each founder, professional fields only."""
    found = store.get_resolution(conn, run_id)
    if found is None:
        return None

    def clean(entity: dict[str, Any] | None, role: str) -> dict[str, Any]:
        entity = entity or {}
        row = {"role": role, **{k: entity.get(k) for k in _ENTITY_FIELDS}}
        row["signals"] = ", ".join(row["signals"] or [])
        return row

    company = found.get("company")
    return {"company": clean(company, "company") if company else None,
            "founders": [clean(f, "founder") for f in found.get("founders") or []]}


# ---------- Claims table columns (rules.yaml output.fields) ----------

# D3 names in the kit output; the UI uses the same column names as the report.
DISPLAY_NAMES = {"label": "verdict", "value": "claimed_value"}


def claim_columns(rules: dict[str, Any]) -> list[str]:
    """Claims-table columns from rules.yaml output.fields, so an hour-3 field change shows in the UI with
    no code edit. Unknown names raise the same error report/builder.py raises."""
    wanted = list(rule(rules, "output.fields"))
    unknown = [f for f in wanted if f not in ROW_FIELDS]
    if unknown:
        raise ValueError(f"config/rules.yaml output.fields has unknown field(s) {unknown}; "
                         f"report/builder.py can show: {list(ROW_FIELDS)}")
    return wanted


def table_cell(value: Any) -> Any:
    """Flatten list/dict values (sources, evidence_ids) so st.dataframe can show them."""
    if isinstance(value, list):
        return "; ".join(f"{v.get('source_type', '')} {v.get('field_or_quote', '')}".strip()
                         if isinstance(v, dict) else str(v) for v in value)
    if isinstance(value, dict):
        return "; ".join(f"{k}: {v}" for k, v in value.items() if v not in (None, "", [], {}))
    return value


# ---------- Motion component payloads (ui/components) ----------

# claim.metric -> where checkers put the found number in CheckResult.observed (verdict/DESIGN.md section 3)
GAUGE_FOUND: dict[str, tuple[str, ...]] = {
    "headcount": ("headcount",),
    "total_raised": ("total_raised",),
    "round_amount": ("matched_round", "amount"),
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def gauge_payload(row: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any] | None:
    """Claimed vs found on one scale, with the tolerance band from rules.yaml. None when the claim has no
    found number, no claimed number or no tolerance for its type. Display only: the verdict label shown is the
    one verdict/engine.py stored; nothing here decides anything."""
    path = GAUGE_FOUND.get(row.get("metric") or "")
    if not path:
        return None
    found: Any = row.get("observed") or {}
    for part in path:
        found = found.get(part) if isinstance(found, dict) else None
    found_n, claimed_n = _number(found), _number(row.get("claimed_value"))
    tol = _number(((rules.get("tolerances") or {}).get(row.get("type") or "") or {}).get("tolerance_pct"))
    if found_n is None or claimed_n is None or claimed_n <= 0 or tol is None:
        return None
    return {"claimed": claimed_n, "found": found_n, "tol_pct": tol, "unit": row.get("unit") or "",
            "metric": row.get("metric"), "label": row.get("verdict") or "PENDING"}


def strip_payload(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per claim in slide order, for the slide strip and the claims landing row."""
    ordered = sorted(rows, key=lambda r: (r.get("slide") or 0, str(r.get("claim_id"))))
    return [{"claim_id": r["claim_id"], "slide": r.get("slide"), "type": r.get("type"),
             "label": r.get("verdict") or r.get("label") or "PENDING", "quote": r.get("quote") or ""}
            for r in ordered]


def route_payload(progress: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The run as a tracked route: checkpoints, where it is now, and one block per claim."""
    by = progress["claims_by_state"]
    n = progress["claims"]
    if progress["failed"]:
        status = f"Stopped with an error: {progress['error'] or 'no error text stored'}. Resume it below."
    elif progress["finished"]:
        status = f"Done. {n} claims decided."
    elif n:
        status = (f"At {progress['state']}. {by.get('decided', 0)} of {n} claims decided, "
                  f"{by.get('pending', 0)} not checked yet.")
    else:
        status = f"At {progress['state']}. Reading the deck."
    index = progress["index"]
    if progress["failed"] and index < 0:
        # 'failed' is not a checkpoint: place the marker where the stored claims show the run had got to
        reached = "created" if not n else "decided" if by.get("decided", 0) == n else "checking"
        index = progress["order"].index(reached)
    return {"order": progress["order"], "index": index, "failed": progress["failed"],
            "finished": progress["finished"], "status": status, "claims": strip_payload(rows)}
