"""Eval runner (T21): compares what DeckCheck decides for a test deck with the answer key, per claim.

Offline (default): runs the REAL runner, resolve stage, checkers and verdict engine on the recorded claims of a deck
(tests/eval/<deck>_claims.json, what extraction should produce) with ONLY sources.crust.get_company replaced by the
recorded Crustdata response (tests/fixtures/crustdata/<deck>_*_company.json). No network, no credits: web search,
web fetch and the quote-picking LLM call are blocked (no_live_web), so web claims come out HELD even with a key in .env.
--live: runs `python cli.py run --request <deck>_request.json` for real (LLM and Crustdata credits are spent).
Who calls it: humans and CI (`python tests/eval/run_eval.py`). Exit code 0 = no FAIL, 1 = at least one FAIL, 2 = harness error.
Fixtures live in tests/ only; this script is never imported by the pipeline.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core import ledger, runner, store  # noqa: E402
from core.config import load_rules  # noqa: E402
from core.models import Claim, ClaimType, Provider, Run, RunInput  # noqa: E402

DECKS = ROOT / "tests" / "decks"
EVAL = ROOT / "tests" / "eval"
FIXTURES = ROOT / "tests" / "fixtures" / "crustdata"


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_key(deck: str) -> list[dict[str, Any]]:
    with open(DECKS / f"deck_{deck}_answers.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or []


def _norm(text: str) -> str:
    return " ".join(str(text).split())


def compare(expected: dict[str, Any], actual: dict[str, Any] | None) -> str:
    """PASS when verdict and reason code both equal the key; SKIP for TBD; FAIL otherwise (also when nothing ran)."""
    if str(expected.get("expected_verdict")).upper() == "TBD":
        return "SKIP"
    if actual is None:
        return "FAIL"
    same_reason = expected.get("expected_reason_code") in (None, actual["reason_code"])
    return "PASS" if actual["verdict"] == expected["expected_verdict"] and same_reason else "FAIL"


def match_actual(row: dict[str, Any], actuals: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The actual verdict for a key row: same slide and same quote (whitespace-insensitive)."""
    for a in actuals:
        if a["slide"] == row["slide"] and _norm(a["quote"]) == _norm(row["quote"]):
            return a
    return None


# ------------------------------------------------------------------ offline replay

@contextmanager
def recorded_company(path: Path) -> Iterator[None]:
    """Replace sources.crust.get_company by the recorded response, shaped like the real function's return value."""
    import sources.crust as crust

    records = _load_json(path)[0]["matches"]
    payload = records[0]["company_data"] if records else {}
    original = crust.get_company

    written: set[str] = set()

    def fake(ctx: Any, domain: str) -> tuple[dict[str, Any], str]:
        if ctx.run.id not in written:   # evidence.call_id is a foreign key: the replayed call gets one ledger row, 0 credits
            ledger.record(ctx.conn, ctx.rules, ctx.run.id, Provider.CRUSTDATA, f"recorded:{path.name}",
                          duration_ms=0, ok=True, credits=0.0, call_id="call-fixture")
            written.add(ctx.run.id)
        return deepcopy(payload), "call-fixture"

    crust.get_company = fake
    try:
        yield
    finally:
        crust.get_company = original


class OfflineWebBlocked(RuntimeError):
    """Raised when an offline replay reaches a web or LLM call; the runner turns it into HELD error."""


@contextmanager
def no_live_web() -> Iterator[list[str]]:
    """Block sources.web.search/fetch and extract.quotes.pick_quote for the offline replay.

    The offline eval must never spend credits, even when .env holds a key. There is no recorded web
    response yet, so web claims come out HELD (error); the yielded list names every blocked call.
    """
    import extract.quotes as quotes
    import sources.web as web

    blocked: list[str] = []
    originals = {(web, "search"): web.search, (web, "fetch"): web.fetch, (quotes, "pick_quote"): quotes.pick_quote}

    def make_block(name: str) -> Any:
        def block(*_args: Any, **_kwargs: Any) -> Any:
            blocked.append(name)
            raise OfflineWebBlocked(f"offline eval: {name} is blocked (no recorded web response)")
        return block

    for module, name in originals:
        setattr(module, name, make_block(f"{module.__name__}.{name}"))
    try:
        yield blocked
    finally:
        for (module, name), original in originals.items():
            setattr(module, name, original)


def check_quotes(deck_pdf: Path, claims: list[dict[str, Any]]) -> list[str]:
    """Problems found when the recorded claims are checked against the real PDF text (empty list = all quotes found)."""
    from extract.claims import verify_claim_quote
    from extract.pdf import extract_pdf_slides

    slides = extract_pdf_slides(deck_pdf)
    return [f"slide {c['slide']}: quote not found on the slide: {c['quote']!r}"
            for c in claims if not verify_claim_quote(c["quote"], slides.get(c["slide"], ""))]


