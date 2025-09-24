from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="Zagori Tools",
    version="0.1.0",
    description="Minimal example tool server that ChatGPT can call via predefined actions.",
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


class TimeResponse(BaseModel):
    """UTC timestamp response."""

    iso_timestamp: str
    timezone: str


class SumRequest(BaseModel):
    """Request payload for summing numeric values."""

    numbers: list[float] = Field(
        ..., description="List of numbers to sum", min_length=1
    )


class SumResponse(BaseModel):
    """Response payload bundling the calculated total."""

    total: float


@app.get("/healthz", response_model=HealthResponse, tags=["internal"])
def health_check() -> HealthResponse:
    """Simple readiness probe for deployment environments."""

    return HealthResponse(status="ok")


@app.get("/time", response_model=TimeResponse, tags=["utility"])
def get_utc_time(timezone_name: str = "UTC") -> TimeResponse:
    """Return the current UTC timestamp; extra timezones can be added later."""

    if timezone_name.upper() != "UTC":
        raise HTTPException(status_code=400, detail="Only UTC is supported in this MVP")

    now = datetime.now(timezone.utc)
    return TimeResponse(iso_timestamp=now.isoformat(), timezone="UTC")


@app.post("/math/sum", response_model=SumResponse, tags=["utility"])
def sum_numbers(payload: SumRequest) -> SumResponse:
    """Sum a list of floating-point numbers."""

    total = float(sum(payload.numbers))
    return SumResponse(total=total)


@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def plugin_manifest(request: Request) -> JSONResponse:
    """Serve the manifest that ChatGPT Actions expect."""

    base_url = str(request.base_url).rstrip("/")
    manifest = {
        "schema_version": "v1",
        "name_for_human": "Zagori Tools",
        "name_for_model": "zagori_tools",
        "description_for_human": "Minimal helper API offering health, time, and math utilities.",
        "description_for_model": "Use this tool to check service health, fetch the current UTC time, or sum numbers.",
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
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("zagori_tools.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
