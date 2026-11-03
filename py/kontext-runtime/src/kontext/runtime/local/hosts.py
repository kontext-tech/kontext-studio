"""Host and bind helpers shared by the local server, guard, and CLI."""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlsplit

ALLOWED_HOSTS_ENV = "KONTEXT_ALLOWED_HOSTS"

LOOPBACK_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1"})

_WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", "[::]"})


def normalize_host(value: str | None) -> str | None:
    """Return a comparable hostname from a Host header, origin, or bind value."""
    if not value:
        return None

    raw = value.strip()
    if not raw:
        return None

    if "://" in raw:
        try:
            return urlsplit(raw).hostname
        except ValueError:
            return None

    if raw.startswith("["):
        try:
            return urlsplit("//" + raw).hostname
        except ValueError:
            return None

    try:
        return ipaddress.ip_address(raw).compressed
    except ValueError:
        pass

    try:
        return urlsplit("//" + raw).hostname
    except ValueError:
        return None


def is_loopback_host(host: str) -> bool:
    """Whether *host* names this machine's loopback interface."""
    return normalize_host(host) in LOOPBACK_HOSTNAMES


def browser_host(host: str) -> str:
    """Return a browser-openable address, bracketing IPv6 literals."""
    raw = host.strip()
    if raw in _WILDCARD_HOSTS:
        return "127.0.0.1"

    try:
        address = ipaddress.ip_address(raw.strip("[]"))
    except ValueError:
        return raw
    return f"[{address.compressed}]" if address.version == 6 else address.compressed


def local_interface_hostnames() -> set[str]:
    """Return this machine's names and addresses for wildcard binds."""
    candidates = {socket.gethostname(), socket.getfqdn()}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            candidates.add(str(info[4][0]))
    except OSError:
        pass

    # ``gethostname`` resolution often only yields loopback. A UDP connect
    # reports the interface address the host would use without sending traffic.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            candidates.add(probe.getsockname()[0])
    except OSError:
        pass

    hostnames: set[str] = set()
    for candidate in candidates:
        if "%" in candidate:
            continue
        hostname = normalize_host(candidate)
        if hostname:
            hostnames.add(hostname)
    return hostnames


def configure_allowed_hosts(bind_host: str) -> set[str]:
    """Add the bind address (or all local interfaces) to the Host allowlist."""
    allowed = {
        entry.strip() for entry in os.getenv(ALLOWED_HOSTS_ENV, "").split(",") if entry.strip()
    }

    if bind_host.strip() in _WILDCARD_HOSTS:
        allowed |= local_interface_hostnames()
    elif not is_loopback_host(bind_host):
        normalized = normalize_host(bind_host)
        if normalized:
            allowed.add(normalized)

    os.environ[ALLOWED_HOSTS_ENV] = ",".join(sorted(allowed))
    return allowed
