"""Tests for local launch-token and signing-key file handling."""

from __future__ import annotations

import stat

from kontext.runtime.local import auth as local_auth
from kontext.runtime.local import launch_token


def _mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_configured_token_wins_and_is_verified(monkeypatch, tmp_path):
    monkeypatch.setenv(launch_token.LAUNCH_TOKEN_ENV, "env-token")
    monkeypatch.setattr("kontext.runtime.local.config.get_local_data_dir", lambda: tmp_path)

    assert launch_token.get_launch_token() == "env-token"
    assert not (tmp_path / "runtime" / "launch.token").exists()
    assert launch_token.verify_launch_token("env-token")
    assert not launch_token.verify_launch_token("wrong-token")
    assert not launch_token.verify_launch_token("héllo")
    assert not launch_token.verify_launch_token(None)


def test_file_fallback_is_owner_only_and_stable(monkeypatch, tmp_path):
    monkeypatch.delenv(launch_token.LAUNCH_TOKEN_ENV, raising=False)
    monkeypatch.setattr("kontext.runtime.local.config.get_local_data_dir", lambda: tmp_path)

    token = launch_token.get_launch_token()

    runtime_dir = tmp_path / "runtime"
    token_file = runtime_dir / "launch.token"
    assert token
    assert token_file.read_text(encoding="utf-8").strip() == token
    assert _mode(runtime_dir) == 0o700
    assert _mode(token_file) == 0o600
    assert launch_token.get_launch_token() == token
    assert launch_token.verify_launch_token(token)


def test_empty_token_file_is_repaired(monkeypatch, tmp_path):
    monkeypatch.delenv(launch_token.LAUNCH_TOKEN_ENV, raising=False)
    monkeypatch.setattr("kontext.runtime.local.config.get_local_data_dir", lambda: tmp_path)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(mode=0o700)
    token_file = runtime_dir / "launch.token"
    token_file.write_text("", encoding="utf-8")

    first = launch_token.get_launch_token()
    second = launch_token.get_launch_token()

    assert first == second
    assert token_file.read_text(encoding="utf-8").strip() == first
    assert launch_token.verify_launch_token(first)


def test_port_specific_token_also_updates_latest(monkeypatch, tmp_path):
    monkeypatch.setattr("kontext.runtime.local.config.get_local_data_dir", lambda: tmp_path)

    path = launch_token.persist_launch_token("port-token", port=8001)

    assert path.name == "launch-8001.token"
    assert path.read_text(encoding="utf-8").strip() == "port-token"
    assert (tmp_path / "runtime" / "launch.token").read_text(
        encoding="utf-8"
    ).strip() == "port-token"


def test_persisted_token_is_recoverable_and_owner_only(monkeypatch, tmp_path):
    monkeypatch.delenv(launch_token.LAUNCH_TOKEN_ENV, raising=False)
    monkeypatch.setattr("kontext.runtime.local.config.get_local_data_dir", lambda: tmp_path)

    path = launch_token.persist_launch_token("first-token")
    assert path.read_text(encoding="utf-8").strip() == "first-token"
    assert _mode(path) == 0o600

    launch_token.persist_launch_token("second-token")
    assert path.read_text(encoding="utf-8").strip() == "second-token"


def test_jwt_secret_file_is_owner_only(monkeypatch, tmp_path):
    key_file = tmp_path / "local.key"
    monkeypatch.setattr(local_auth, "_get_key_file", lambda: key_file)

    secret = local_auth.get_local_jwt_secret()

    assert secret
    assert key_file.read_text(encoding="utf-8").strip() == secret
    assert _mode(key_file) == 0o600
    assert local_auth.get_local_jwt_secret() == secret
