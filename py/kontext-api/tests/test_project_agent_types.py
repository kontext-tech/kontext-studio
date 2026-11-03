import uuid

import pytest
from fastapi.testclient import TestClient

from kontext.api.main import app


@pytest.fixture
def mock_jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test_secret_key_for_validation_tests")


@pytest.fixture
def client(mock_jwt_secret):
    return TestClient(app)


def test_get_agent_types_endpoint_removed(client, mock_jwt_secret):
    project_id = str(uuid.uuid4())
    response = client.get(f"/project/{project_id}/agent-types")
    assert response.status_code == 404
