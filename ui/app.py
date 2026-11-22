"""DeckCheck Streamlit UI: Run, Report, Claims, Entities, Approvals, Inbox and Ledger pages.

Run from the repo root: streamlit run ui/app.py
Called by: humans (the demo). Calls: ui/data.py, ui/theme.py, actions/email.py, core/store.py,
core/config.py. Shows what the pipeline stored; it never writes claims, evidence or verdicts. The
founder email is approved or rejected only by a human click here, then sent by the exactly-once sender.
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

# Streamlit Cloud keeps keys in st.secrets; the background run (cli.py) reads the environment.
# Names are matched case-insensitively and nested [sections] are searched, so
# "openai_api_key" or [api] OPENAI_API_KEY = ... also work.
def _export_secrets(node: Any) -> None:
    import os
    for key, value in node.items():
        if isinstance(value, str) and value.strip():
            os.environ.setdefault("_".join(str(key).strip().upper().split()), value.strip())
        elif hasattr(value, "items"):
            _export_secrets(value)


try:
    _export_secrets(st.secrets)
except Exception:  # no secrets file locally: keys come from .env (core/env.py)
    pass

from core import store  # noqa: E402
from core.config import load_rules  # noqa: E402
from actions import email  # noqa: E402
from core.models import ActionStatus  # noqa: E402
from ui import components, data, theme  # noqa: E402
from ui.theme import esc  # noqa: E402

st.set_page_config(page_title="DeckCheck", layout="wide")
st.markdown(theme.CSS, unsafe_allow_html=True)

# A strip click or a button asked for another page: apply it before the page radio is drawn.
if "nav_to" in st.session_state:
    _target, _claim = st.session_state.pop("nav_to")
    st.session_state["page"] = _target
    if _claim:
        st.session_state["focus_claim"] = _claim

PAGES = ["Run", "Report", "Claims", "Entities", "Approvals", "Inbox", "Ledger"]
PAGE_NAMES = {"Run": "Check a deck", "Report": "Report", "Claims": "Every claim", "Entities": "Who we matched",
              "Approvals": "Founder email", "Inbox": "Test inbox", "Ledger": "Cost and calls"}
VERDICT_ORDER = ["CONTRADICTED", "HELD", "CANNOT_VERIFY", "NOT_COMPARABLE", "SUPPORTED", "PENDING"]
# Colours and names for the motion components, from ui/theme.py (one source of truth).
VERDICT_ARGS = {"colours": {k: v[1] for k, v in theme.VERDICTS.items()},
                "names": {k: v[0] for k, v in theme.VERDICTS.items()}}

st.sidebar.markdown('<p class="dc-brand">DeckCheck</p><p class="dc-brand-sub">Checks each claim in a pitch '
                    'deck against live company records, and shows the proof.</p>', unsafe_allow_html=True)
page = st.sidebar.radio("Page", PAGES, key="page", format_func=PAGE_NAMES.get, label_visibility="collapsed")
st.sidebar.divider()
db_path = st.sidebar.text_input("Database file", str(ROOT / store.DEFAULT_DB), key="db_path")
conn = store.connect(db_path)
rules = load_rules()
st.sidebar.caption("Decision support for a human reviewer. A verdict is not an automatic rejection.")


# ---------- shared helpers ----------

def go_to(target: str, run_id: str | None = None) -> None:
    """Button callback: switch page (and run) before the next rerun draws the sidebar."""
    st.session_state["page"] = target
    if run_id:
        st.session_state["current_run"] = run_id


def pick_run(label: str = "Run", db=None) -> str | None:
    """One run choice shared by every page (kept in session_state across page switches)."""
    runs = store.list_runs(db or conn)
    if not runs:
        st.info("No deck has been checked yet. Start one on Check a deck.")
        return None
    ids = [r.id for r in runs]
    names = {r.id: f"{r.input.domain}, {r.id} ({r.state.value})" for r in runs}
    current = st.session_state.get("current_run")
    index = ids.index(current) if current in ids else 0
    rid = st.selectbox(label, ids, index=index, format_func=names.get)
    st.session_state["current_run"] = rid
    return rid


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def plain(value: object) -> str:
    """Readable text for a stored value: 'employer: Amazon; title: Software Developer' instead of raw JSON."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return "; ".join(f"{k}: {plain(v)}" for k, v in value.items() if v not in (None, "", [], {}))
    if isinstance(value, (list, tuple)):
        return " | ".join(plain(v) for v in value)
    return str(value)


