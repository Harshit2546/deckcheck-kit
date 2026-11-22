"""DeckCheck Streamlit UI: Run, Report, Claims, Entities, Approvals, Inbox and Ledger pages.

Run from the repo root: streamlit run ui/app.py
Called by: humans (the demo). Calls: ui/data.py, actions/email.py, core/store.py, core/config.py.
Shows what the pipeline stored; it never writes claims, evidence or verdicts. The founder email
is approved or rejected only by a human click here, then sent by the exactly-once sender.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from core import store  # noqa: E402
from core.config import load_rules  # noqa: E402
from actions import email  # noqa: E402
from core.models import ActionStatus  # noqa: E402
from ui import data  # noqa: E402

st.set_page_config(page_title="DeckCheck", layout="wide")

PAGES = ["Run", "Report", "Claims", "Entities", "Approvals", "Inbox", "Ledger"]
# Text label always shown; colour only repeats it (Streamlit markdown colour names).
VERDICT_COLOUR = {"SUPPORTED": "green", "CONTRADICTED": "red", "HELD": "orange",
                  "NOT_COMPARABLE": "gray", "CANNOT_VERIFY": "gray", "PENDING": "gray"}
VERDICT_ORDER = ["CONTRADICTED", "HELD", "CANNOT_VERIFY", "NOT_COMPARABLE", "SUPPORTED", "PENDING"]

db_path = st.sidebar.text_input("Database file", str(ROOT / store.DEFAULT_DB))
conn = store.connect(db_path)
rules = load_rules()
page = st.sidebar.radio("Page", PAGES, key="page")
st.sidebar.caption("Decision support for a human reviewer. A verdict is not an automatic rejection.")


# ---------- shared helpers ----------

def go_to(target: str, run_id: str | None = None) -> None:
    """Button callback: switch page (and run) before the next rerun draws the sidebar."""
    st.session_state["page"] = target
    if run_id:
        st.session_state["current_run"] = run_id


def pick_run(label: str = "Run") -> str | None:
    """One run choice shared by every page (kept in session_state across page switches)."""
    runs = store.list_runs(conn)
    if not runs:
        st.info("No runs yet. Start one on the Run page.")
        return None
    ids = [r.id for r in runs]
    states = {r.id: r.state.value for r in runs}
    current = st.session_state.get("current_run")
    index = ids.index(current) if current in ids else 0
    rid = st.selectbox(label, ids, index=index, format_func=lambda r: f"{r} ({states[r]})")
    st.session_state["current_run"] = rid
    return rid


def badge(label: str | None) -> str:
    label = label or "PENDING"
    return f":{VERDICT_COLOUR.get(label, 'gray')}[**{label}**]"


def _cell(value: object) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def _sources_table(sources: list[dict]) -> str:
    """Markdown table; URL sources are clickable links, API endpoints are shown as code."""
    lines = ["| source | url_or_endpoint | field_or_quote | value | record_date | retrieved_at | call_id |",
             "|---|---|---|---|---|---|---|"]
    for s in sources:
        where = s.get("url_or_endpoint") or s.get("locator") or ""
        is_url = s.get("is_url", str(where).startswith(("http://", "https://")))
        where_md = f"[{_cell(where)}]({where})" if is_url else f"`{_cell(where)}`"
        lines.append(f"| {_cell(s.get('source_type'))} | {where_md} | {_cell(s.get('field_or_quote'))} | "
                     f"{_cell(s.get('value'))} | {_cell(s.get('record_date'))} | "
                     f"{_cell(s.get('retrieved_at'))} | {_cell(s.get('call_id'))} |")
    return "\n".join(lines)


def _kv_table(pairs: list[tuple[str, Any]]) -> str:
    lines = ["| field | value |", "|---|---|"]
    lines += [f"| {_cell(k)} | {_cell(v)} |" for k, v in pairs]
    return "\n".join(lines)


# ---------- Run ----------

def _progress_block() -> None:
    """Run state stepper and per-claim progress for the chosen run."""
    rid = pick_run("Follow run")
    if rid is None:
        return
    prog = data.run_progress(conn, rid)
    steps = []
    for i, name in enumerate(prog["order"]):
        if i < prog["index"] or prog["finished"]:
            steps.append(f":green[{name}]")
        elif i == prog["index"]:
            steps.append(f"**{name}**")
        else:
            steps.append(f":gray[{name}]")
    st.markdown("  →  ".join(steps))
    if prog["failed"]:
        st.error(f"Run failed: {prog['error'] or 'no error text stored'}. Resume it below.")
    n = prog["claims"]
    decided = prog["claims_by_state"].get("decided", 0)
    checked = prog["claims_by_state"].get("checked", 0)
    if n:
        st.progress(decided / n, text=f"{decided} of {n} claims decided · {checked} checked, "
                                      f"waiting for a verdict · {prog['claims_by_state'].get('pending', 0)} pending")
    else:
        st.caption("No claims extracted yet.")
    if prog["finished"]:
        st.button("Open the report", on_click=go_to, args=("Report", rid), type="primary")


def page_run() -> None:
    st.header("Run")
    st.caption("Start a deck check. It runs in the background; this page refreshes itself until the run is done.")
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
            st.session_state["current_run"] = run_id
            st.success(f"Started {run_id}")
    except ValueError as e:
        st.error(str(e))

    rows = data.run_rows(conn)
    live = any(r["state"] not in ("done", "failed") for r in rows)

    @st.fragment(run_every=3 if live else None)
    def live_part() -> None:
        st.subheader("Runs")
        fresh = data.run_rows(conn)
        if not fresh:
            st.info("No runs yet.")
            return
        st.dataframe(fresh, use_container_width=True, hide_index=True)
        st.subheader("Progress")
        _progress_block()

    live_part()
    unfinished = [r["run_id"] for r in rows if r["state"] != "done"]
    if unfinished:
        st.subheader("Resume")
        rid = st.selectbox("Resume a run that stopped", unfinished)
        if st.button("Resume"):
            data.launch(db_path, rid)
            st.success(f"Resuming {rid}: finished steps and claims are skipped.")


# ---------- Report ----------

def page_report() -> None:
    st.header("Report")
    rid = pick_run()
    if rid is None:
        return
    found = data.report_view(conn, rid)
    if found is None:
        run = store.get_run(conn, rid)
        st.info(f"The report is not built yet (run state: {run.state.value}). It appears after the "
                "verdict stage; follow the run on the Run page.")
        return
    report, markdown = found
    run, summary, led = report["run"], report["summary"], report["ledger"]
    st.subheader(run["domain"])
    st.caption(f"Run {run['id']} · deck date {run['deck_date'] or 'unknown'} ({run['deck_date_source']}) · "
               f"report generated {report['generated_at']}")

    by = summary["by_label"]
    cols = st.columns(7)
    cols[0].metric("Claims", summary["claims"])
    cols[1].metric("Supported", by.get("SUPPORTED", 0))
    cols[2].metric("Contradicted", by.get("CONTRADICTED", 0))
    cols[3].metric("Cannot verify", by.get("CANNOT_VERIFY", 0) + by.get("NOT_COMPARABLE", 0))
    cols[4].metric("Held", by.get("HELD", 0))
    cols[5].metric("Cost (INR)", f"₹{led['cost_inr']:.2f}")
    cols[6].metric("Call time", f"{led['duration_ms'] / 1000:.1f} s")
    for flag in summary["flags"]:
        st.warning(flag)

    st.subheader(f"Red flags ({len(report['red_flags'])})")
    st.caption("Contradicted claims, most material first (materiality weights in config/rules.yaml).")
    if not report["red_flags"]:
        st.write("None. No claim was contradicted by the sources we checked.")
    for f in report["red_flags"]:
        with st.container(border=True):
            st.markdown(f"Slide {f.get('slide', '-')} · {f.get('type', '-')} · {badge(f.get('label'))} · "
                        f"confidence {f.get('confidence') or '-'} · materiality {f.get('materiality', '-')}")
            if f.get("explanation"):
                st.write(f["explanation"])
            if f.get("sources"):
                st.markdown(_sources_table(f["sources"]))
            st.button("Open this claim", key=f"flag-{f.get('claim_id', id(f))}", on_click=go_to,
                      args=("Claims", rid))

    left, right = st.columns(2)
    with left:
        st.subheader(f"Questions for the founders ({len(report['founder_questions'])})")
        if report["founder_questions"]:
            st.markdown("\n".join(f"{i}. {q.get('question', '')} _(slide {q.get('slide', '-')})_"
                                  for i, q in enumerate(report["founder_questions"], 1)))
        else:
            st.write("None.")
    with right:
        st.subheader(f"Evidence requests ({len(report['evidence_requests'])})")
        if report["evidence_requests"]:
            st.markdown("\n".join(f"- {r.get('request', '')} _(slide {r.get('slide', '-')}, {r.get('label', '-')})_"
                                  for r in report["evidence_requests"]))
        else:
            st.write("None.")

    st.subheader(f"Not checked: HELD ({len(report['held'])})")
    if report["held"]:
        st.markdown("\n".join(f"- {h.get('note', '')} _(slide {h.get('slide', '-')}, {h.get('reason_code', '-')})_" for h in report["held"]))
    else:
        st.write("None. Every claim was checked.")

    st.subheader("Run cost")
    st.write(f"{led['calls']} external calls ({led['failed']} failed), {led['credits']:g} credits, "
             f"₹{led['cost_inr']:.2f}.")
    if led["by_provider"]:
        st.markdown(_kv_table([(p, f"{v.get('calls', 0)} calls, {v.get('failed', 0)} failed, "
                                   f"{v.get('credits', 0):g} credits, ₹{v.get('cost_inr', 0):.2f}") for p, v in sorted(led["by_provider"].items())]))

    d1, d2, _ = st.columns([1, 1, 3])
    d1.download_button("Download report.json", json.dumps(report, indent=2, ensure_ascii=False),
                       file_name=f"{rid}-report.json", mime="application/json")
    d2.download_button("Download report.md", markdown, file_name=f"{rid}-report.md", mime="text/markdown")


# ---------- Claims ----------

def _claim_detail(r: dict[str, Any]) -> None:
    st.markdown(f"> {r['quote']}")
    st.markdown(f"{badge(r['verdict'])} · confidence {r['confidence'] or '-'} · reason `{r['reason_code'] or '-'}`")
    if r["explanation"]:
        st.write(r["explanation"])
    if r["missing"]:
        st.write(f"**What would settle it:** {r['missing']}")

    claimed, found = st.columns(2)
    with claimed:
        st.markdown("**Claimed in the deck**")
        st.markdown(_kv_table([("slide", r["slide"]), ("subject", r["subject"]), ("metric", r["metric"]),
                               ("value", r["claimed_value"]), ("unit", r["unit"]), ("as_of", r["as_of"])]))
    with found:
        st.markdown("**Found by the checker**")
        if not r["checked"]:
            st.caption("Not checked yet.")
        else:
            pairs = list(r["observed"].items())
            pairs.append(("comparable", r["comparable"]))
            if r["held_reason"]:
                pairs.append(("held_reason", r["held_reason"]))
            st.markdown(_kv_table(pairs))

    if r["sources"]:
        st.markdown("**Sources**")
        st.markdown(_sources_table(r["sources"]))
    else:
        st.caption("No sources stored for this claim.")


def page_claims() -> None:
    st.header("Claims")
    rid = pick_run()
    if rid is None:
        return
    run = store.get_run(conn, rid)
    st.caption(f"{run.input.domain} · deck date {run.input.deck_date or 'unknown'} "
               f"({run.input.deck_date_source}) · state {run.state.value}")
    rows = data.claim_rows(conn, rid, rules)
    if not rows:
        st.info("No claims yet for this run.")
        return
    try:
        columns = data.claim_columns(rules)
    except (ValueError, KeyError) as e:
        st.error(str(e))
        columns = ["claim_id", "slide", "type", "label", "confidence", "reason_code", "quote"]

    present = [v for v in VERDICT_ORDER if any(r["verdict"] == v for r in rows)]
    f1, f2 = st.columns(2)
    verdicts = f1.multiselect("Verdict", present, default=present)
    types = sorted({r["type"] for r in rows})
    chosen_types = f2.multiselect("Claim type", types, default=types)
    shown = [r for r in rows if r["verdict"] in verdicts and r["type"] in chosen_types]

    table = [{data.DISPLAY_NAMES.get(c, c): data.table_cell(r.get(c)) for c in columns} for r in shown]
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.caption(f"{len(shown)} of {len(rows)} claims · columns follow output.fields in config/rules.yaml")

    for r in shown:
        title = f"Slide {r['slide']} · {r['type']} · {r['verdict']}" + (
            f" ({r['confidence']})" if r["confidence"] else "")
        with st.expander(title, expanded=r["verdict"] == "CONTRADICTED"):
            _claim_detail(r)


# ---------- Entities ----------

def page_entities() -> None:
    st.header("Entities")
    st.caption("Who the deck was matched to. A company or founder counts as identified only with enough "
               "independent signals (identity.min_signals in config/rules.yaml). Professional fields only.")
    rid = pick_run()
    if rid is None:
        return
    view = data.entities_view(conn, rid)
    if view is None:
        st.info("Entities are not resolved yet for this run.")
        return
    rows = ([view["company"]] if view["company"] else []) + view["founders"]
    if not rows:
        st.info("Resolve found no company or founders to match.")
        return
    unclear = [r for r in rows if r["identity"] != "confirmed"]
    for r in unclear:
        who = r.get("name") or r.get("profile_url") or r["role"]
        st.warning(f"{r['role'].capitalize()} {who}: identity {r['identity']} ({r['reason'] or 'no reason stored'}). "
                   "Claims about it cannot be Supported or Contradicted.")
    st.dataframe(rows, use_container_width=True, hide_index=True)


# ---------- Approvals ----------

def page_approvals() -> None:
    st.header("Approvals")
    st.caption("The founder email is sent only after a human approves it here, and only to the "
               "local test inbox. Sending happens exactly once, even after a crash.")
    reviewer = st.text_input("Your name (recorded with the decision)")
    for msg in st.session_state.pop("approval_msgs", []):
        st.success(msg)

    pending = data.emails(conn, ActionStatus.PENDING)
    st.subheader(f"Waiting for approval ({len(pending)})")
    if not pending:
        st.info("No founder email is waiting.")
    for a in pending:
        with st.container(border=True):
            found = data.report_view(conn, a.run_id)
            flags = len(found[0]["red_flags"]) if found else None
            st.write(f"**Run:** {a.run_id} · **To:** {a.recipient}"
                     + (f" · **Red flags in report:** {flags}" if flags is not None else ""))
            st.write(f"**Subject:** {a.subject}")
            st.text(a.body)
            left, mid, right = st.columns(3)
            if left.button("Approve and send", key=f"approve-{a.id}", type="primary"):
                try:
                    email.approve(conn, rules, a.id, reviewer)
                    sent = email.send_approved(conn, rules)
                    st.session_state["approval_msgs"] = [
                        f"Approved by {reviewer}; sent {len(sent)} email(s) to the test inbox."]
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            if mid.button("Reject", key=f"reject-{a.id}"):
                try:
                    email.reject(conn, a.id, reviewer)
                    st.session_state["approval_msgs"] = [f"Rejected by {reviewer}; it will not be sent."]
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            right.button("Read the report first", key=f"report-{a.id}", on_click=go_to,
                         args=("Report", a.run_id))

    stuck = data.emails(conn, ActionStatus.APPROVED) + data.emails(conn, ActionStatus.SENDING)
    if stuck:
        st.subheader("Approved but not sent yet (for example after a crash)")
        st.dataframe([{"action_id": a.id, "run_id": a.run_id, "status": a.status.value,
                       "approved_by": a.decided_by} for a in stuck], hide_index=True)
        if st.button("Send now (exactly once)"):
            sent = email.send_approved(conn, rules)
            st.session_state["approval_msgs"] = [f"Sent {len(sent)} email(s) to the test inbox."]
            st.rerun()

    decided = [a for s in (ActionStatus.SENT, ActionStatus.REJECTED) for a in data.emails(conn, s)]
    if decided:
        st.subheader("Decided")
        st.dataframe([{"run_id": a.run_id, "status": a.status.value, "by": a.decided_by,
                       "decided_at": a.decided_at, "sent_at": a.sent_at} for a in decided],
                     hide_index=True)


# ---------- Inbox ----------

def page_inbox() -> None:
    st.header("Inbox")
    st.warning("Local test inbox, no real email. Approved founder emails land here and nowhere else.")
    rows = data.inbox_rows(conn)
    if not rows:
        st.info("The test inbox is empty.")
        return
    st.dataframe([{k: r[k] for k in ("received_at", "to", "subject", "action_id")} for r in rows],
                 use_container_width=True, hide_index=True)
    for r in rows:
        with st.expander(f"{r['received_at']} · {r['subject']}"):
            st.text(r["body"])


# ---------- Ledger ----------

def page_ledger() -> None:
    st.header("Ledger")
    st.caption("Every external call of a run, including failed ones: Crustdata, LLM and web. "
               "A source's call_id on the Claims page is the call_id here.")
    rid = pick_run()
    if rid is None:
        return
    summary = data.ledger_summary(conn, rid)
    cols = st.columns(5)
    cols[0].metric("Calls", summary["calls"])
    cols[1].metric("Failed", summary["failed"])
    cols[2].metric("Credits", f"{summary['credits']:g}")
    cols[3].metric("Cost (INR)", f"₹{summary['cost_inr']:.2f}")
    cols[4].metric("Seconds in calls", summary["seconds"])
    for lim in data.limits_used(rules, summary):
        st.progress(lim["share"], text=f"{lim['limit']}: {lim['used']:g} of {lim['max']:g} "
                                       "(limit in config/rules.yaml; past it, claims become HELD)")
    if not summary["rows"]:
        st.info("No external calls recorded for this run yet.")
        return
    st.dataframe(summary["rows"], use_container_width=True, hide_index=True)
    failed = [r for r in summary["rows"] if not r["ok"]]
    if failed:
        st.subheader(f"Failed calls ({len(failed)})")
        st.markdown(_kv_table([(f"{r['provider']} {r['endpoint_or_model']}", r["error"]) for r in failed]))
    st.subheader("By provider")
    st.dataframe(summary["by_provider"], use_container_width=True, hide_index=True)
    st.download_button("Download ledger.csv", data.ledger_csv(conn, rid), file_name=f"{rid}-ledger.csv",
                       mime="text/csv")


PAGE_FUNCS = {"Run": page_run, "Report": page_report, "Claims": page_claims, "Entities": page_entities,
              "Approvals": page_approvals, "Inbox": page_inbox, "Ledger": page_ledger}
PAGE_FUNCS[page]()
