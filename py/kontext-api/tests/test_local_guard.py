"""Unit tests for local-mode Host and Origin validation."""

from __future__ import annotations

from kontext.api.middleware.local_guard import allowed_hostnames


def test_allowed_hostnames_defaults_to_loopback(monkeypatch):
    monkeypatch.delenv("KONTEXT_ALLOWED_HOSTS", raising=False)

    assert allowed_hostnames() == {"127.0.0.1", "localhost", "::1"}


def test_allowed_hostnames_accepts_hosts_and_origin_urls(monkeypatch):
    monkeypatch.setenv(
        "KONTEXT_ALLOWED_HOSTS",
        "myhost.lan, https://app.example.com:8443, testserver",
    )

    allowed = allowed_hostnames()

    assert "myhost.lan" in allowed
    assert "app.example.com" in allowed
    assert "testserver" in allowed
    assert "https" not in allowed


def test_allowed_hostnames_accepts_bare_ipv6(monkeypatch):
    monkeypatch.setenv("KONTEXT_ALLOWED_HOSTS", "fd00::1")

    allowed = allowed_hostnames()

    assert "fd00::1" in allowed
    assert "fd00" not in allowed
