"""Tests for extract/pdf.py."""

from pathlib import Path
import pytest
from reportlab.pdfgen import canvas

from extract.pdf import extract_pdf_slides, extract_slides, extract_text_per_slide


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a 3-page test pitch deck PDF."""
    pdf_path = tmp_path / "sample_deck.pdf"
    c = canvas.Canvas(str(pdf_path))

    # Slide 1: Title & Team
    c.drawString(100, 750, "LogiFlow Solutions - Series A Pitch")
    c.drawString(100, 720, "Team of 42 full-time employees across India.")
    c.showPage()

    # Slide 2: Funding & Growth
    c.drawString(100, 750, "Financial Traction")
    c.drawString(100, 720, "Raised 2M USD in Seed round led by Venture Partners in 2023.")
    c.drawString(100, 690, "ARR grew 150% year over year.")
    c.showPage()

    # Slide 3: Market Size
    c.drawString(100, 750, "Market Opportunity")
    c.drawString(100, 720, "India 3PL logistics market estimated at 215B USD by 2028.")
    c.showPage()

    c.save()
    return pdf_path


def test_extract_pdf_slides_success(sample_pdf: Path) -> None:
    slides = extract_pdf_slides(sample_pdf, run_id="test_run_1")
    assert len(slides) == 3
    assert 1 in slides
    assert 2 in slides
    assert 3 in slides

    assert "LogiFlow Solutions" in slides[1]
    assert "42 full-time employees" in slides[1]
    assert "Financial Traction" in slides[2]
    assert "2M USD in Seed" in slides[2]
    assert "Market Opportunity" in slides[3]
    assert "215B USD" in slides[3]


def test_extract_pdf_aliases(sample_pdf: Path) -> None:
    assert extract_slides(sample_pdf) == extract_pdf_slides(sample_pdf)
    assert extract_text_per_slide(sample_pdf) == extract_pdf_slides(sample_pdf)


def test_extract_pdf_non_existent(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        extract_pdf_slides(tmp_path / "non_existent.pdf")


def test_extract_pdf_invalid_file(tmp_path: Path) -> None:
    invalid_file = tmp_path / "not_a_pdf.pdf"
    invalid_file.write_text("This is not a PDF content", encoding="utf-8")
    with pytest.raises(ValueError):
        extract_pdf_slides(invalid_file)
