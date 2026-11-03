from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

from kontext.api.main import create_app
from kontext.data.database import get_engine, get_session_factory

TEST_LAUNCH_TOKEN = "test-launch-token"


def _launch_headers() -> dict[str, str]:
    return {"X-Kontext-Launch-Token": TEST_LAUNCH_TOKEN}


def _clear_db_caches() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def _get_local_access_token(client: TestClient) -> str:
    bootstrap_response = client.get("/host/auth/bootstrap", headers=_launch_headers())
    bootstrap_payload = bootstrap_response.json()

    if bootstrap_payload.get("accessToken"):
        return bootstrap_payload["accessToken"]["accessToken"]

    setup_response = client.post(
        "/setup",
        json={
            "firstName": "Local",
            "lastName": "Tester",
            "email": "local-tester@example.com",
        },
        headers=_launch_headers(),
    )
    assert setup_response.status_code == 200
    return setup_response.json()["accessToken"]


@contextmanager
def _local_client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
            clear=True,
        ),
        patch(
            "kontext.runtime.local.config.get_local_database_url",
            return_value=database_url,
        ),
        patch(
            "kontext.runtime.local.auth.get_local_jwt_secret",
            return_value="test-local-secret",
        ),
    ):
        _clear_db_caches()
        try:
            app = create_app()
            with TestClient(app) as client:
                access_token = _get_local_access_token(client)
                yield client, {"Authorization": f"Bearer {access_token}"}
        finally:
            _clear_db_caches()


def test_model_connection_providers_endpoint_lists_supported_kinds(tmp_path):
    with _local_client(tmp_path) as (client, headers):
        response = client.get("/model-connections/providers", headers=headers)

    assert response.status_code == 200
    provider_kinds = {item["connectionKind"] for item in response.json()}
    assert {
        "lm_studio",
        "ollama",
        "ollama_cloud",
        "openai",
        "anthropic",
        "openai_compatible",
        "openrouter",
        "deepseek",
        "mistral",
        "gemini",
        "google_vertex",
        "azure_openai",
        "bedrock",
    }.issubset(provider_kinds)


def test_create_model_connection_persists_provider_config_and_credentials(tmp_path):
    with _local_client(tmp_path) as (client, headers):
        create_response = client.post(
            "/model-connections",
            headers=headers,
            json={
                "sourceType": "user_managed",
                "adapterType": "openai_native",
                "connectionKind": "openai",
                "canonicalModelId": "openai/gpt-4o-mini",
                "displayName": "OpenAI GPT-4o Mini",
                "providerConfig": {
                    "endpointBaseUrl": "https://api.openai.com/v1",
                },
                "credentialRefs": {"apiKeyRef": "sk-test-key"},
                "secretConfigured": True,
                "enabled": True,
                "isDefault": True,
                "validationState": "unknown",
            },
        )
        catalog_response = client.get("/models/catalog", headers=headers)

    assert create_response.status_code == 201
    created = create_response.json()
    # The runtime provider model name is derived server-side from the curated
    # alias, not sent by the client.
    assert created["providerConfig"].get("providerModelName") is None
    assert created["providerConfig"]["endpointBaseUrl"] == "https://api.openai.com/v1"
    assert created["credentialRefs"]["apiKeyRef"].startswith("local-secret://model-connections/")
    assert created["secretRef"] == created["credentialRefs"]["apiKeyRef"]
    assert created["secretConfigured"] is True
    assert created["validationState"] == "valid"

    assert catalog_response.status_code == 200
    catalog_entries = catalog_response.json()
    assert len(catalog_entries) == 1
    assert catalog_entries[0]["providerModelName"] == "gpt-4o-mini"


def test_create_model_connection_recomputes_validation_state(tmp_path):
    with _local_client(tmp_path) as (client, headers):
        create_response = client.post(
            "/model-connections",
            headers=headers,
            json={
                "sourceType": "user_managed",
                "adapterType": "openai_compatible",
                "connectionKind": "openai",
                "canonicalModelId": "openai/gpt-4o-mini",
                "displayName": "OpenAI GPT-4o Mini",
                "enabled": True,
                "isDefault": False,
                "validationState": "valid",
            },
        )
        catalog_response = client.get("/models/catalog", headers=headers)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["adapterType"] == "openai_native"
    assert created["validationState"] == "pending"
    assert created["credentialRefs"] is None
    assert catalog_response.status_code == 200
    assert catalog_response.json() == []


def test_create_model_connection_accepts_custom_models(tmp_path):
    """The curated catalog is advisory; free-text model ids are accepted."""
    with _local_client(tmp_path) as (client, headers):
        response = client.post(
            "/model-connections",
            headers=headers,
            json={
                "sourceType": "user_managed",
                "adapterType": "openai_native",
                "connectionKind": "openai",
                "canonicalModelId": "totally/custom-model",
                "displayName": "Custom Model",
                "credentialRefs": {"apiKeyRef": "sk-test-key"},
                "enabled": True,
                "isDefault": False,
                "validationState": "unknown",
            },
        )

    assert response.status_code == 201
    created = response.json()
    assert created["canonicalModelId"] == "totally/custom-model"
    assert created["validationState"] == "valid"


def test_create_model_connection_accepts_uncurated_alias_model_ids(tmp_path):
    """A non-catalog model id is accepted and used verbatim."""
    with _local_client(tmp_path) as (client, headers):
        response = client.post(
            "/model-connections",
            headers=headers,
            json={
                "sourceType": "user_managed",
                "adapterType": "gemini_native",
                "connectionKind": "gemini",
                "canonicalModelId": "google/gemini-2.5-flash",
                "displayName": "Legacy Gemini",
                "credentialRefs": {"apiKeyRef": "legacy-gemini-key"},
                "enabled": True,
                "isDefault": False,
                "validationState": "unknown",
            },
        )

    assert response.status_code == 201
    created = response.json()
    assert created["canonicalModelId"] == "google/gemini-2.5-flash"
    assert created["validationState"] == "valid"


def test_create_model_connection_accepts_deepseek_provider(tmp_path):
    with _local_client(tmp_path) as (client, headers):
        response = client.post(
            "/model-connections",
            headers=headers,
            json={
                "sourceType": "user_managed",
                "adapterType": "openai_compatible",
                "connectionKind": "deepseek",
                "canonicalModelId": "deepseek/deepseek-chat",
                "displayName": "DeepSeek Chat",
                "credentialRefs": {"apiKeyRef": "sk-test-key"},
                "enabled": True,
                "isDefault": False,
                "validationState": "unknown",
            },
        )

    assert response.status_code == 201
    created = response.json()
    assert created["connectionKind"] == "deepseek"
    assert created["adapterType"] == "openai_compatible"
    assert created["validationState"] == "valid"
