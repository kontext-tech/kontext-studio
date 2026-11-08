"""Tests for the desktop launch mode and parent watchdog."""

from __future__ import annotations

import json
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from kontext.labs import desktop
from kontext.labs.cli import cli
from kontext.labs.parent_watchdog import process_exists, start_parent_watchdog


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class TestPortSelection:
    def test_uses_preferred_port_when_free(self) -> None:
        port = _free_port()
        assert desktop._choose_port("127.0.0.1", port) == port

    def test_falls_back_when_preferred_is_busy(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = int(listener.getsockname()[1])
            assert desktop._choose_port("127.0.0.1", port) == 0

    def test_zero_stays_ephemeral(self) -> None:
        assert desktop._choose_port("127.0.0.1", 0) == 0


class TestBoundPort:
    def test_reads_first_socket(self) -> None:
        server = SimpleNamespace(
            servers=[
                SimpleNamespace(sockets=[SimpleNamespace(getsockname=lambda: ("127.0.0.1", 4321))])
            ]
        )
        assert desktop._bound_port(server) == 4321

    def test_raises_without_sockets(self) -> None:
        with pytest.raises(RuntimeError, match="bound socket"):
            desktop._bound_port(SimpleNamespace(servers=[]))


class TestReadyHandshake:
    def test_prints_ready_payload(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        persist = MagicMock()
        monkeypatch.setattr(
            "kontext.runtime.local.launch_token.persist_launch_token",
            persist,
        )

        server = SimpleNamespace(
            started=True,
            should_exit=False,
            servers=[
                SimpleNamespace(sockets=[SimpleNamespace(getsockname=lambda: ("127.0.0.1", 4321))])
            ],
        )

        desktop._announce_when_ready(server, "test-token", "127.0.0.1")

        output = capsys.readouterr().out
        line = next(line for line in output.splitlines() if line.startswith(desktop.READY_MARKER))
        payload = json.loads(line[len(desktop.READY_MARKER) :])

        assert payload["event"] == "ready"
        assert payload["port"] == 4321
        assert payload["url"] == "http://127.0.0.1:4321"
        assert payload["launchUrl"] == "http://127.0.0.1:4321/#token=test-token"
        assert payload["pid"] == os.getpid()
        assert "version" not in payload
        persist.assert_called_once_with("test-token", port=4321)


class TestDesktopCommand:
    def test_cli_dispatches_desktop(self) -> None:
        with (
            patch("kontext.labs.desktop.run_desktop") as run_desktop,
            patch(
                "sys.argv",
                [
                    "kontext",
                    "desktop",
                    "--preferred-port",
                    "0",
                    "--parent-pid",
                    "123",
                ],
            ),
        ):
            cli()

        args = run_desktop.call_args[0][0]
        assert args.host == "127.0.0.1"
        assert args.preferred_port == 0
        assert args.parent_pid == 123
        assert args.no_worker is False

    def test_graceful_signal_handlers_restore_previous(self) -> None:
        previous = signal.getsignal(signal.SIGTERM)
        server = SimpleNamespace(should_exit=False)

        with desktop._graceful_signal_handlers(server):
            assert signal.getsignal(signal.SIGTERM) is not previous

        assert signal.getsignal(signal.SIGTERM) is previous

    @pytest.mark.integration
    def test_desktop_process_handshake_and_shutdown(self, tmp_path) -> None:
        env = dict(os.environ)
        env["HOME"] = str(tmp_path)
        env["USERPROFILE"] = str(tmp_path)
        env["KONTEXT_LOCAL_WORKER_ENABLED"] = "false"
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "kontext.labs",
                "desktop",
                "--preferred-port",
                "0",
                "--parent-pid",
                str(os.getpid()),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        lines: queue.Queue[str] = queue.Queue()
        stderr_lines: list[str] = []

        def _read_stdout() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                lines.put(line)

        def _read_stderr() -> None:
            assert process.stderr is not None
            for line in process.stderr:
                stderr_lines.append(line)

        threading.Thread(target=_read_stdout, daemon=True).start()
        threading.Thread(target=_read_stderr, daemon=True).start()

        payload = None
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if line.startswith(desktop.READY_MARKER):
                payload = json.loads(line[len(desktop.READY_MARKER) :])
                break

        try:
            assert payload is not None, "".join(stderr_lines)
            with urllib.request.urlopen(f"{payload['url']}/health", timeout=5) as response:
                assert response.status == 200
        finally:
            assert process.stdin is not None
            process.stdin.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        assert process.returncode == 0, "".join(stderr_lines)


class TestParentWatchdog:
    def test_process_exists_for_current_process(self) -> None:
        assert process_exists(os.getpid())

    def test_watchdog_fires_when_parent_disappears(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("KONTEXT_PARENT_PID", "424242")
        monkeypatch.setattr(
            "kontext.labs.parent_watchdog.process_exists",
            lambda _pid: False,
        )
        fired: list[bool] = []

        stop = start_parent_watchdog(
            lambda: fired.append(True),
            poll_interval_seconds=0.01,
        )
        deadline = time.monotonic() + 2
        while not fired and time.monotonic() < deadline:
            time.sleep(0.01)
        stop()

        assert fired == [True]

    def test_watchdog_stays_quiet_while_parent_lives(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("KONTEXT_PARENT_PID", str(os.getpid()))
        fired: list[bool] = []

        stop = start_parent_watchdog(
            lambda: fired.append(True),
            poll_interval_seconds=0.01,
        )
        time.sleep(0.1)
        stop()

        assert fired == []
