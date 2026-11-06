"""Tests for local host/bind helpers."""

from __future__ import annotations

from kontext.runtime.local.hosts import (
    browser_host,
    configure_allowed_hosts,
    is_loopback_host,
    normalize_host,
)


def test_normalize_host_handles_ports_origins_and_ipv6():
    assert normalize_host("127.0.0.1:8000") == "127.0.0.1"
    assert normalize_host("[fd00::1]:8000") == "fd00::1"
    assert normalize_host("fd00::1") == "fd00::1"
    assert normalize_host("https://app.example.com:8443") == "app.example.com"


def test_browser_host_brackets_ipv6_and_maps_wildcards():
    assert browser_host("0.0.0.0") == "127.0.0.1"
    assert browser_host("::") == "127.0.0.1"
    assert browser_host("::1") == "[::1]"
    assert browser_host("fd00::1") == "[fd00::1]"
    assert browser_host("127.0.0.1") == "127.0.0.1"


def test_is_loopback_host():
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("[::1]")
    assert is_loopback_host("localhost")
    assert not is_loopback_host("fd00::1")


def test_configure_allowed_hosts_adds_explicit_bind_host(monkeypatch):
    monkeypatch.setenv("KONTEXT_ALLOWED_HOSTS", "existing.host")

    allowed = configure_allowed_hosts("192.168.1.5")

    assert {"existing.host", "192.168.1.5"} <= allowed
