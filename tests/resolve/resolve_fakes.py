"""Test-only builders for Crustdata-shaped payloads and a scriptable fake `sources.crust` (tests only).

Called by: tests/resolve/conftest.py and test_entities.py. Calls: core/models.py.
Payload shapes follow docs/crustdata_fields.md (unverified against a live response, T02 pending).
"""

from __future__ import annotations

import sys
import types
from typing import Any

from core.models import Run, RunContext, RunInput


def company(cid: str = "co-1", name: str = "Acme Technologies Pvt Ltd", domain: str = "acme.example",
            founders: list[tuple[str, str]] | None = None, all_domains: list[str] | None = None) -> dict[str, Any]:
    return {"crustdata_company_id": cid,
            "basic_info": {"name": name, "primary_domain": domain, "all_domains": all_domains or [domain]},
            "people": {"founders": [{"crustdata_person_id": pid, "basic_profile": {"name": n}}
                                    for pid, n in (founders or [])]}}


def company_payload(*records: dict[str, Any]) -> dict[str, Any]:
    return {"matches": [{"company_data": r, "confidence_score": 0.9} for r in records]}


def person(pid: str, name: str, url: str | None = None, companies: list[tuple[str, str]] | None = None,
           email: str | None = None) -> dict[str, Any]:
    rec: dict[str, Any] = {"crustdata_person_id": pid, "basic_profile": {"name": name},
                           "experience": {"employment_details": {
                               "current": [{"crustdata_company_id": cid, "name": cname, "title": "CEO"}
                                           for cid, cname in (companies or [])], "past": []}}}
    if url:
        rec["social_handles"] = {"professional_network_identifier": {"profile_url": url}}
    if email:
        rec["contact"] = {"email": email}     # contact field that must never reach the output
    return rec


def people_payload(*records: dict[str, Any]) -> dict[str, Any]:
    return {"matches": [{"person_data": r, "match_status": "matched"} for r in records]}


def search_payload(*records: dict[str, Any]) -> dict[str, Any]:
    return {"profiles": list(records), "total_count": len(records)}


class FakeCrust:
    """Scriptable replacement for sources.crust. Set the three `*_result` attributes; calls are recorded."""

    def __init__(self) -> None:
        self.company_result: Any = None
        self.people_result: Any = None
        self.search_results: dict[str, Any] = {}     # deck name -> payload
        self.calls: list[tuple[str, Any]] = []
        self.raise_on: dict[str, Exception] = {}

    def get_company(self, ctx: RunContext, domain: str) -> tuple[Any, str]:
        self.calls.append(("get_company", domain))
        if "get_company" in self.raise_on:
            raise self.raise_on["get_company"]
        return self.company_result, "call-company"

    def get_people(self, ctx: RunContext, urls: list[str]) -> tuple[Any, str]:
        self.calls.append(("get_people", list(urls)))
        return self.people_result, "call-people"

    def search_people(self, ctx: RunContext, name: str, company_id: str) -> tuple[Any, str]:
        self.calls.append(("search_people", (name, company_id)))
        return self.search_results.get(name), f"call-search-{len(self.calls)}"

    def install(self, monkeypatch: Any) -> None:
        pkg = sys.modules.get("sources") or types.ModuleType("sources")
        mod = types.ModuleType("sources.crust")
        mod.get_company, mod.get_people, mod.search_people = self.get_company, self.get_people, self.search_people
        monkeypatch.setitem(sys.modules, "sources", pkg)
        monkeypatch.setitem(sys.modules, "sources.crust", mod)
        monkeypatch.setattr(pkg, "crust", mod, raising=False)

    def names(self) -> list[str]:
        return [c[0] for c in self.calls]


def make_ctx(rules: dict[str, Any], domain: str = "acme.example", founder_urls: list[str] | None = None) -> RunContext:
    run = Run(id="run_1", input=RunInput("deck.pdf", domain, "2026-01-15", founder_urls=founder_urls or []))
    return RunContext(conn=None, rules=rules, run=run, entities={})
