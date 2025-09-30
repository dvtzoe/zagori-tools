"""Tests for the Notion proxy FastAPI application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from zagori_tools.server import app

client = TestClient(app)


@dataclass
class StubResponse:
    status_code: int
    json_payload: Any | None = None
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        if self.json_payload is None:
            raise ValueError("No JSON payload provided")
        return self.json_payload


class StubNotionClient:
    """Context manager that mimics the subset of httpx.Client used by the app."""

    def __init__(self, response: StubResponse):
        self._response = response
        self.captured_method: str | None = None
        self.captured_path: str | None = None
        self.captured_params: dict[str, Any] | None = None
        self.captured_body: dict[str, Any] | None = None

    def __enter__(self) -> "StubNotionClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - nothing to clean up
        return None

    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> StubResponse:
        self.captured_method = method
        self.captured_path = path
        self.captured_params = params
        self.captured_body = json
        return self._response


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOTION_API_TOKEN", raising=False)
    monkeypatch.delenv("NOTION_API_VERSION", raising=False)


def test_health_endpoint_reports_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_proxy_request_passes_through_to_notion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTION_API_TOKEN", "secret")

    response_payload = {"results": []}
    stub_response = StubResponse(
        status_code=200,
        json_payload=response_payload,
        headers={"x-notion-request-id": "abc-123"},
    )
    stub_client = StubNotionClient(stub_response)
    monkeypatch.setattr("zagori_tools.server._build_notion_client", Mock(return_value=stub_client))

    payload = {
        "method": "POST",
        "path": "v1/databases/database-id/query",
        "params": {"page_size": 10},
        "body": {"filter": {"property": "Done", "checkbox": {"equals": False}}},
    }

    response = client.post("/notion/request", json=payload)
    assert response.status_code == 200
    assert response.json() == {
        "status_code": 200,
        "data": response_payload,
        "notion_request_id": "abc-123",
    }

    assert stub_client.captured_method == "POST"
    assert stub_client.captured_path == "/v1/databases/database-id/query"
    assert stub_client.captured_params == {"page_size": 10}
    assert stub_client.captured_body == payload["body"]


def test_missing_token_returns_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("zagori_tools.server._build_notion_client", Mock())

    response = client.post(
        "/notion/request",
        json={"method": "GET", "path": "/v1/databases"},
    )
    assert response.status_code == 500
    assert "NOTION_API_TOKEN" in response.json()["detail"]


def test_proxy_returns_error_payload_from_notion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTION_API_TOKEN", "secret")

    error_payload = {"object": "error", "status": 404, "message": "Not found"}
    stub_response = StubResponse(status_code=404, json_payload=error_payload)
    stub_client = StubNotionClient(stub_response)
    monkeypatch.setattr("zagori_tools.server._build_notion_client", Mock(return_value=stub_client))

    response = client.post(
        "/notion/request",
        json={"method": "GET", "path": "/v1/pages/non-existent"},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": error_payload}


def test_proxy_handles_non_json_bodies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTION_API_TOKEN", "secret")

    stub_response = StubResponse(status_code=200, json_payload=None, text="")
    stub_client = StubNotionClient(stub_response)
    monkeypatch.setattr("zagori_tools.server._build_notion_client", Mock(return_value=stub_client))

    response = client.post(
        "/notion/request",
        json={"method": "DELETE", "path": "/v1/blocks/block-id"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "status_code": 200,
        "data": None,
        "notion_request_id": None,
    }
