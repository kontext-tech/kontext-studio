"""Kernel wire protocol primitives.

The Kontext kernel protocol is a small, dependency-free messaging model
inspired by interactive kernel conventions. Four loopback sockets are used:

* ``shell``   request/reply for :class:`execute_request` / :class:`kernel_info_request`
* ``iopub``   one-way broadcast of stream, display and status messages
* ``control`` out-of-band interrupt/shutdown, plus host-call request/reply
* ``heartbeat`` simple liveness echo

A *connection file* describes the socket addresses and carries a shared auth
token, following the same connection-file contract without a ZeroMQ
dependency.

Wire format
-----------
Every message is a single JSON object followed by ``b"\\n"``::

    {"msg_id": "...", "msg_type": "execute_request", "channel": "shell",
     "parent_id": null, "content": {...}}

``json.dumps`` escapes embedded newlines, so newline framing is unambiguous.
The stdlib-only child harness (``harness.py``) mirrors these constants and
framing rules; keep the two in sync when the protocol changes.
"""

from __future__ import annotations

import contextlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "1.0"
KERNEL_NAME = "kontext-python"

SHELL = "shell"
IOPUB = "iopub"
CONTROL = "control"
HEARTBEAT = "heartbeat"

# Message types used on the parent side. The stdlib-only child harness mirrors
# these as literals (it cannot import this package); keep the two in sync.
EXECUTE_REQUEST = "execute_request"
EXECUTE_REPLY = "execute_reply"
KERNEL_INFO_REQUEST = "kernel_info_request"
KERNEL_INFO_REPLY = "kernel_info_reply"
INTERRUPT_REQUEST = "interrupt_request"
SHUTDOWN_REQUEST = "shutdown_request"
HOST_CALL_REQUEST = "host_call_request"
HOST_CALL_REPLY = "host_call_reply"
HELLO = "hello"
HELLO_ACK = "hello_ack"
STREAM = "stream"
EXECUTE_RESULT = "execute_result"
ERROR = "error"


def new_message(
    msg_type: str,
    content: dict[str, Any],
    *,
    channel: str,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Build a protocol message envelope."""
    return {
        "msg_id": uuid.uuid4().hex,
        "msg_type": msg_type,
        "channel": channel,
        "parent_id": parent_id,
        "content": content,
    }


def parse_line(line: bytes) -> dict[str, Any]:
    """Parse a newline-terminated JSON line into a message envelope."""
    parsed = json.loads(line.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Kernel message must be a JSON object")
    return parsed


@dataclass(frozen=True)
class KernelConnectionInfo:
    """Addresses and auth token for a running kernel, persisted as JSON."""

    ip: str
    shell_port: int
    iopub_port: int
    control_port: int
    heartbeat_port: int
    key: str
    transport: str = "tcp"
    kernel_name: str = KERNEL_NAME
    version: str = PROTOCOL_VERSION

    def port(self, channel: str) -> int:
        ports = {
            SHELL: self.shell_port,
            IOPUB: self.iopub_port,
            CONTROL: self.control_port,
            HEARTBEAT: self.heartbeat_port,
        }
        return ports[channel]

    def to_json(self) -> str:
        return json.dumps(
            {
                "transport": self.transport,
                "ip": self.ip,
                "shell_port": self.shell_port,
                "iopub_port": self.iopub_port,
                "control_port": self.control_port,
                "heartbeat_port": self.heartbeat_port,
                "key": self.key,
                "kernel_name": self.kernel_name,
                "version": self.version,
            }
        )

    def write(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")
        # The connection file carries the auth key; keep it owner-only so other
        # local users cannot connect to the kernel.
        with contextlib.suppress(OSError):
            os.chmod(path, 0o600)

    @classmethod
    def read(cls, path: Path) -> KernelConnectionInfo:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            ip=str(payload["ip"]),
            shell_port=int(payload["shell_port"]),
            iopub_port=int(payload["iopub_port"]),
            control_port=int(payload["control_port"]),
            heartbeat_port=int(payload["heartbeat_port"]),
            key=str(payload["key"]),
            transport=str(payload.get("transport", "tcp")),
            kernel_name=str(payload.get("kernel_name", KERNEL_NAME)),
            version=str(payload.get("version", PROTOCOL_VERSION)),
        )
