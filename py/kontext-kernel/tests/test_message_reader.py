"""Tests for the kernel's newline-delimited message reader."""

from __future__ import annotations

import json
import socket
from typing import cast

import pytest

from kontext.kernel.harness import _MessageReader


class _ScriptedSocket:
    """Socket stub yielding scripted chunks, or raising scripted exceptions."""

    def __init__(self, *chunks: bytes | BaseException) -> None:
        self._chunks = list(chunks)

    def recv(self, _size: int) -> bytes:
        if not self._chunks:
            return b""
        chunk = self._chunks.pop(0)
        if isinstance(chunk, BaseException):
            raise chunk
        return chunk


def _reader(*chunks: bytes | BaseException) -> _MessageReader:
    return _MessageReader(cast(socket.socket, _ScriptedSocket(*chunks)))


def test_reader_survives_interrupt_raised_inside_recv() -> None:
    """A SIGINT while blocked in ``recv`` must not close the reader.

    The shell loop swallows that ``KeyboardInterrupt`` and keeps serving, so the
    reader has to keep its own buffer; a generator would have been closed and the
    kernel would see EOF instead.
    """
    frame = json.dumps({"msg_type": "execute_request"}).encode("utf-8") + b"\n"
    reader = _reader(KeyboardInterrupt(), frame)

    with pytest.raises(KeyboardInterrupt):
        next(reader)

    assert next(reader) == {"msg_type": "execute_request"}
    with pytest.raises(StopIteration):
        next(reader)


def test_reader_keeps_partial_frame_across_interrupt() -> None:
    """Bytes buffered before an interrupt are still framed afterwards."""
    payload = json.dumps({"msg_type": "kernel_info_request"}).encode("utf-8") + b"\n"
    split = len(payload) // 2
    reader = _reader(payload[:split], KeyboardInterrupt(), payload[split:])

    with pytest.raises(KeyboardInterrupt):
        next(reader)

    assert next(reader) == {"msg_type": "kernel_info_request"}


def test_reader_skips_blank_and_malformed_frames() -> None:
    frames = b"\n" + b"not json\n" + json.dumps({"msg_type": "status"}).encode("utf-8") + b"\n"
    reader = _reader(frames)

    assert next(reader) == {"msg_type": "status"}
    with pytest.raises(StopIteration):
        next(reader)
