"""Builds the DeckCheck report from stored claims, verdicts, evidence and the ledger (T15).

Who calls it: core/runner.py stage `report` (D7: build(conn, rules, run_id) -> (json dict, markdown str)).
What it calls: core.store (read only), core.config.rule, report/render.py, report/question_templates.yaml.
No LLM here: wording comes from verdict explanations and the templates; ordering uses rules.yaml materiality.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import yaml

from core import store
from core.config import rule
from core.models import Claim, Confidence, Evidence, Verdict, VerdictLabel, now_iso
from report.render import render_markdown

TEMPLATES_PATH = Path(__file__).resolve().parent / "question_templates.yaml"
_CONF_RANK = {Confidence.HIGH: 2, Confidence.MEDIUM: 1, Confidence.LOW: 0}
# Every field a claim row can show; rules.yaml output.fields must be a list of these (checked before any row is built).
ROW_FIELDS = ("claim_id", "slide", "quote", "type", "subject", "metric", "value", "unit", "as_of", "label",
              "reason_code", "explanation", "confidence", "missing", "sources", "evidence_ids", "materiality")


def _source(ev: Evidence) -> dict[str, Any]:
    return {"source_type": ev.source_type.value, "locator": ev.locator, "field_or_quote": ev.field_or_quote,
            "value": ev.value, "record_date": ev.record_date, "retrieved_at": ev.retrieved_at, "call_id": ev.call_id}


def _fields(claim: Claim, verdict: Verdict | None, sources: list[dict[str, Any]], weight: float) -> dict[str, Any]:
    """Every field a report row may show. rules.yaml output.fields picks and orders from these."""
    return {
        "claim_id": claim.id, "slide": claim.slide, "quote": claim.quote, "type": claim.type.value,
        "subject": claim.subject, "metric": claim.metric, "value": claim.value, "unit": claim.unit,
        "as_of": claim.as_of, "label": verdict.label.value if verdict else "PENDING",
        "reason_code": verdict.reason_code if verdict else None,
        "explanation": verdict.explanation if verdict else None,
        "confidence": verdict.confidence.value if verdict else None,
        "missing": verdict.missing if verdict else None, "sources": sources,
        "evidence_ids": list(verdict.evidence_ids) if verdict else [], "materiality": weight,
    }


def _check_fields(wanted: list[str]) -> None:
    unknown = [f for f in wanted if f not in ROW_FIELDS]
    if unknown:
        raise ValueError(f"config/rules.yaml output.fields has unknown field(s) {unknown}; "
                         f"report/builder.py can show: {list(ROW_FIELDS)}")


def _load_templates(path: Path = TEMPLATES_PATH) -> dict[str, dict[str, str]]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    for section in ("founder_questions", "evidence_requests", "held_notes"):
        if "default" not in (data.get(section) or {}):
            raise ValueError(f"{path}: section '{section}' needs a 'default' template")
    return data


def _fill(templates: dict[str, str], row: dict[str, Any], section: str) -> str:
    template = templates.get(row["type"], templates["default"])
    try:
        return template.format(**{k: ("" if v is None else v) for k, v in row.items()})
    except KeyError as exc:
        raise ValueError(f"{TEMPLATES_PATH}: unknown placeholder {exc} in section '{section}'") from exc


def _flag_order(row: dict[str, Any]) -> tuple[Any, ...]:
    return (-row["materiality"], -_CONF_RANK[Confidence(row["confidence"])], row["slide"], row["claim_id"])


def _ledger_summary(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    entries = store.list_ledger(conn, run_id)
    by_provider: dict[str, dict[str, float]] = {}
    for e in entries:
        p = by_provider.setdefault(e.provider.value, {"calls": 0, "failed": 0, "credits": 0.0, "cost_inr": 0.0,
                                                      "tokens_in": 0, "tokens_out": 0})
        p["calls"] += 1
        p["failed"] += 0 if e.ok else 1
        p["credits"] += e.credits
        p["cost_inr"] += e.cost_inr
        p["tokens_in"] += e.tokens_in
        p["tokens_out"] += e.tokens_out
    totals = store.ledger_totals(conn, run_id)
    return {"calls": int(totals["calls"]), "failed": int(totals["failed"]), "credits": totals["credits"],
            "cost_inr": round(totals["cost_inr"], 2), "duration_ms": sum(e.duration_ms for e in entries),
            "by_provider": by_provider}


def _run_flags(run: Any, rows: list[dict[str, Any]]) -> list[str]:
    flags = []
    if run.input.deck_date_source != "input":
        flags.append(f"Deck date came from {run.input.deck_date_source} ({run.input.deck_date or 'unknown'}), "
                     "not from the user; confidence is capped at medium.")
    pending = sum(1 for r in rows if r["label"] == "PENDING")
    if pending:
        flags.append(f"{pending} claim(s) have no verdict yet; this report is incomplete.")
    held = sum(1 for r in rows if r["label"] == VerdictLabel.HELD.value)
    if held:
        flags.append(f"{held} claim(s) are HELD (limit, timeout or error); they were not checked.")
    return flags


def build(conn: sqlite3.Connection, rules: dict[str, Any], run_id: str) -> tuple[dict[str, Any], str]:
    """Return (report JSON, report Markdown) for one run. Read-only on the database."""
    run = store.get_run(conn, run_id)
    if run is None:
        raise ValueError(f"unknown run {run_id}")
    templates = _load_templates()
    wanted = list(rule(rules, "output.fields"))
    _check_fields(wanted)
    rows: list[dict[str, Any]] = []
    for claim in store.list_claims(conn, run_id):
        sources = [_source(e) for e in store.list_evidence(conn, claim.id)]
        weight = float(rule(rules, f"materiality.{claim.type.value}"))
        rows.append(_fields(claim, store.get_verdict(conn, claim.id), sources, weight))

    flagged = sorted((r for r in rows if r["label"] == VerdictLabel.CONTRADICTED.value), key=_flag_order)
    asks = [r for r in rows if r["label"] in (VerdictLabel.CANNOT_VERIFY.value, VerdictLabel.NOT_COMPARABLE.value)]
    held = [r for r in rows if r["label"] == VerdictLabel.HELD.value]
    counts = {lab.value: sum(1 for r in rows if r["label"] == lab.value) for lab in VerdictLabel}
    counts["PENDING"] = sum(1 for r in rows if r["label"] == "PENDING")

    report = {
        "run": {"id": run.id, "deck_path": run.input.deck_path, "domain": run.input.domain,
                "deck_date": run.input.deck_date, "deck_date_source": run.input.deck_date_source,
                "state": run.state.value},
        "generated_at": now_iso(),
        "summary": {"claims": len(rows), "by_label": counts, "flags": _run_flags(run, rows)},
        "red_flags": [{"claim_id": r["claim_id"], "slide": r["slide"], "type": r["type"], "label": r["label"],
                       "confidence": r["confidence"], "materiality": r["materiality"],
                       "reason_code": r["reason_code"], "explanation": r["explanation"], "sources": r["sources"]}
                      for r in flagged],
        "claims": [{f: r[f] for f in wanted} for r in rows],
        "founder_questions": [{"claim_id": r["claim_id"], "slide": r["slide"],
                               "question": _fill(templates["founder_questions"], r, "founder_questions")}
                              for r in flagged],
        "evidence_requests": [{"claim_id": r["claim_id"], "slide": r["slide"], "type": r["type"], "label": r["label"],
                               "reason_code": r["reason_code"], "missing": r["missing"],
                               "request": _fill(templates["evidence_requests"], r, "evidence_requests")}
                              for r in asks],
        "held": [{"claim_id": r["claim_id"], "slide": r["slide"], "type": r["type"], "reason_code": r["reason_code"],
                  "missing": r["missing"], "note": _fill(templates["held_notes"], r, "held_notes")} for r in held],
        "ledger": _ledger_summary(conn, run_id),
    }
    return report, render_markdown(report, wanted)