def _cell(value: object) -> str:
    return plain(value).replace("|", "\\|").replace("\n", " ")


def _short_time(ts: object) -> str:
    """'2026-11-22T10:15:39+00:00' -> '2026-11-22 10:15 UTC' (the full value stays in the JSON report)."""
    text = str(ts or "")
    return f"{text[:10]} {text[11:16]} UTC" if len(text) >= 16 and text[10] == "T" else text


def _sources_table(sources: list[dict], with_call: bool = True) -> str:
    """Markdown table; URL sources are clickable links, API endpoints are shown as code."""
    head = ["Source", "Where", "Field or quote", "Value", "Record date", "Retrieved"] + (["Call"] if with_call else [])
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for s in sources:
        where = s.get("url_or_endpoint") or s.get("locator") or ""
        is_url = s.get("is_url", str(where).startswith(("http://", "https://")))
        where_md = f"[{_cell(where)}]({where})" if is_url else f"`{_cell(where)}`"
        cells = [_cell(s.get("source_type")), where_md, _cell(s.get("field_or_quote")), _cell(s.get("value")),
                 _cell(s.get("record_date")), _short_time(s.get("retrieved_at"))]
        if with_call:
            cells.append(_cell(s.get("call_id")))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _kv_table(pairs: list[tuple[str, Any]], head: tuple[str, str] = ("Field", "Value")) -> str:
    lines = [f"| {head[0]} | {head[1]} |", "|---|---|"]
    lines += [f"| {_cell(k)} | {_cell(v)} |" for k, v in pairs]
    return "\n".join(lines)


def _type_name(claim_type: str | None) -> str:
    return (claim_type or "").replace("_", " ")


def strip_view(rows: list[dict[str, Any]], rid: str, where: str, counts: dict[str, int],
               animate: bool = False) -> None:
    """The slide strip: animated, clickable component, or the static HTML strip if components are off."""
    payload = {"run_id": rid, "animate": animate, "claims": data.strip_payload(rows), "counts": counts,
               **VERDICT_ARGS}
    value = components.motion("strip", payload, key=f"strip-{where}-{rid}")
    if value is components.MISSING:
        html(theme.strip(rows) + theme.legend(counts))
        return
    if isinstance(value, dict) and value.get("nonce") != st.session_state.get("strip_nonce"):
        st.session_state["strip_nonce"] = value.get("nonce")
        st.session_state["nav_to"] = ("Claims", value.get("claim_id"))
        st.rerun()


def gauge_view(row: dict[str, Any] | None, where: str) -> None:
    """Claimed vs found on one scale (numeric claims with a tolerance only). Nothing drawn otherwise:
    the claimed/found tables already show the numbers."""
    payload = data.gauge_payload(row, rules) if row else None
    if payload is None:
        return
    components.motion("gauge", {**payload, "gauge_id": row["claim_id"], **VERDICT_ARGS},
                      key=f"gauge-{where}-{row['claim_id']}")


def route_view(db, rid: str) -> None:
    """The run as a tracked route with claims landing; static stepper + progress bar if components are off."""
    prog = data.run_progress(db, rid)
    rows = data.claim_rows(db, rid)
    value = components.motion("route", {"run_id": rid, **data.route_payload(prog, rows), **VERDICT_ARGS},
                              key=f"route-{rid}")
    if value is not components.MISSING:
        return
    html(theme.stepper(prog["order"], prog["index"], prog["failed"], prog["finished"]))
    if prog["failed"]:
        st.error(f"The run stopped with an error: {prog['error'] or 'no error text stored'}. "
                 "Resume it below; finished steps are skipped.")
    n = prog["claims"]
    by = prog["claims_by_state"]
    if n:
        st.progress(by.get("decided", 0) / n,
                    text=f"{by.get('decided', 0)} of {n} claims decided, {by.get('checked', 0)} waiting for a "
                         f"verdict, {by.get('pending', 0)} not checked yet")
    else:
        st.caption("No claims read from the deck yet.")


# ---------- Run ----------

def _progress_block(db) -> None:
    """Route tracker for the chosen run. `db` is the caller's connection (the auto-refresh fragment runs
    in its own thread and SQLite connections are per thread)."""
    rid = pick_run("Follow a run", db)
    if rid is None:
        return
    route_view(db, rid)


