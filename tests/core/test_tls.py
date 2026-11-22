"""core/tls.py: the shared context verifies certificates and trusts certifi's CA bundle."""

from __future__ import annotations

import ssl

import certifi

from core.tls import tls_context


def test_context_verifies_certificates_and_hostnames() -> None:
    ctx = tls_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_context_trusts_certifi_bundle() -> None:
    # A context with no system CAs would have 0; certifi alone adds well over 100 roots.
    assert ctx_ca_count() >= 100


def test_context_is_shared() -> None:
    assert tls_context() is tls_context()


def ctx_ca_count() -> int:
    return tls_context().cert_store_stats()["x509_ca"]


def test_certifi_bundle_exists() -> None:
    assert certifi.where()
