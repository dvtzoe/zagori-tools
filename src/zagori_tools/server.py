"""FastAPI server exposing a Notion-focused tool surface for ChatGPT."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

load_dotenv()

OPENAPI_JSON_PATH = Path(__file__).with_name("openapi.json")


@lru_cache(maxsize=1)
def _get_openapi_document() -> dict[str, Any]:
    """Load the OpenAPI document stored alongside the server module."""

    try:
        raw = OPENAPI_JSON_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="openapi.json is missing; unable to serve the schema.",
        ) from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail="openapi.json is invalid JSON; unable to serve the schema.",
        ) from exc


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
    """
    Generic proxy request body for forwarding calls to the Notion API.
    
    This tool allows you to make any Notion API call by specifying the HTTP method, 
    endpoint path, query parameters, and request body. It supports all core Notion 
    operations including pages, databases, blocks, users, and comments.
    
    Common Notion API patterns:
    - Create a page: POST /v1/pages
    - Query a database: POST /v1/databases/{database_id}/query  
    - Retrieve a page: GET /v1/pages/{page_id}
    - Update page properties: PATCH /v1/pages/{page_id}
    - Append block children: PATCH /v1/blocks/{block_id}/children
    - Search content: POST /v1/search
    
    Authentication is handled automatically via the NOTION_API_TOKEN environment variable.
    """

    method: Literal["GET", "POST", "PATCH", "DELETE"] = Field(
        ...,
        description="HTTP method for the Notion API request. Use GET for retrieval, POST for creation and queries, PATCH for updates, DELETE for removal."
    )
    path: str = Field(
        ...,
        description="""
        Notion API endpoint path (without the base URL). Examples:
        - '/v1/pages' (create page)
        - '/v1/pages/{page_id}' (get/update page)
        - '/v1/databases/{database_id}' (get database)
        - '/v1/databases/{database_id}/query' (query database)
        - '/v1/blocks/{block_id}/children' (get/append block children)
        - '/v1/search' (search pages and databases)
        - '/v1/users' (list users)
        - '/v1/comments' (create comment)
        
        Replace {page_id}, {database_id}, etc. with actual UUIDs (with or without hyphens).
        """,
    )
    params: dict[str, Any] | None = Field(
        default=None, 
        description="""
        Optional query parameters. Common examples:
        - For pagination: {'start_cursor': 'cursor_value', 'page_size': 100}
        - For filtering results: {'filter_properties': ['title']}
        - For archived content: {'filter': {'property': 'object', 'value': 'page'}}
        """
    )
    body: dict[str, Any] | None = Field(
        default=None,
        description="""
        Optional JSON request body (ignored for GET requests). Structure varies by endpoint:
        
        For page creation (POST /v1/pages):
        {
            "parent": {"database_id": "database_uuid"},
            "properties": {
                "title": {"title": [{"text": {"content": "Page Title"}}]},
                "status": {"select": {"name": "In Progress"}}
            }
        }
        
        For database queries (POST /v1/databases/{database_id}/query):
        {
            "filter": {
                "property": "Status",
                "select": {"equals": "Done"}
            },
            "sorts": [{"property": "Created", "direction": "descending"}],
            "page_size": 50
        }
        
        For block appending (PATCH /v1/blocks/{block_id}/children):
        {
            "children": [
                {
                    "paragraph": {
                        "rich_text": [{"text": {"content": "New paragraph text"}}]
                    }
                }
            ]
        }
        
        For search (POST /v1/search):
        {
            "query": "search term",
            "filter": {"property": "object", "value": "page"},
            "page_size": 10
        }
        """
    )

    @field_validator("path")
    @classmethod
    def normalise_path(cls, value: str) -> str:
        """Ensure the path sent to the Notion API begins with a slash."""

        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Path must not be empty")
        if not trimmed.startswith("/"):
            trimmed = f"/{trimmed}"
        return trimmed


class NotionProxyResponse(BaseModel):
    """
    Standardised response from Notion API calls.
    
    Contains the HTTP status code, response data, and Notion's request ID for debugging.
    The data field contains the raw JSON response from Notion's API, which varies by endpoint.
    
    Common response structures:
    - Pages: Contains 'id', 'properties', 'parent', 'created_time', etc.
    - Databases: Contains 'id', 'title', 'properties' schema, 'parent', etc.
    - Query results: Contains 'results' array and 'next_cursor' for pagination
    - Errors: Contains 'object': 'error', 'status', 'code', 'message'
    """

    status_code: int = Field(
        ...,
        description="HTTP status code from Notion API. 200 for success, 400+ for errors."
    )
    data: Any | None = Field(
        ...,
        description="Raw JSON response from Notion API. Structure varies by endpoint. null for non-JSON responses."
    )
    notion_request_id: str | None = Field(
        default=None,
        description="Notion's request ID for debugging and support. Include this when reporting issues to Notion.",
    )


NOTION_API_BASE_URL = "https://api.notion.com"
DEFAULT_NOTION_VERSION = "2024-05-01"


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
    """
    Proxy requests to Notion API v2024-05-01. Supports all operations: pages, databases, blocks, search, users. 
    Handles authentication, versioning, and error responses automatically. Returns raw API response with metadata.
    """

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


@app.get("/.well-known/openapi.json", include_in_schema=False)
async def well_known_openapi() -> JSONResponse:
    """Serve the static OpenAPI document for plugin registration."""

    return JSONResponse(content=_get_openapi_document())


@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def plugin_manifest(request: Request) -> JSONResponse:
    """Serve the manifest that ChatGPT Actions expect."""

    base_url = str(request.base_url).rstrip("/")
    manifest = {
        "schema_version": "v1",
        "name_for_human": "Zagori Tools",
        "name_for_model": "zagori_tools_notion",
        "description_for_human": "Access and manage Notion workspaces through the complete Notion API. Create, read, update pages, databases, and blocks.",
        "description_for_model": (
            "Use this tool to interact with Notion workspaces via the latest Notion API (2024-05-01). "
            "Supports all Notion operations: create/edit pages and databases, query data with filters and sorts, "
            "manage blocks and rich text content, search across workspaces, and handle user permissions. "
            "Specify HTTP method, API path, query params, and JSON body as needed. "
            "Authentication is handled automatically. Returns raw Notion API responses with status codes."
        ),
        "auth": {"type": "none"},
        "api": {"type": "openapi", "url": f"{base_url}/.well-known/openapi.json"},
        "contact_email": "ohmtzoe@gmail.com",
        "legal_info_url": "https://github.com/dvtzoe/zagori-tools/blob/main/README.md",
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
