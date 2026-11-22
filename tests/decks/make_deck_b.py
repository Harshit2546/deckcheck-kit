"""Generate the synthetic eight-slide Shadowfax PDF for DeckCheck's test suite.
Run this script directly to regenerate deck_b.pdf beside it.
Uses ReportLab and stores each slide's content as selectable text.
"""

from datetime import date
from pathlib import Path

from reportlab import rl_config
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas


DECK_DATE = date(2026, 11, 15)
PAGE_SIZE = (960, 540)
MARGIN = 64
FOOTER = "Synthetic test deck for DeckCheck. Not issued by Shadowfax."
SLIDES = (
    "Shadowfax: Full-stack logistics network for India. Deck date 15 November 2026.",
    "Shadowfax employs a core team of 1500 professionals.",
    "We closed a $60M Series D funding round in December 2019.",
    "Total funding across all institutional rounds exceeds $120M.",
    "Over 5000 full-time corporate staff in Bengaluru HQ.",
    "Partnered with Flipkart to power pan-India express logistics.",
    "India's hyperlocal delivery market is projected at $12B by 2027.",
    "Headcount has doubled with 100% year-on-year team growth.",
)


def _pdf_date(_year: int, _month: int, _day: int, _hour: int, _minute: int, _second: int) -> str:
    return f"D:{DECK_DATE:%Y%m%d}000000Z"


def make_deck(path: Path) -> None:
    """Write Deck B to path with stable metadata and one text line per slide."""
    rl_config.useA85 = 0
    width, height = PAGE_SIZE
    pdf = Canvas(str(path), pagesize=PAGE_SIZE, invariant=1, pageCompression=1)
    pdf.setTitle("Deck B - Shadowfax synthetic test fixture")
    pdf.setAuthor("DeckCheck")
    pdf.setSubject(FOOTER)
    pdf.setDateFormatter(_pdf_date)

    for number, text in enumerate(SLIDES, start=1):
        pdf.setFillColor(HexColor("#F6F8FB"))
        pdf.rect(0, 0, width, height, stroke=0, fill=1)
        pdf.setFillColor(HexColor("#1E56A0"))
        pdf.rect(MARGIN, height / 2 + 51, 48, 5, stroke=0, fill=1)
        pdf.setFillColor(HexColor("#163172"))
        preferred_size = 24 if number == 1 else 28
        available_width = width - 2 * MARGIN - 16
        font_size = min(preferred_size, available_width / stringWidth(text, "Helvetica-Bold", 1))
        pdf.setFont("Helvetica-Bold", font_size)
        pdf.drawString(MARGIN, height / 2, text)

        pdf.setStrokeColor(HexColor("#B8C6D3"))
        pdf.line(MARGIN, 57, width - MARGIN, 57)
        pdf.setFillColor(HexColor("#334C64"))
        pdf.setFont("Helvetica", 12)
        pdf.drawString(MARGIN, 34, FOOTER)
        pdf.showPage()

    pdf.save()


if __name__ == "__main__":
    make_deck(Path(__file__).with_name("deck_b.pdf"))
