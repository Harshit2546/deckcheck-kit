"""T01 tests: io/adapter.py loads by file path and maps a kit request to RunInput.

Called by: pytest. Calls: core/adapter_loader.py, io/adapter.py.
"""

import pytest

from core.adapter_loader import load_adapter


def test_from_kit_maps_input():
    adapter = load_adapter()
    run_input = adapter.from_kit({"deck_path": "d.pdf", "company_domain": "Example.COM",
                                  "founder_profile_urls": ["https://x/in/a"]})
    assert run_input.domain == "example.com"
    assert run_input.deck_date is None and run_input.deck_date_source == "missing"
    assert run_input.founder_urls == ["https://x/in/a"]


def test_from_kit_rejects_missing_domain():
    with pytest.raises(ValueError, match="domain"):
        load_adapter().from_kit({"deck_path": "d.pdf"})
