"""T28 tests: the UI shows every stored result. Report page (red flags, founder questions, evidence
requests, held, downloads), Claims page (columns follow rules.yaml output.fields, claimed vs found),
Entities page, run progress and ledger CSV. Data is written with core/store.py helpers (fixtures in tests only).

Called by: pytest. Calls: ui/data.py, ui/app.py (Streamlit AppTest), core/store.py, report/builder.py.
"""

import copy

from conftest import open_app
from test_claims_page import make_decided_run

from core import store
from core.config import load_rules
from report.builder import build
from ui import data


def _with_report(conn, rules):
    rid = make_decided_run(conn, rules)                  # one claim, checked and decided
    report, md = build(conn, rules, rid)
    store.save_report(conn, rid, report, md)
    return rid


def test_report_page_shows_red_flags_questions_and_downloads(conn, db_path):
    rules = load_rules()
    _with_report(conn, rules)
    at = open_app(db_path, "Report")
    text = " ".join(m.value for m in at.markdown)
    assert 'class="dc-strip"' in text and "Slide 4: Contradicted, team_size" in text   # one strip segment
    assert "Contradicted</span> <b>1</b>" in text                                      # legend count
    assert "We are 300 people" in text                    # the deck quote sits next to the red flag
    assert "Records show about 210 people." in text      # verdict explanation of the red flag
    assert "locus.sh/about" in text                     # source of the red flag is shown
    assert any(h.value.startswith("Questions for the founders (1)") for h in at.subheader)
    labels = [b.proto.label for b in at.get("download_button")]
    assert labels == ["Download report.json", "Download report.md"]


def test_report_page_says_when_not_built(conn, db_path):
    make_decided_run(conn, load_rules())
    at = open_app(db_path, "Report")
    assert any("not ready yet" in i.value for i in at.info)


def test_report_view_fills_missing_sections(conn):
    rules = load_rules()
    rid = make_decided_run(conn, rules)
    store.save_report(conn, rid, {"run": {"domain": "locus.sh"}}, "# r")
    report, md = data.report_view(conn, rid)
    assert report["red_flags"] == [] and report["ledger"]["calls"] == 0 and md == "# r"


def test_claim_columns_follow_output_fields(conn, db_path):
    rules = copy.deepcopy(load_rules())
    rules["output"]["fields"] = ["slide", "label", "as_of"]
    assert data.claim_columns(rules) == ["slide", "label", "as_of"]
    rules["output"]["fields"].append("nonsense")
    try:
        data.claim_columns(rules)
        raise AssertionError("unknown field accepted")
    except ValueError as e:
        assert "nonsense" in str(e)


def test_claims_page_shows_claimed_vs_found(conn, db_path):
    make_decided_run(conn, load_rules())
    at = open_app(db_path, "Claims")
    assert at.dataframe[0].value["verdict"].tolist() == ["CONTRADICTED"]
    assert "claimed_value" in at.dataframe[0].value.columns
    text = " ".join(m.value for m in at.markdown)
    assert "Claimed in the deck" in text and "Found by the checker" in text
    assert "crustdata_company" in text                   # source_type column


def test_claims_filter_hides_rows(conn, db_path):
    make_decided_run(conn, load_rules())
    at = open_app(db_path, "Claims")
    at.multiselect[0].set_value([]).run()
    assert len(at.dataframe[0].value) == 0


def test_entities_page_flags_unclear_identity(conn, db_path):
    rid = make_decided_run(conn, load_rules())
    store.save_resolution(conn, rid, {
        "company": {"id": "c1", "identity": "confirmed", "identity_signals": 3, "confidence": "high",
                    "signals": ["domain", "name", "founder"], "reason": None, "call_id": None},
        "founders": [{"id": None, "identity": "unclear", "identity_signals": 1, "confidence": "low",
                      "signals": ["name"], "reason": "multiple_candidates", "call_id": None,
                      "name": "Nishith Rastogi", "profile_url": None}]})
    view = data.entities_view(conn, rid)
    assert view["company"]["signals"] == "domain, name, founder"
    at = open_app(db_path, "Entities")
    assert any("Nishith Rastogi" in w.value and "unclear" in w.value for w in at.warning)
    assert len(at.dataframe[0].value) == 2


def test_run_progress_counts_claim_states(conn):
    rid = make_decided_run(conn, load_rules())
    prog = data.run_progress(conn, rid)
    assert prog["state"] == "created" and prog["index"] == 0
    assert prog["claims"] == 1 and prog["claims_by_state"]["decided"] == 1


def test_ledger_csv_and_by_provider(conn, db_path):
    rid = make_decided_run(conn, load_rules())
    csv_text = data.ledger_csv(conn, rid)
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("call_id,ts,provider") and len(lines) == 3
    providers = {p["provider"]: p["calls"] for p in data.ledger_summary(conn, rid)["by_provider"]}
    assert providers == {"crustdata": 1, "web": 1}
    at = open_app(db_path, "Ledger")
    assert [b.proto.label for b in at.get("download_button")] == ["Download ledger.csv"]
