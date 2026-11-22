"""DeckCheck Streamlit UI: Run, Claims, Approvals, Inbox and Ledger pages.

Run from the repo root: streamlit run ui/app.py
Called by: humans (the demo). Calls: ui/data.py, actions/email.py, core/store.py, core/config.py.
Shows what the pipeline stored; it never writes claims, evidence or verdicts. The founder email
is approved or rejected only by a human click here, then sent by the exactly-once sender.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from core import store  # noqa: E402
from core.config import load_rules  # noqa: E402
from ui import data  # noqa: E402

st.set_page_config(page_title="DeckCheck", layout="wide")

db_path = st.sidebar.text_input("Database file", str(ROOT / store.DEFAULT_DB))
conn = store.connect(db_path)
rules = load_rules()
PAGES = ["Run"]
page = st.sidebar.radio("Page", PAGES)


def pick_run(label: str = "Run") -> str | None:
    runs = store.list_runs(conn)
    if not runs:
        st.info("No runs yet. Start one on the Run page.")
        return None
    return st.selectbox(label, [r.id for r in runs],
                        format_func=lambda rid: f"{rid} ({store.get_run(conn, rid).state.value})")


def page_run() -> None:
    st.header("Run")
    st.caption("Start a deck check. The run happens in the background; press Refresh to follow it.")
    mode = st.radio("Start from", ["Request file in repo", "Upload D3 request", "Deck + domain + date"],
                    horizontal=True)
    run_input = None
    try:
        if mode == "Request file in repo":
            files = data.request_files()
            if not files:
                st.warning("No request files in tests/decks or tests/requests.")
            else:
                chosen = st.selectbox("Request", files, format_func=lambda p: str(p.relative_to(ROOT)))
                if st.button("Start run", type="primary"):
                    run_input = data.input_from_request_file(chosen)
        elif mode == "Upload D3 request":
            req = st.file_uploader("Request JSON (DECISIONS.md D3)", type=["json"])
            deck = st.file_uploader("Deck PDF (optional; otherwise deck_path in the request)", type=["pdf"])
            if req and st.button("Start run", type="primary"):
                import json
                override = data.save_upload(deck.name, deck.getvalue()) if deck else None
                run_input = data.input_from_request(json.loads(req.getvalue()), ROOT, override)
        else:
            deck = st.file_uploader("Deck PDF", type=["pdf"])
            domain = st.text_input("Company domain", placeholder="locus.sh")
            deck_date = st.text_input("Deck date (YYYY-MM-DD, blank = read from the PDF)")
            urls = st.text_area("Founder profile URLs (one per line, optional)")
            if deck and domain and st.button("Start run", type="primary"):
                run_input = data.input_from_form(data.save_upload(deck.name, deck.getvalue()), domain,
                                                 deck_date.strip() or None,
                                                 [u.strip() for u in urls.splitlines() if u.strip()])
        if run_input is not None:
            run_id = data.create_run(conn, run_input)
            data.launch(db_path, run_id)
            st.success(f"Started {run_id}")
    except ValueError as e:
        st.error(str(e))

    st.subheader("Runs")
    st.button("Refresh")
    rows = data.run_rows(conn)
    if not rows:
        st.info("No runs yet.")
        return
    st.dataframe(rows, use_container_width=True, hide_index=True)
    unfinished = [r["run_id"] for r in rows if r["state"] != "done"]
    if unfinished:
        rid = st.selectbox("Resume a run that stopped", unfinished)
        if st.button("Resume"):
            data.launch(db_path, rid)
            st.success(f"Resuming {rid}: finished steps and claims are skipped.")


PAGE_FUNCS = {"Run": page_run}
PAGE_FUNCS[page]()
