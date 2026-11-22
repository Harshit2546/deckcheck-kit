"""Extract text per slide from a pitch deck PDF.

Who calls it: extract/claims.py.
What it calls: pypdf.PdfReader, core/log.py (log_step, log_error).
Returns a dict mapping 1-based slide numbers (int) to extracted slide text (str).
"""

from __future__ import annotations

from pathlib import Path

from core.log import log_error, log_step


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
        log_error(run_id, None, "extract_pdf", f"file_not_found: {path}")
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
        log_error(run_id, None, "extract_pdf", str(exc), path=str(path))
        raise ValueError(f"Failed to read PDF {path}: {exc}") from exc

    log_step(
        run_id,
        None,
        "extract_pdf",
        "ok",
        slide_count=len(slides),
        non_empty_slides=sum(1 for t in slides.values() if t.strip()),
    )
    return slides