def page_run() -> None:
    st.title("Check a deck")
    st.caption("Give DeckCheck a deck and the company's domain. The check runs in the background and this "
               "page follows it until the report is ready.")
    modes = ["Upload a deck PDF", "Request file in repo", "Upload D3 request (JSON)"]
    mode = st.radio("Start from", modes, horizontal=True, label_visibility="collapsed")
    run_input = None
    try:
        with st.container(border=True):
            if mode == "Upload a deck PDF":
                deck = st.file_uploader("Deck PDF (text-based)", type=["pdf"])
                left, right = st.columns(2)
                domain = left.text_input("Company domain", placeholder="locus.sh")
                deck_date = right.text_input("Deck date (YYYY-MM-DD, blank = read from the PDF)")
                urls = st.text_area("Founder profile URLs (one per line, optional)")
                # The button is always shown; missing inputs are reported when it is pressed.
                if st.button("Check this deck", type="primary", key="check_pdf"):
                    if deck is None:
                        raise ValueError("Add the deck PDF first.")
                    if not domain.strip():
                        raise ValueError("Add the company domain (for example locus.sh).")
                    run_input = data.input_from_form(data.save_upload(deck.name, deck.getvalue()),
                                                     domain.strip().lower(), deck_date.strip() or None,
                                                     [u.strip() for u in urls.splitlines() if u.strip()])
            elif mode == "Request file in repo":
                files = data.request_files()
                if not files:
                    st.warning("No request files found in tests/decks or tests/requests.")
                else:
                    chosen = st.selectbox("Request", files, format_func=lambda p: str(p.relative_to(ROOT)))
                    if st.button("Check this deck", type="primary", key="check_repo"):
                        run_input = data.input_from_request_file(chosen)
            else:
                req = st.file_uploader("Request JSON (DECISIONS.md D3)", type=["json"])
                deck = st.file_uploader("Deck PDF (optional; otherwise deck_path in the request)", type=["pdf"])
                if st.button("Check this deck", type="primary", key="check_json"):
                    if req is None:
                        raise ValueError("Add the request JSON first.")
                    override = data.save_upload(deck.name, deck.getvalue()) if deck else None
                    run_input = data.input_from_request(json.loads(req.getvalue()), ROOT, override)
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
        # Fragment reruns run in another thread and reuse the closure of the run that first drew them,
        # so read the current database path from session state, not from the captured variable.
        db = store.connect(st.session_state.get("db_path", db_path))
        try:
            fresh = data.run_rows(db)
            if not fresh:
                st.info("No deck has been checked yet. Add a deck PDF and its domain above, then press Check this deck.")
                return
            st.subheader("Progress")
            _progress_block(db)
            st.subheader("All runs")
            st.dataframe(fresh, use_container_width=True, hide_index=True,
                         column_config={"cost_inr": st.column_config.NumberColumn("cost (INR)", format="₹%.2f")})
        finally:
            db.close()
        if live and not any(r["state"] not in ("done", "failed") for r in fresh):
            st.rerun()                              # a run just finished: redraw the whole page once

    live_part()
    followed = st.session_state.get("current_run")
    if followed and any(r["run_id"] == followed and r["state"] == "done" for r in data.run_rows(conn)):
        st.button("Open the report", on_click=go_to, args=("Report", followed), type="primary")
    unfinished = [r["run_id"] for r in rows if r["state"] != "done"]
    if unfinished:
        st.subheader("Resume a stopped run")
        rid = st.selectbox("Resume a run that stopped", unfinished, label_visibility="collapsed")
        if st.button("Resume"):
            data.launch(db_path, rid)
            st.success(f"Resuming {rid}: finished steps and claims are skipped.")


# ---------- Report ----------

def _red_flag(flag: dict[str, Any], claim: dict[str, Any] | None, rid: str) -> None:
    with st.container(border=True):
        left, right = st.columns([5, 6], gap="large")
        with left:
            html(theme.quote(claim["quote"] if claim else "(quote not stored)", flag.get("slide")))
            st.caption(f"{_type_name(flag.get('type'))}, materiality {flag.get('materiality', '-')}")
        with right:
            html(f"{theme.mark(flag.get('label'))} "
                 f"<span class='dc-small'>{esc(flag.get('confidence') or '-')} confidence</span>"
                 f"<div class='dc-found'>{esc(flag.get('explanation') or 'No explanation stored.')}</div>")
            gauge_view(claim, "flag")
            st.button("See the evidence", key=f"flag-{flag.get('claim_id', id(flag))}", on_click=go_to,
                      args=("Claims", rid))
        if flag.get("sources"):
            st.markdown(_sources_table(flag["sources"], with_call=False))


