"""Read visible text and the page's own publish date from fetched HTML (pure functions, no I/O).

Who calls it: checkers/market_size.py and checkers/customer.py (T32), on pages from sources/web.fetch.
What it calls: only the stdlib (html.parser, json, re, datetime). Web search results carry no
publish date (docs/WEB_SOURCE.md section 1), so the record date of a web fact comes from here.
It never falls back to the fetch time or today's date: no readable date gives (None, None).
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any

_SKIP_TAGS = {"script", "style", "noscript", "template", "title"}
_BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption",
    "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li",
    "main", "nav", "ol", "p", "pre", "section", "table", "td", "th", "tr", "ul",
}
_DATE_META_NAMES = ("date", "pubdate", "publish-date", "dc.date", "citation_publication_date")
_TEXT_DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y")


class _TextParser(HTMLParser):
    """Collects text outside script/style/noscript; block tags become spaces."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


class _DateParser(HTMLParser):
    """Collects every date candidate; published_date picks by priority afterwards."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.jsonld: list[str] = []
        self.meta_property: list[str] = []
        self.meta_name: list[tuple[str, str]] = []
        self.time_datetime: list[str] = []
        self._in_jsonld = False
        self._jsonld_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and a.get("type", "").strip().lower() == "application/ld+json":
            self._in_jsonld = True
            self._jsonld_buf = []
        elif tag == "meta":
            content = a.get("content", "")
            if a.get("property", "").strip().lower() == "article:published_time":
                self.meta_property.append(content)
            name = a.get("name", "").strip().lower()
            if name in _DATE_META_NAMES:
                self.meta_name.append((name, content))
        elif tag == "time" and "datetime" in a:
            self.time_datetime.append(a["datetime"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._jsonld_buf))
            self._in_jsonld = False

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._jsonld_buf.append(data)


def page_text(html: str) -> str:
    """Visible text: drop script/style/noscript, unescape entities, collapse whitespace."""
    parser = _TextParser()
    parser.feed(html or "")
    parser.close()
    return " ".join("".join(parser.parts).split())


def _to_iso_date(raw: str) -> str | None:
    """'2024-03-05T10:00:00+05:30', '2024/03/05', 'March 5, 2024' -> '2024-03-05'. Date as written,
    never shifted to UTC. Anything else -> None."""
    s = (raw or "").strip()
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?!\d)", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    for fmt in _TEXT_DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _jsonld_dates(node: Any) -> list[str]:
    """Every "datePublished" value in a JSON-LD tree (dicts, lists, @graph), in document order."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "datePublished" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_jsonld_dates(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_jsonld_dates(item))
    return found


def _candidates(parser: _DateParser) -> list[tuple[str, str]]:
    """(raw value, where_found) in priority order: JSON-LD, article:published_time, meta name, <time>."""
    out: list[tuple[str, str]] = []
    for block in parser.jsonld:
        try:
            data = json.loads(block)
        except (ValueError, TypeError):
            continue
        out.extend((v, "json-ld[datePublished]") for v in _jsonld_dates(data))
    out.extend((v, "meta[property=article:published_time]") for v in parser.meta_property)
    for wanted in _DATE_META_NAMES:
        out.extend((v, f"meta[name={wanted}]") for n, v in parser.meta_name if n == wanted)
    if parser.time_datetime:
        out.append((parser.time_datetime[0], "time[datetime]"))
    return out


def published_date(html: str) -> tuple[str | None, str | None]:
    """('YYYY-MM-DD', where_found) or (None, None). First readable hit in priority order wins:
    JSON-LD "datePublished"; meta property="article:published_time"; meta name in
    (date, pubdate, publish-date, dc.date, citation_publication_date); the first <time datetime>.
    An unreadable value falls through to the next candidate. dateModified is never used."""
    parser = _DateParser()
    parser.feed(html or "")
    parser.close()
    for raw, where in _candidates(parser):
        iso = _to_iso_date(raw)
        if iso is not None:
            return iso, where
    return None, None
