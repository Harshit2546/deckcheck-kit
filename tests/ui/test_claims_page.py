"""T18 tests: the Claims page shows each claim's verdict, confidence, reason and sources, and
URL sources are links. Data is written with core/store.py helpers (fixtures in tests only).

Called by: pytest. Calls: ui/data.py, ui/app.py (Streamlit AppTest), core/store.py, core/ledger.py.
"""

from conftest import open_app

from core import ledger, store
from core.models import (CheckResult, Claim, ClaimType, Confidence, Evidence, Provider, Run,
                         RunInput, SourceType, Verdict, VerdictLabel, now_iso)
from ui import data


def make_decided_run(conn, rules, run_id="run-ui"):
    store.insert_run(conn, Run(id=run_id, input=RunInput("deck.pdf", "locus.sh", "2026-11-15")))
    claim = Claim(id=f"{run_id}-c001", run_id=run_id, slide=4, quote="We are 300 people",
                  type=ClaimType.TEAM_SIZE, subject="Locus", metric="headcount", value=300,
                  unit="people")
    store.insert_claim(conn, claim)
    call = ledger.record(conn, rules, run_id, Provider.CRUSTDATA, "/screener/company",
                         duration_ms=1500, ok=True, credits=2)
    web = ledger.record(conn, rules, run_id, Provider.WEB, "https://locus.sh/about",
                        duration_ms=500, ok=True)
    evs = [Evidence("ev-1", claim.id, SourceType.CRUSTDATA_COMPANY, "/screener/company",
                    "headcount", 210, "2026-11-01", now_iso(), call.id),
           Evidence("ev-2", claim.id, SourceType.WEB_PAGE, "https://locus.sh/about",
                    "a team of 200+", "200+", "2026-10-20", now_iso(), web.id)]
    store.save_check_result(conn, claim.id, CheckResult(evidence=evs, observed={}))
    store.save_verdict(conn, Verdict(claim.id, VerdictLabel.CONTRADICTED, "outside_tolerance",
                                     "Records show about 210 people.", ["ev-1", "ev-2"],
                                     Confidence.HIGH, None))
    return run_id


def test_claim_rows_have_verdict_and_sources(conn):
    from core.config import load_rules
    rid = make_decided_run(conn, load_rules())
    [row] = data.claim_rows(conn, rid)
    assert (row["verdict"], row["confidence"], row["reason_code"]) == \
        ("CONTRADICTED", "high", "outside_tolerance")
    assert [s["is_url"] for s in row["sources"]] == [False, True]
    assert row["sources"][0]["record_date"] == "2026-11-01"


def test_claims_page_renders_links(conn, db_path):
    from core.config import load_rules
    make_decided_run(conn, load_rules())
    at = open_app(db_path, "Claims")
    assert at.dataframe[0].value["verdict"].tolist() == ["CONTRADICTED"]
    text = " ".join(m.value for m in at.markdown)
    assert "[https://locus.sh/about](https://locus.sh/about)" in text
    assert "`/screener/company`" in text and "2026-11-01" in text