def page_report() -> None:
    rid = pick_run()
    if rid is None:
        return
    found = data.report_view(conn, rid)
    if found is None:
        run = store.get_run(conn, rid)
        st.info(f"The report is not ready yet (the run is at '{run.state.value}'). It appears once every "
                "claim has a verdict.")
        route_view(conn, rid)
        return
    report, markdown = found
    run, summary, led = report["run"], report["summary"], report["ledger"]
    claims = data.claim_rows(conn, rid, rules)
    by_id = {c["claim_id"]: c for c in claims}

    html(f'<div class="dc-hero"><p class="dc-company">{esc(run["domain"])}</p>'
         f'<p class="dc-meta">Deck dated {esc(run["deck_date"] or "unknown")} '
         f'(from {esc(run["deck_date_source"])}). {summary["claims"]} claims checked with '
         f'{led["calls"]} live calls for ₹{led["cost_inr"]:.2f}.</p></div>')
    _, dl1, dl2, _ = st.columns([2, 2, 2, 2])
    dl1.download_button("Download report.json", json.dumps(report, indent=2, ensure_ascii=False),
                        file_name=f"{rid}-report.json", mime="application/json", use_container_width=True)
    dl2.download_button("Download report.md", markdown, file_name=f"{rid}-report.md", mime="text/markdown",
                        use_container_width=True)
    st.caption(f"Run {rid}")

    strip_view(claims, rid, "report", summary["by_label"], animate=True)
    for flag in summary["flags"]:
        html(theme.banner(flag, "Note"))

    flags = report["red_flags"]
    st.subheader(f"Red flags ({len(flags)})")
    if not flags:
        st.write("No claim was contradicted by the records we checked.")
    else:
        st.caption("Contradicted claims, most material first. What the deck says on the left, what the "
                   "records say on the right.")
    for f in flags:
        _red_flag(f, by_id.get(f.get("claim_id")), rid)

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader(f"Questions for the founders ({len(report['founder_questions'])})")
        if report["founder_questions"]:
            st.markdown("\n".join(f"{i}. {q.get('question', '')}"
                                  for i, q in enumerate(report["founder_questions"], 1)))
        else:
            st.write("None. Nothing in the deck was contradicted.")
    with right:
        st.subheader(f"Evidence requests ({len(report['evidence_requests'])})")
        if report["evidence_requests"]:
            st.markdown("\n".join(f"- {r.get('request', '')}" for r in report["evidence_requests"]))
        else:
            st.write("None. Every claim could be compared with a record.")

    st.subheader(f"Not checked ({len(report['held'])})")
    if report["held"]:
        st.caption("Held claims hit a limit, a timeout or an error. They have no verdict, not a negative one.")
        st.markdown("\n".join(f"- {h.get('note', '')}" for h in report["held"]))
    else:
        st.write("None. Every claim was checked.")

    with st.expander(f"Run cost: ₹{led['cost_inr']:.2f} for {led['calls']} calls ({led['failed']} failed)"):
        if led["by_provider"]:
            st.markdown(_kv_table([(p, f"{v.get('calls', 0)} calls, {v.get('failed', 0)} failed, "
                                       f"{v.get('credits', 0):g} credits, ₹{v.get('cost_inr', 0):.2f}")
                                   for p, v in sorted(led["by_provider"].items())], ("Provider", "Use")))
        st.button("Open the full ledger", on_click=go_to, args=("Ledger", rid))


# ---------- Claims ----------

def _claim_detail(r: dict[str, Any]) -> None:
    left, right = st.columns([5, 6], gap="large")
    with left:
        html(theme.quote(r["quote"], r["slide"]))
        st.markdown(_kv_table([("Subject", r["subject"]), ("Metric", r["metric"]),
                               ("Value", f"{_cell(r['claimed_value'])} {r['unit'] or ''}".strip()),
                               ("As of", r["as_of"])], ("Claimed in the deck", "")))
    with right:
        html(f"{theme.mark(r['verdict'])} <span class='dc-small'>{esc(r['confidence'] or '-')} confidence, "
             f"reason <code>{esc(r['reason_code'] or '-')}</code></span>"
             f"<div class='dc-found'>{esc(r['explanation'] or '')}</div>")
        if r["missing"]:
            st.markdown(f"**What would settle it:** {r['missing']}")
        gauge_view(r, "claim")
        if not r["checked"]:
            st.caption("Found by the checker: not checked yet.")
        else:
            pairs = list(r["observed"].items()) + [("comparable", r["comparable"])]
            if r["held_reason"]:
                pairs.append(("held_reason", r["held_reason"]))
            st.markdown(_kv_table(pairs, ("Found by the checker", "")))
    if r["sources"]:
        st.markdown(_sources_table(r["sources"]))
    else:
        st.caption("No sources stored for this claim.")


