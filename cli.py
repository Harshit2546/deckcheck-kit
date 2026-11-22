"""Command line entry point: `run` starts a new deck check, `resume` continues one after a kill.
With --out, the D3 result JSON (io/adapter.py to_kit) and the Markdown report are written.

Called by: humans, tests, the demo script. Calls: core/config.py, core/store.py,
core/runner.py, core/log.py, core/adapter_loader.py (io/adapter.py).
Examples:
  python cli.py run --request tests/decks/deck_a_request.json --out out/result.json
  python cli.py resume <run_id> --out out/result.json
  python cli.py run --deck deck.pdf --domain example.com --deck-date 2026-10-01
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core import runner, store
from core.adapter_loader import load_adapter
from core.config import DEFAULT_RULES, load_rules
from core.log import log_step
from core.models import Run, RunInput


def new_run_id() -> str:
    return "run-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="deckcheck", description="Check every claim in a pitch deck.")
    p.add_argument("--db", default=store.DEFAULT_DB, help="SQLite file (default: %(default)s)")
    p.add_argument("--rules", default=str(DEFAULT_RULES), help="rules.yaml path")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="start a new run, from a request JSON or from --deck/--domain")
    run.add_argument("--request", help="request JSON in the DECISIONS.md D3 format")
    run.add_argument("--deck", help="path to the deck PDF (text-based)")
    run.add_argument("--domain", help="company domain, e.g. example.com")
    run.add_argument("--deck-date", help="deck date YYYY-MM-DD; if missing, PDF metadata is used and flagged")
    run.add_argument("--founder-url", action="append", default=[], dest="founder_urls",
                     help="founder profile URL (repeatable)")
    run.add_argument("--out", help="write the D3 result JSON here, and the Markdown report next to it")

    res = sub.add_parser("resume", help="continue a run after a kill or crash")
    res.add_argument("run_id")
    res.add_argument("--out", help="write the D3 result JSON here, and the Markdown report next to it")
    return p


def _valid_date(text: str) -> str:
    datetime.strptime(text, "%Y-%m-%d")
    return text


def _input_from_request(path: str) -> RunInput:
    """Read a D3 request file. A relative deck_path is looked up next to the request file
    first, then from the current folder (repo-relative paths like tests/decks/deck_a.pdf)."""
    request_file = Path(path)
    run_input = load_adapter().from_kit(json.loads(request_file.read_text(encoding="utf-8")))
    deck = Path(run_input.deck_path)
    if not deck.is_absolute():
        beside_request = request_file.parent / deck
        chosen = beside_request if beside_request.is_file() or not deck.is_file() else deck
        run_input.deck_path = str(chosen.resolve())
    return run_input


def _input_from_flags(args: argparse.Namespace) -> RunInput:
    deck_date = _valid_date(args.deck_date) if args.deck_date else None
    return RunInput(deck_path=args.deck, domain=args.domain.strip().lower(), deck_date=deck_date,
                    deck_date_source="input" if deck_date else "missing",
                    founder_urls=args.founder_urls)


def write_result(conn: sqlite3.Connection, run_id: str, out: str) -> bool:
    """Write the D3 result JSON to `out` and the Markdown report to the same name with .md.
    Returns False if the run has no report yet."""
    saved = store.get_report(conn, run_id)
    if saved is None:
        log_step(run_id, None, "cli.out", "skipped", note="no report yet; resume to finish the run")
        return False
    report_json, report_md = saved
    company = (store.get_resolution(conn, run_id) or {}).get("company")
    actions = store.list_actions(conn, run_id)
    result = load_adapter().to_kit(report_json, company=company,
                                   founder_email=actions[0] if actions else None)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    out_path.with_suffix(".md").write_text(report_md, encoding="utf-8")
    log_step(run_id, None, "cli.out", "written", json=str(out_path),
             markdown=str(out_path.with_suffix(".md")))
    return True


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        if args.request and (args.deck or args.domain):
            parser.error("use either --request or --deck/--domain, not both")
        if not args.request and not (args.deck and args.domain):
            parser.error("give --request, or both --deck and --domain")

    rules = load_rules(args.rules)
    conn = store.connect(args.db)

    if args.command == "run":
        try:
            run_input = _input_from_request(args.request) if args.request else _input_from_flags(args)
        except (OSError, ValueError) as e:
            log_step(None, None, "cli.run", "error", error=str(e))
            return 2
        if not Path(run_input.deck_path).is_file():
            log_step(None, None, "cli.run", "error", error=f"deck not found: {run_input.deck_path}")
            return 2
        run = Run(id=new_run_id(), input=run_input)
        store.insert_run(conn, run)
        log_step(run.id, None, "cli.run", "created", deck=run_input.deck_path,
                 domain=run_input.domain)
        done = runner.start(conn, rules, run.id)
        run_id = run.id
    else:
        run_id = args.run_id
        if store.get_run(conn, run_id) is None:
            log_step(run_id, None, "cli.resume", "error", error="unknown run id")
            return 2
        done = runner.resume(conn, rules, run_id)

    if args.out:
        write_result(conn, run_id, args.out)
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
