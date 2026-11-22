"""Tests for sources/pages.py: visible text and the page's own publish date (HTML fixtures)."""

from pathlib import Path

import pytest

from sources.pages import page_text, published_date

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pages"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_page_text_drops_hidden_parts_unescapes_and_collapses() -> None:
    text = page_text(_html("jsonld_graph.html"))
    assert "India's logistics market" in text
    assert "The market was worth ₹75,000 crore in 2023." in text
    assert "It may grow further." in text
    for hidden in ("do not show", "Enable JavaScript", "color: red", "datePublished", "Tab title"):
        assert hidden not in text
    assert "  " not in text and "\n" not in text


def test_page_text_keeps_block_boundaries_apart() -> None:
    assert page_text("<p>one</p><p>two</p><div>three<br>four</div>") == "one two three four"
    assert page_text("<p>R<b>s 5</b> crore</p>") == "Rs 5 crore"
    assert page_text("") == ""


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        # JSON-LD inside @graph beats article:published_time and <time>; date as written, no UTC shift
        ("jsonld_graph.html", ("2024-03-05", "json-ld[datePublished]")),
        # JSON-LD in a top-level list, written as text
        ("jsonld_list.html", ("2024-03-05", "json-ld[datePublished]")),
        # invalid JSON-LD is skipped; article:published_time beats meta name=pubdate
        ("meta_property.html", ("2022-11-15", "meta[property=article:published_time]")),
        # meta name matched case-insensitively, slash dates read, beats <time>
        ("meta_name.html", ("2021-07-04", "meta[name=dc.date]")),
        # first <time datetime> only; an unreadable value falls through
        ("time_only.html", (None, None)),
        # dateModified is never used, and there is no fallback to today
        ("no_date.html", (None, None)),
    ],
)
def test_published_date_priority(fixture: str, expected: tuple[str | None, str | None]) -> None:
    assert published_date(_html(fixture)) == expected


def test_published_date_unreadable_high_priority_falls_through() -> None:
    html = ('<script type="application/ld+json">{"datePublished": "sometime"}</script>'
            '<meta name="citation_publication_date" content="2019/3/7">')
    assert published_date(html) == ("2019-03-07", "meta[name=citation_publication_date]")


def test_published_date_time_tag_and_invalid_calendar_date() -> None:
    assert published_date('<time datetime="2020-02-29T10:00">x</time>') == ("2020-02-29", "time[datetime]")
    assert published_date('<meta name="date" content="2023-02-30">') == (None, None)
    assert published_date("") == (None, None)