def page_claims() -> None:
    st.title("Every claim")
    rid = pick_run()
    if rid is None:
        return
    run = store.get_run(conn, rid)
    rows = data.claim_rows(conn, rid, rules)
    if not rows:
        st.info(f"No claims yet for {run.input.domain}. They appear once the deck has been read.")
        return
    try:
        columns = data.claim_columns(rules)
    except (ValueError, KeyError) as e:
        st.error(str(e))
        columns = ["claim_id", "slide", "type", "label", "confidence", "reason_code", "quote"]

    counts = {label: sum(1 for r in rows if r["verdict"] == label) for label in theme.VERDICTS}
    strip_view(rows, rid, "claims", counts)
    focus = st.session_state.pop("focus_claim", None)
    present = [v for v in VERDICT_ORDER if any(r["verdict"] == v for r in rows)]
    f1, f2 = st.columns(2)
    verdicts = f1.multiselect("Verdict", present, default=present, format_func=theme.verdict_name)
    types = sorted({r["type"] for r in rows})
    chosen_types = f2.multiselect("Claim type", types, default=types, format_func=_type_name)
    shown = [r for r in rows if (r["verdict"] in verdicts and r["type"] in chosen_types) or r["claim_id"] == focus]

    table = [{data.DISPLAY_NAMES.get(c, c): data.table_cell(r.get(c)) for c in columns} for r in shown]
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.caption(f"{len(shown)} of {len(rows)} claims. Columns follow output.fields in config/rules.yaml.")

    for r in sorted(shown, key=lambda r: (VERDICT_ORDER.index(r["verdict"]) if r["verdict"] in VERDICT_ORDER
                                          else 99, r["slide"])):
        colour = {"SUPPORTED": "green", "CONTRADICTED": "red", "HELD": "orange"}.get(r["verdict"], "gray")
        title = (f":{colour}[**{theme.verdict_name(r['verdict'])}**]  Slide {r['slide']}, "
                 f"{_type_name(r['type'])}: {r['quote'][:90]}{'...' if len(r['quote']) > 90 else ''}")
        with st.expander(title, expanded=r["verdict"] == "CONTRADICTED" or r["claim_id"] == focus):
            _claim_detail(r)


# ---------- Entities ----------

def page_entities() -> None:
    st.title("Who we matched")
    st.caption("A company or founder counts as identified only with enough independent signals "
               "(identity.min_signals in config/rules.yaml). Only professional fields are kept.")
    rid = pick_run()
    if rid is None:
        return
    view = data.entities_view(conn, rid)
    if view is None:
        st.info("The company and founders are not matched yet for this run.")
        return
    rows = ([view["company"]] if view["company"] else []) + view["founders"]
    if not rows:
        st.info("The deck named no company or founders to match.")
        return
    for r in [r for r in rows if r["identity"] != "confirmed"]:
        who = r.get("name") or r.get("profile_url") or r["role"]
        st.warning(f"{r['role'].capitalize()} {who}: identity {r['identity']} ({r['reason'] or 'no reason stored'}). "
                   "Claims about it cannot be Supported or Contradicted.")
    st.dataframe(rows, use_container_width=True, hide_index=True)


# ---------- Approvals ----------

