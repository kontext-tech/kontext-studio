"""Tests for the Kontext CLI."""

import argparse
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from kontext.labs.cli import (
    _cmd_project_create,
    _cmd_project_list,
    _cmd_serve,
    _get_project_index,
    _init_engine,
    cli,
)
from kontext.schema import ProjectModel

# ── Helpers ──────────────────────────────────────────────────────────────────


@contextmanager
def _mock_db_session():
    """Return a MagicMock session usable as a context manager."""
    session = MagicMock()
    yield session


# ── TestProjectList ──────────────────────────────────────────────────────────


class TestProjectList:
    def test_empty_index(self, capsys):
        with patch("kontext.labs.cli._init_engine") as mock_init:
            mock_init.return_value = MagicMock()
            with patch("kontext.labs.cli._get_project_index", return_value=[]):
                args = argparse.Namespace(lake_path=None)
                _cmd_project_list(args)

                out = capsys.readouterr().out
                assert "No projects" in out

    def test_list_projects(self, capsys):
        with patch("kontext.labs.cli._init_engine") as mock_init:
            mock_init.return_value = MagicMock()
            projects = [
                {
                    "id": "abc-123",
                    "project_code": "demo",
                    "project_name": "Demo Project",
                }
            ]
            with patch("kontext.labs.cli._get_project_index", return_value=projects):
                args = argparse.Namespace(lake_path=None)
                _cmd_project_list(args)

                out = capsys.readouterr().out
                assert "abc-123" in out
                assert "demo" in out
                assert "Demo Project" in out


# ── TestProjectCreate ────────────────────────────────────────────────────────


class TestProjectCreate:
    def _run(self, capsys, *, profile_id: str, name: str, code: str | None) -> str:
        """Run the create command with the project service mocked out."""
        with (
            patch("kontext.labs.cli._init_engine"),
            patch("kontext.account.read_profile") as read_profile,
            patch("kontext.project.local.create_project_service") as create_service,
        ):
            read_profile.return_value = SimpleNamespace(id=profile_id)
            create_service.return_value = ProjectModel.model_construct(
                id=str(uuid4()),
                project_name=name,
                project_code=code or "test-project",
            )
            _cmd_project_create(argparse.Namespace(lake_path=None, name=name, code=code))
        return capsys.readouterr().out

    def test_create_project(self, capsys):
        out = self._run(capsys, profile_id=str(uuid4()), name="Test Project", code=None)

        assert "Created project" in out
        assert "Test Project" in out

    def test_create_with_custom_code(self, capsys):
        out = self._run(capsys, profile_id=str(uuid4()), name="My Project", code="myproj")

        assert "Created project" in out
        assert "My Project" in out

    def test_create_uses_domain_service(self):
        with (
            patch("kontext.labs.cli._init_engine"),
            patch("kontext.account.read_profile") as read_profile,
            patch("kontext.project.local.create_project_service") as create_service,
        ):
            read_profile.return_value = SimpleNamespace(id=str(uuid4()))
            create_service.return_value = ProjectModel.model_construct(
                id=str(uuid4()), project_name="Test Project", project_code="p"
            )
            _cmd_project_create(argparse.Namespace(lake_path=None, name="Test Project", code=None))

        assert create_service.call_count == 1
        request, profile = create_service.call_args[0]
        assert request.project_name == "Test Project"
        assert request.project_code == "test-project"  # slugified name
        assert profile.id == read_profile.return_value.id

    def test_create_without_profile_fails_closed(self, capsys):
        with (
            patch("kontext.labs.cli._init_engine"),
            patch("kontext.account.read_profile", return_value=None),
            pytest.raises(SystemExit),
        ):
            _cmd_project_create(argparse.Namespace(lake_path=None, name="X", code=None))

        err = capsys.readouterr().err
        assert "No local profile" in err


# ── TestGetProjectIndex ──────────────────────────────────────────────────────


