"""Integration tests for the FastAPI tool server."""

from fastapi.testclient import TestClient

from zagori_tools.server import app

client = TestClient(app)


def test_health_endpoint_reports_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_time_endpoint_returns_utc_timestamp() -> None:
    response = client.get("/time")
    assert response.status_code == 200

    payload = response.json()
    assert payload["timezone"] == "UTC"
    assert payload["iso_timestamp"].endswith("+00:00")


def test_time_endpoint_rejects_non_utc_timezone() -> None:
    response = client.get("/time", params={"timezone_name": "PST"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Only UTC is supported in this MVP"


def test_sum_endpoint_totals_numbers() -> None:
    response = client.post("/math/sum", json={"numbers": [1, 2.5, 0.5]})
    assert response.status_code == 200
    assert response.json() == {"total": 4.0}


def test_manifest_uses_generated_openapi_url() -> None:
    # FastAPI's TestClient uses http://testserver as the base URL in tests.
    response = client.get("/.well-known/ai-plugin.json")
    assert response.status_code == 200

    manifest = response.json()
    assert manifest["schema_version"] == "v1"
    assert manifest["name_for_model"] == "zagori_tools"
    assert manifest["api"] == {"type": "openapi", "url": "http://testserver/openapi.json"}
