"""Controllers for operational and integration-test endpoints."""

import os

import httpx
from fastapi import HTTPException

GPU_API_URL = os.getenv("GPU_API_URL", "").rstrip("/")


async def gpu_health_controller() -> dict[str, object]:
    """Check connectivity to the remote llama.cpp service."""
    if not GPU_API_URL:
        raise HTTPException(
            status_code=500,
            detail="GPU_API_URL is not configured",
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{GPU_API_URL}/health")
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach GPU server: {exc}",
        ) from exc

    try:
        llama_server = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="GPU server returned invalid JSON",
        ) from exc

    return {
        "gpu": "connected",
        "llama_server": llama_server,
    }