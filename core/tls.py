"""One verifying TLS context for every stdlib HTTPS call (sources/crust.py, sources/web.py).

Who calls it: sources/crust.py and sources/web.py pass `tls_context()` to HTTPSConnection.
What it calls: ssl, and certifi (installed with requests) when present.
The context trusts the OS store plus certifi's CA bundle, so it works on machines whose
Python has no system CAs (python.org macOS builds) while still honouring corporate roots
installed in the OS. Certificate and hostname verification are never turned off.
"""

from __future__ import annotations

import ssl
from functools import lru_cache


@lru_cache(maxsize=1)
def tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()  # OS trust store, CERT_REQUIRED, check_hostname
    try:
        import certifi
    except ImportError:
        return context
    context.load_verify_locations(cafile=certifi.where())
    return context
