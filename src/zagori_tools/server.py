"""FastAPI server exposing a Notion-focused tool surface for ChatGPT."""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

load_dotenv()

app = FastAPI(
    title="Zagori Tools",
    version="0.2.2",
    description="Tool server that proxies requests to the Notion API for ChatGPT.",
)

# Allow the GPT callers to reach the service from any origin during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    """Response payload for the health check endpoint."""

    status: Literal["ok"]


class NotionProxyRequest(BaseModel):
    """Generic proxy request body for forwarding calls to the Notion API."""

    method: Literal["GET", "POST", "PATCH", "DELETE"]
    path: str = Field(
        ..., description="Endpoint path, e.g. '/v1/pages' or 'v1/databases/{database_id}/query'."
    )
    params: dict[str, Any] | None = Field(
        default=None, description="Optional query parameters appended to the request."
    )
    body: dict[str, Any] | None = Field(
        default=None,
        description="Optional JSON body forwarded to Notion (ignored for GET requests).",
    )

    @validator("path")
    def normalise_path(cls, value: str) -> str:
        """Ensure the path sent to the Notion API begins with a slash."""

        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Path must not be empty")
        if not trimmed.startswith("/"):
            trimmed = f"/{trimmed}"
        return trimmed


class NotionProxyResponse(BaseModel):
    """Standardised response surfaced back to ChatGPT."""

    status_code: int
    data: Any | None
    notion_request_id: str | None = Field(
        default=None, description="Value of Notion's X-Request-Id header when available."
    )


NOTION_API_BASE_URL = "https://api.notion.com"
DEFAULT_NOTION_VERSION = "2022-06-28"


def _get_notion_token() -> str:
    """Fetch the Notion integration token from the environment."""

    token = os.getenv("NOTION_API_TOKEN")
    if not token:
        raise HTTPException(
            status_code=500,
            detail=(
                "NOTION_API_TOKEN environment variable is not set; unable to call the Notion API."
            ),
        )
    return token


def _build_notion_client(token: str) -> httpx.Client:
    """Create an HTTP client configured for the Notion API."""

    notion_version = os.getenv("NOTION_API_VERSION", DEFAULT_NOTION_VERSION)
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": notion_version,
        "Content-Type": "application/json",
    }
    return httpx.Client(base_url=NOTION_API_BASE_URL, headers=headers, timeout=30.0)


@app.get("/healthz", response_model=HealthResponse, tags=["internal"])
def health_check() -> HealthResponse:
    """Simple readiness probe for deployment environments."""

    return HealthResponse(status="ok")


@app.post("/notion/request", response_model=NotionProxyResponse, tags=["notion"])
def proxy_notion_request(payload: NotionProxyRequest) -> NotionProxyResponse:
    """Forward a request to Notion and return the raw response for ChatGPT to consume."""

    token = _get_notion_token()
    with _build_notion_client(token) as client:
        response = client.request(
            payload.method,
            payload.path,
            params=payload.params,
            json=payload.body if payload.method != "GET" else None,
        )

    if response.status_code >= 400:
        try:
            detail: Any = response.json()
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        data: Any | None = response.json()
    except ValueError:
        data = response.text or None

    return NotionProxyResponse(
        status_code=response.status_code,
        data=data,
        notion_request_id=response.headers.get("x-request-id")
        or response.headers.get("x-notion-request-id"),
    )


@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def plugin_manifest(request: Request) -> JSONResponse:
    """Serve the manifest that ChatGPT Actions expect."""

    base_url = str(request.base_url).rstrip("/")
    manifest = {
        "schema_version": "v1",
        "name_for_human": "Zagori Tools",
        "name_for_model": "zagori_tools_notion",
        "description_for_human": "Proxy every Notion API endpoint through a single action.",
        "description_for_model": (
            "Use this tool to perform any Notion API call by specifying the HTTP method, path,"
            " query params, and body."
        ),
        "auth": {"type": "none"},
        "api": {"type": "openapi", "url": f"{base_url}/openapi.json"},
        "contact_email": "support@example.com",
        "legal_info_url": "https://example.com/legal",
    }
    return JSONResponse(content=manifest)


def main() -> None:
    """Launch the FastAPI app with uvicorn."""

    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "443"))

    certfile = os.getenv("SSL_CERTFILE")
    keyfile = os.getenv("SSL_KEYFILE")
    ssl_kwargs: dict[str, Any] = {}

    if certfile and keyfile:
        ssl_kwargs["ssl_certfile"] = certfile
        ssl_kwargs["ssl_keyfile"] = keyfile
        key_password = os.getenv("SSL_KEYFILE_PASSWORD")
        if key_password:
            ssl_kwargs["ssl_keyfile_password"] = key_password
    elif port == 443:
        raise SystemExit(
            "PORT is 443 but SSL_CERTFILE/SSL_KEYFILE are not configured; HTTPS requires both."
        )

    uvicorn.run(
        "zagori_tools.server:app",
        host=host,
        port=port,
        reload=False,
        **ssl_kwargs,
    )


if __name__ == "__main__":
    main()