def run_offline(deck: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(actual verdict rows, info) from a full offline run. Raises if a fixture file is missing."""
    request = _load_json(DECKS / f"deck_{deck}_request.json")
    recorded = _load_json(EVAL / f"deck_{deck}_claims.json")
    company = next(iter(sorted(FIXTURES.glob(f"deck_{deck}_*_company.json"))), None)
    if company is None:
        raise FileNotFoundError(f"no recorded company response tests/fixtures/crustdata/deck_{deck}_*_company.json")
    rules = load_rules()
    with tempfile.TemporaryDirectory() as tmp:
        conn = store.connect(Path(tmp) / "eval.db")
        run = Run(id=f"eval_{deck}", input=RunInput(deck_path=str(ROOT / request["deck_path"]),
                                                    domain=request["company_domain"], deck_date=request["deck_date"]))
        store.insert_run(conn, run)

        def fake_extract(ctx: Any) -> list[Claim]:
            return [Claim(id="x", run_id=ctx.run.id, slide=c["slide"], quote=c["quote"], type=ClaimType(c["type"]),
                          subject=c["subject"], metric=c["metric"], value=c["value"], unit=c["unit"], as_of=c["as_of"])
                    for c in recorded]

        with recorded_company(company), no_live_web() as blocked_calls:
            done = runner.start(conn, rules, run.id, stages={"extract": fake_extract})
        final = store.get_run(conn, run.id)
        rows = []
        for claim in store.list_claims(conn, run.id):
            v = store.get_verdict(conn, claim.id)
            rows.append({"slide": claim.slide, "quote": claim.quote, "claim_type": claim.type.value,
                         "verdict": v.label.value if v else "NONE", "reason_code": v.reason_code if v else None,
                         "confidence": v.confidence.value if v else None})
        info = {"done": done, "state": final.state.value if final else "?", "error": final.error if final else None,
                "problems": check_quotes(ROOT / request["deck_path"], recorded),
                "blocked_web_calls": list(blocked_calls)}
        conn.close()
    return rows, info


# ------------------------------------------------------------------ live run

def run_live(deck: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run cli.py for real on the deck's request file and read the D3 result JSON. Spends credits."""
    request = DECKS / f"deck_{deck}_request.json"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "result.json"
        cmd = [sys.executable, str(ROOT / "cli.py"), "--db", str(Path(tmp) / "live.db"),
               "run", "--request", str(request), "--out", str(out)]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if not out.exists():
            raise RuntimeError(f"cli.py wrote no result (exit {proc.returncode}): {proc.stderr[-600:]}")
        result = _load_json(out)
    rows = [{"slide": c["slide"], "quote": c["quote"], "claim_type": c.get("type"), "verdict": c["verdict"],
             "reason_code": c.get("reason_code"), "confidence": c.get("confidence")} for c in result.get("claims", [])]
    return rows, {"done": proc.returncode == 0, "state": f"exit {proc.returncode}", "error": None, "problems": []}


# ------------------------------------------------------------------ report

def evaluate(deck: str, live: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Result rows (key row + actual + status) and run info."""
    key = load_key(deck)
    actuals, info = (run_live if live else run_offline)(deck)
    rows = []
    for row in key:
        actual = match_actual(row, actuals)
        rows.append({**row, "actual": actual, "status": compare(row, actual)})
    return rows, info


def render(deck: str, rows: list[dict[str, Any]], info: dict[str, Any], live: bool) -> str:
    mode = ("LIVE (cli.py, credits spent)" if live
            else "offline replay (real runner, resolve, checkers, engine; recorded company response)")
    lines = [f"Deck {deck.upper()}: {mode}",
             f"run state: {info['state']}" + (f", error: {info['error']}" if info["error"] else "")]
    lines += [f"WARNING {p}" for p in info["problems"]]
    if info.get("blocked_web_calls"):
        lines.append(f"NOTE offline: {len(info['blocked_web_calls'])} web/LLM call(s) blocked, no credits spent; "
                     "web claims are HELD here (use --live to check them)")
    lines.append(f"{'slide':<6}{'status':<7}{'expected':<44}actual")
    for r in rows:
        a = r["actual"]
        exp = f"{r['expected_verdict']} / {r['expected_reason_code']}"
        act = f"{a['verdict']} / {a['reason_code']} ({a['confidence']})" if a else "no verdict"
        lines.append(f"{r['slide']:<6}{r['status']:<7}{exp:<44}{act}")
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in ("PASS", "FAIL", "SKIP")}
    scored = counts["PASS"] + counts["FAIL"]
    pct = f"{100 * counts['PASS'] / scored:.0f}%" if scored else "n/a"
    lines.append(f"Summary: {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['SKIP']} SKIP; "
                 f"accuracy {pct} of {scored} scored claims")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare DeckCheck verdicts with the answer key of a test deck.")
    ap.add_argument("--deck", default="a", help="deck letter (default: a)")
    ap.add_argument("--live", action="store_true",
                    help="run cli.py for real instead of the offline replay (spends credits)")
    args = ap.parse_args(argv)
    try:
        rows, info = evaluate(args.deck, live=args.live)
    except (OSError, RuntimeError, ValueError) as exc:
        sys.stderr.write(f"eval harness error: {exc}\n")
        return 2
    sys.stdout.write(render(args.deck, rows, info, args.live) + "\n")
    return 1 if any(r["status"] == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