def page_approvals() -> None:
    st.title("Founder email")
    st.caption("The email goes out only after a person approves it here, and only to the local test inbox. "
               "It is sent exactly once, even after a crash.")
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
            st.markdown(f"**{a.subject}**")
            st.caption(f"To {a.recipient}, from run {a.run_id}"
                       + (f", based on {flags} red flag(s) in the report" if flags is not None else ""))
            st.text(a.body)
            left, mid, right = st.columns([2, 1, 2])
            if left.button("Approve and send", key=f"approve-{a.id}", type="primary"):
                try:
                    email.approve(conn, rules, a.id, reviewer)
                    sent = email.send_approved(conn, rules)
                    st.session_state["just_sent"] = a.id
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
        st.subheader("Approved but not sent yet")
        st.caption("This happens when the app stopped between approval and sending.")
        st.dataframe([{"action_id": a.id, "run_id": a.run_id, "status": a.status.value,
                       "approved_by": a.decided_by} for a in stuck], hide_index=True)
        if st.button("Send now (exactly once)"):
            sent = email.send_approved(conn, rules)
            st.session_state["approval_msgs"] = [f"Sent {len(sent)} email(s) to the test inbox."]
            st.rerun()

    sent_list = sorted(data.emails(conn, ActionStatus.SENT), key=lambda a: a.sent_at or "", reverse=True)
    if sent_list:
        st.subheader(f"Sent ({len(sent_list)})")
        inbox_count = len(data.inbox_rows(conn))
        for a in sent_list[:3]:
            value = components.motion("sent", {
                "action_id": a.id, "subject": a.subject, "recipient": a.recipient,
                "key_prefix": a.idempotency_key[:10], "sent_at": a.sent_at, "inbox_count": inbox_count,
                "just_sent": a.id == st.session_state.get("just_sent")}, key=f"sent-{a.id}")
            if value is components.MISSING:
                st.success(f"Sent once: {a.subject} to {a.recipient} at {a.sent_at} "
                           f"(key {a.idempotency_key[:10]}...).")

    decided = [a for s in (ActionStatus.SENT, ActionStatus.REJECTED) for a in data.emails(conn, s)]
    if decided:
        st.subheader("Decided")
        st.dataframe([{"run_id": a.run_id, "status": a.status.value, "by": a.decided_by,
                       "decided_at": a.decided_at, "sent_at": a.sent_at} for a in decided],
                     hide_index=True)


# ---------- Inbox ----------

def page_inbox() -> None:
    st.title("Test inbox")
    st.warning("Local test inbox, no real email. Approved founder emails land here and nowhere else.")
    rows = data.inbox_rows(conn)
    if not rows:
        st.info("The test inbox is empty. Approve a founder email to see it arrive here.")
        return
    st.dataframe([{k: r[k] for k in ("received_at", "to", "subject", "action_id")} for r in rows],
                 use_container_width=True, hide_index=True)
    for r in rows:
        with st.expander(f"{r['subject']}, received {r['received_at']}"):
            st.text(r["body"])


# ---------- Ledger ----------

def page_ledger() -> None:
    st.title("Cost and calls")
    st.caption("Every external call of a run, including failed ones: Crustdata, LLM and web. The Call column "
               "on a claim's sources matches call_id here.")
    rid = pick_run()
    if rid is None:
        return
    summary = data.ledger_summary(conn, rid)
    with st.container(border=True):
        cols = st.columns(5)
        cols[0].metric("Calls", summary["calls"])
        cols[1].metric("Failed", summary["failed"])
        cols[2].metric("Credits", f"{summary['credits']:g}")
        cols[3].metric("Cost (INR)", f"₹{summary['cost_inr']:.2f}")
        cols[4].metric("Seconds in calls", summary["seconds"])
        for lim in data.limits_used(rules, summary):
            st.progress(lim["share"], text=f"{lim['limit']}: {lim['used']:g} of {lim['max']:g} allowed per run. "
                                           "Past the limit, remaining claims are held.")
    if not summary["rows"]:
        st.info("No external calls recorded for this run yet.")
        return
    st.dataframe(summary["rows"], use_container_width=True, hide_index=True,
                 column_config={"ok": st.column_config.CheckboxColumn("ok"),
                                "cost_inr": st.column_config.NumberColumn("cost (INR)", format="₹%.2f")})
    failed = [r for r in summary["rows"] if not r["ok"]]
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("By provider")
        st.dataframe(summary["by_provider"], use_container_width=True, hide_index=True)
    with right:
        st.subheader(f"Failed calls ({len(failed)})")
        if failed:
            st.markdown(_kv_table([(f"{r['provider']} {r['endpoint_or_model']}", r["error"]) for r in failed],
                                  ("Call", "Error")))
        else:
            st.write("None.")
    st.download_button("Download ledger.csv", data.ledger_csv(conn, rid), file_name=f"{rid}-ledger.csv",
                       mime="text/csv")


PAGE_FUNCS = {"Run": page_run, "Report": page_report, "Claims": page_claims, "Entities": page_entities,
              "Approvals": page_approvals, "Inbox": page_inbox, "Ledger": page_ledger}
PAGE_FUNCS[page]()
