from kontext.api.export_openapi import export_openapi_document


def test_openapi_export_uses_cloud_routing_shape(monkeypatch):
    monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")

    spec = export_openapi_document()

    assert spec["info"]["title"] == "Kontext API"
    assert spec["openapi"].startswith("3.1")
    assert "/health" in spec["paths"]
    assert "/auth/login" not in spec["paths"]
    assert "/account/info" not in spec["paths"]
