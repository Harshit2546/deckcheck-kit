"""Command line entry point: `run` starts a new deck check, `resume` continues one after a kill.

Called by: humans, tests, the demo script. Calls: core/config.py, core/store.py,
core/runner.py, core/log.py.
Example: python cli.py run --deck tests/decks/deck_a.pdf --domain example.com --deck-date 2026-10-01
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core import runner, store
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

    run = sub.add_parser("run", help="start a new run on a deck")
    run.add_argument("--deck", required=True, help="path to the deck PDF (text-based)")
    run.add_argument("--domain", required=True, help="company domain, e.g. example.com")
    run.add_argument("--deck-date", help="deck date YYYY-MM-DD; if missing, PDF metadata is used and flagged")
    run.add_argument("--founder-url", action="append", default=[], dest="founder_urls",
                     help="founder profile URL (repeatable)")

    res = sub.add_parser("resume", help="continue a run after a kill or crash")
    res.add_argument("run_id")
    return p


def _valid_date(text: str) -> str:
    datetime.strptime(text, "%Y-%m-%d")
    return text


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rules = load_rules(args.rules)
    conn = store.connect(args.db)

    if args.command == "run":
        if not Path(args.deck).is_file():
            log_step(None, None, "cli.run", "error", error=f"deck not found: {args.deck}")
            return 2
        deck_date = _valid_date(args.deck_date) if args.deck_date else None
        run = Run(id=new_run_id(), input=RunInput(
            deck_path=args.deck, domain=args.domain.strip().lower(), deck_date=deck_date,
            deck_date_source="input" if deck_date else "missing",
            founder_urls=args.founder_urls))
        store.insert_run(conn, run)
        log_step(run.id, None, "cli.run", "created", deck=args.deck, domain=run.input.domain)
        return 0 if runner.start(conn, rules, run.id) else 1

    if store.get_run(conn, args.run_id) is None:
        log_step(args.run_id, None, "cli.resume", "error", error="unknown run id")
        return 2
    return 0 if runner.resume(conn, rules, args.run_id) else 1


if __name__ == "__main__":
    sys.exit(main())
