"""Operational and integration-test routes."""

from fastapi import APIRouter

from api.controllers.testing import gpu_health_controller

router = APIRouter(tags=["testing"])

@router.get("/")
def read_root() -> dict[str, str]:
    """Basic backend health route."""
    return {"message": "ZakLang"}


@router.get("/gpu-health")
async def gpu_health() -> dict[str, object]:
    """Check connectivity to the remote llama.cpp service."""
    return await gpu_health_controller()