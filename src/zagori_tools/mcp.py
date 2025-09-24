"""Model Context Protocol (MCP) server exposing Notion proxy tools."""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError

from .server import DEFAULT_NOTION_VERSION, NOTION_API_BASE_URL

load_dotenv()

mcp_server = FastMCP(name="Zagori Tools MCP")


async def _send_notion_request(
    method: Literal["GET", "POST", "PATCH", "DELETE"],
    path: str,
    params: dict[str, Any] | None,
    body: dict[str, Any] | None,
) -> tuple[int, Any, str | None]:
    """Issue a request to the Notion API using the shared configuration."""

    token = os.getenv("NOTION_API_TOKEN")
    if not token:
        raise ToolError(
            "NOTION_API_TOKEN environment variable is not set; unable to call the Notion API."
        )

    trimmed = path.strip()
    if not trimmed:
        raise ToolError("Path must not be empty")
    if not trimmed.startswith("/"):
        trimmed = f"/{trimmed}"

    notion_version = os.getenv("NOTION_API_VERSION", DEFAULT_NOTION_VERSION)
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": notion_version,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(
        base_url=NOTION_API_BASE_URL,
        headers=headers,
        timeout=30.0,
    ) as client:
        response = await client.request(
            method,
            trimmed,
            params=params,
            json=body if method != "GET" else None,
        )

    notion_request_id = response.headers.get("x-request-id") or response.headers.get(
        "x-notion-request-id"
    )

    try:
        data: Any | None = response.json()
    except ValueError:
        data = response.text or None

    return response.status_code, data, notion_request_id


@mcp_server.tool(name="notion_request", description="Proxy an arbitrary Notion API call.")
async def notion_request(
    method: Literal["GET", "POST", "PATCH", "DELETE"],
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    ctx: Context | None = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Call the Notion API and return the raw response metadata."""

    try:
        status_code, data, notion_request_id = await _send_notion_request(
            method,
            path,
            params,
            body,
        )
    except ToolError:
        raise
    except Exception as exc:  # pragma: no cover - defensive logging path
        if ctx is not None:
            ctx.error(f"Unexpected error calling Notion: {exc}")
        raise ToolError(f"Unexpected error calling Notion: {exc}") from exc

    result = {
        "status_code": status_code,
        "data": data,
        "notion_request_id": notion_request_id,
    }

    if ctx is not None:
        ctx.info(
            f"Notion {method} {path} -> {status_code}"
            + (f" (request-id {notion_request_id})" if notion_request_id else "")
        )

    return result


def main() -> None:
    """Run the MCP server using an SSE transport compatible with ChatGPT connectors."""

    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    import uvicorn

    settings = mcp_server.settings
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await mcp_server._mcp_server.run(  # type: ignore[attr-defined]
                streams[0],
                streams[1],
                mcp_server._mcp_server.create_initialization_options(),  # type: ignore[attr-defined]
            )

    starlette_app = Starlette(
        debug=settings.debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/sse/", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    certfile = os.getenv("SSL_CERTFILE")
    keyfile = os.getenv("SSL_KEYFILE")
    ssl_kwargs: dict[str, Any] = {}

    if certfile and keyfile:
        ssl_kwargs["ssl_certfile"] = certfile
        ssl_kwargs["ssl_keyfile"] = keyfile
        key_password = os.getenv("SSL_KEYFILE_PASSWORD")
        if key_password:
            ssl_kwargs["ssl_keyfile_password"] = key_password
    elif settings.port == 443:
        raise SystemExit(
            "PORT is 443 but SSL_CERTFILE/SSL_KEYFILE are not configured; HTTPS requires both."
        )

    uvicorn.run(
        starlette_app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        **ssl_kwargs,
    )


if __name__ == "__main__":
    main()