class TestGetProjectIndex:
    @pytest.fixture(autouse=True)
    def _sqlite_db(self, monkeypatch, tmp_path):
        """Set up a fresh in-memory SQLite DB for each test."""
        monkeypatch.setenv("PROJECT_DB_URL", f"sqlite:///{tmp_path}/cli_test.db")
        from kontext.data.database import Base, get_engine, get_session_factory

        get_engine.cache_clear()
        get_session_factory.cache_clear()
        Base.metadata.create_all(get_engine())
        yield
        get_engine.cache_clear()
        get_session_factory.cache_clear()

    def test_empty_returns_empty(self):
        assert _get_project_index() == []

    def test_returns_projects(self):
        from kontext.data.database import get_sync_db_session
        from kontext.data.models import Project

        pid = uuid4()
        with get_sync_db_session() as session:
            session.add(
                Project(
                    id=pid,
                    project_code="demo",
                    project_name="Demo Project",
                    is_deleted=False,
                    date_created=datetime.now(timezone.utc),
                )
            )
            session.commit()

        result = _get_project_index()
        assert len(result) == 1
        assert result[0]["project_code"] == "demo"
        assert result[0]["project_name"] == "Demo Project"

    def test_excludes_deleted(self):
        from kontext.data.database import get_sync_db_session
        from kontext.data.models import Project

        with get_sync_db_session() as session:
            session.add(
                Project(
                    id=uuid4(),
                    project_code="deleted",
                    project_name="Deleted Project",
                    is_deleted=True,
                    date_created=datetime.now(timezone.utc),
                )
            )
            session.commit()

        assert _get_project_index() == []


# ── TestCliEntrypoint ─────────────────────────────────────────────────────────


class TestCliEntrypoint:
    def test_no_command_shows_help(self, capsys):
        with patch("sys.argv", ["kontext"]):
            with pytest.raises(SystemExit) as exc_info:
                cli()
            assert exc_info.value.code == 0


class TestServeSetup:
    def test_serve_starts_without_first_time_setup_prompt(self):
        args = argparse.Namespace(
            dist_dir=None,
            lake_path=None,
            host="127.0.0.1",
            port=8000,
            open=False,
            reload=False,
        )

        with (
            patch("kontext.labs.cli._init_engine", return_value=MagicMock()),
            patch("kontext.labs.cli.ensure_supported_sqlite"),
            patch("kontext.labs.cli._print_startup_banner"),
            patch("uvicorn.Config"),
            patch("uvicorn.Server") as mock_server,
            patch("kontext.labs.server.create_app", return_value=MagicMock()),
        ):
            _cmd_serve(args)

        mock_server.return_value.run.assert_called_once()


class TestInitEngine:
    def test_init_engine_preserves_configured_project_db_url(self, monkeypatch, tmp_path):
        configured_db_url = f"sqlite:///{tmp_path}/custom-kontext.db"
        monkeypatch.setenv("PROJECT_DB_URL", configured_db_url)

        with (
            patch("kontext.data.database.Base.metadata.create_all"),
            patch("kontext.data.database.get_engine", return_value=MagicMock()),
            patch("importlib.import_module"),
            patch(
                "kontext.storage.engine.local.LocalStorageEngine",
                return_value=MagicMock(),
            ),
        ):
            _init_engine()

        assert os.environ["PROJECT_DB_URL"] == configured_db_url

    def test_init_engine_replaces_non_sqlite_project_db_url_in_local_mode(self, monkeypatch):
        configured_db_url = "postgresql://localhost:5432/kontext"
        monkeypatch.setenv("PROJECT_DB_URL", configured_db_url)

        with (
            patch("kontext.data.database.Base.metadata.create_all"),
            patch("kontext.data.database.get_engine", return_value=MagicMock()),
            patch("importlib.import_module"),
            patch(
                "kontext.storage.engine.local.LocalStorageEngine",
                return_value=MagicMock(),
            ),
        ):
            _init_engine()

        assert os.environ["PROJECT_DB_URL"].startswith("sqlite:///")
        assert os.environ["PROJECT_DB_URL"] != configured_db_url
