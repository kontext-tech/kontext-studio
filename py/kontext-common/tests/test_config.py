"""Settings sources: ``.env.local`` must override ``.env``.

``KontextConfig.model_config["env_file"]`` is a tuple, and pydantic-settings
merges those files in order with the *last* one winning. This pins the local
override chain documented in ``.env.example`` / ``CONTRIBUTING.md`` so the order
cannot silently flip back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kontext.common.config import KontextConfig


def test_env_local_overrides_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("KONTEXT_LOG_LEVEL=WARNING\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("KONTEXT_LOG_LEVEL=DEBUG\n", encoding="utf-8")
    # The OS environment outranks dotenv sources; clear both spellings so the
    # assertion is about file precedence only.
    monkeypatch.delenv("KONTEXT_LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.chdir(tmp_path)

    assert KontextConfig().log_level == "DEBUG"
