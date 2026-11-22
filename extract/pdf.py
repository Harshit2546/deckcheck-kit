"""Extract text per slide from a pitch deck PDF.

Who calls it: core/runner.py, cli.py, and extract/claims.py.
What it calls: pypdf (PdfReader), core/log (log_step), and optional fitz fallback.
Returns a dict mapping 1-based slide numbers (int) to extracted slide text (str).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.log import log_step


def extract_pdf_slides(pdf_path: str | Path, run_id: str | None = None) -> dict[int, str]:
    """Extract slide text from a PDF, returning a dictionary keyed by 1-based slide number.

    Args:
        pdf_path: Path to the PDF file.
        run_id: Optional run id for logging.

    Returns:
        dict[int, str]: Mapping of 1-based slide number to slide text.

    Raises:
        FileNotFoundError: If the PDF file does not exist.
        ValueError: If the file is not a valid PDF or is unreadable.
    """
    path = Path(pdf_path)
    if not path.is_file():
        log_step(run_id, "extract_pdf", "error", error="file_not_found", path=str(path))
        raise FileNotFoundError(f"PDF file not found: {path}")

    slides: dict[int, str] = {}

    try:
        import pypdf

        reader = pypdf.PdfReader(str(path))
        for idx, page in enumerate(reader.pages):
            slide_no = idx + 1
            text = page.extract_text() or ""
            slides[slide_no] = text

    except Exception as exc:
        # Attempt fallback to fitz/pymupdf if available
        try:
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz

            doc = fitz.open(str(path))
            for idx, page in enumerate(doc):
                slide_no = idx + 1
                text = page.get_text() or ""
                slides[slide_no] = text
            doc.close()
        except Exception:
            log_step(run_id, "extract_pdf", "error", error=str(exc), path=str(path))
            raise ValueError(f"Failed to read PDF {path}: {exc}") from exc

    # If all slides extracted to empty strings with pypdf, try pymupdf fallback in case pypdf missed fonts
    if slides and all(not text.strip() for text in slides.values()):
        try:
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz

            doc = fitz.open(str(path))
            fitz_slides: dict[int, str] = {}
            for idx, page in enumerate(doc):
                slide_no = idx + 1
                text = page.get_text() or ""
                fitz_slides[slide_no] = text
            doc.close()
            if any(text.strip() for text in fitz_slides.values()):
                slides = fitz_slides
        except Exception:
            pass

    log_step(
        run_id,
        "extract_pdf",
        "ok",
        slide_count=len(slides),
        non_empty_slides=sum(1 for t in slides.values() if t.strip()),
    )
    return slides


# Aliases for convenience
extract_slides = extract_pdf_slides
extract_text_per_slide = extract_pdf_slides
