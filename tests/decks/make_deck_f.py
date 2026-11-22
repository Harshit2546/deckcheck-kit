"""Generate the synthetic three-slide Locus founder PDF (deck F, T36) for DeckCheck's test suite.
Run this script directly to regenerate deck_f.pdf beside it.
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
FOOTER = "Synthetic test deck for DeckCheck. Not issued by Locus."
SLIDES = (
    "Locus: the founding team. Deck date 15 November 2026.",
    "Our co-founder and CEO Nishith Rastogi previously worked at Amazon.",
    "Nishith Rastogi was a Software Development Engineer at Amazon.",
)


def _pdf_date(_year: int, _month: int, _day: int, _hour: int, _minute: int, _second: int) -> str:
    return f"D:{DECK_DATE:%Y%m%d}000000Z"


def make_deck(path: Path) -> None:
    """Write Deck F to path with stable metadata and one text line per slide."""
    rl_config.useA85 = 0  # Keep Flate streams binary so Git preserves the PDF bytes.
    width, height = PAGE_SIZE
    pdf = Canvas(str(path), pagesize=PAGE_SIZE, invariant=1, pageCompression=1)
    pdf.setTitle("Deck F - Locus founder synthetic test fixture")
    pdf.setAuthor("DeckCheck")
    pdf.setSubject(FOOTER)
    pdf.setDateFormatter(_pdf_date)

    for number, text in enumerate(SLIDES, start=1):
        pdf.setFillColor(HexColor("#F6F8FB"))
        pdf.rect(0, 0, width, height, stroke=0, fill=1)
        pdf.setFillColor(HexColor("#197278"))
        pdf.rect(MARGIN, height / 2 + 51, 48, 5, stroke=0, fill=1)
        pdf.setFillColor(HexColor("#14283D"))
        preferred_size = 26 if number == 1 else 31
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
    make_deck(Path(__file__).with_name("deck_f.pdf"))
