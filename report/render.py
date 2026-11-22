"""Renders the report dict from report/builder.py as Markdown for humans (and the founder-email appendix).

Who calls it: report/builder.py only. What it calls: nothing (pure string formatting, no I/O).
The claim table columns follow rules.yaml output.fields, so the hour-3 change can add a column with a config edit.
"""

from __future__ import annotations

from typing import Any

_ORDER = ["SUPPORTED", "CONTRADICTED", "NOT_COMPARABLE", "CANNOT_VERIFY", "HELD", "PENDING"]


def _cell(value: Any) -> str:
    """One Markdown table cell: sources become 'type field (record date)', pipes and newlines are escaped."""
    if isinstance(value, list):
        value = "; ".join(_source_text(v) if isinstance(v, dict) else str(v) for v in value)
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _source_text(src: dict[str, Any]) -> str:
    date = f", record {src['record_date']}" if src.get("record_date") else ""
    return f"{src['source_type']} {src['locator']} [{src['field_or_quote']}]{date}, retrieved {src['retrieved_at']}"


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return lines


def render_markdown(report: dict[str, Any], claim_fields: list[str]) -> str:
    run, summary = report["run"], report["summary"]
    out = [f"# DeckCheck report: {run['domain']}", "",
           f"Run `{run['id']}` · deck `{run['deck_path']}` · deck date {run['deck_date'] or 'unknown'} "
           f"({run['deck_date_source']}) · generated {report['generated_at']}", "",
           "_Decision support for a human reviewer. A verdict is not an automatic rejection._", "",
           "## Summary", ""]
    out += _table(["Verdict", "Claims"], [[k, summary["by_label"].get(k, 0)] for k in _ORDER
                                           if summary["by_label"].get(k, 0) or k != "PENDING"])
    out += [""] + [f"- **Note:** {f}" for f in summary["flags"]] + ([""] if summary["flags"] else [])

    out += ["## Red flags (contradicted claims, most material first)", ""]
    flags = report["red_flags"]
    out += _table(["Slide", "Type", "Materiality", "Confidence", "What we found", "Sources"],
                  [[f["slide"], f["type"], f["materiality"], f["confidence"], f["explanation"], f["sources"]]
                   for f in flags]) if flags else ["None."]

    out += ["", "## Claims", ""]
    out += _table(claim_fields, [[c[f] for f in claim_fields] for c in report["claims"]])

    out += ["", "## Questions for the founders", ""]
    out += [f"{i}. {q['question']}" for i, q in enumerate(report["founder_questions"], 1)] or ["None."]

    out += ["", "## Evidence requests", ""]
    out += [f"- {r['request']}" for r in report["evidence_requests"]] or ["None."]

    out += ["", "## Not checked (HELD)", ""]
    out += [f"- {h['note']}" for h in report["held"]] or ["None."]

    led = report["ledger"]
    out += ["", "## Run cost", "",
            f"{led['calls']} external calls ({led['failed']} failed), {led['credits']:g} credits, "
            f"INR {led['cost_inr']:.2f}, {led['duration_ms'] / 1000:.1f} s of call time.", ""]
    out += _table(["Provider", "Calls", "Failed", "Credits", "Cost INR"],
                  [[p, v["calls"], v["failed"], f"{v['credits']:g}", f"{v['cost_inr']:.2f}"]
                   for p, v in sorted(led["by_provider"].items())]) if led["by_provider"] else []
    return "\n".join(out) + "\n"
