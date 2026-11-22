"""extract module: extracts slide text and claims from pitch deck PDFs.

Who calls it: core/runner.py, cli.py.
What it calls: extract/pdf.py, extract/claims.py.
"""

from extract.claims import extract_claims, verify_claim_quote, verify_claim_quotes
from extract.pdf import extract_pdf_slides, extract_slides, extract_text_per_slide

__all__ = [
    "extract_claims",
    "extract_pdf_slides",
    "extract_slides",
    "extract_text_per_slide",
    "verify_claim_quote",
    "verify_claim_quotes",
]
