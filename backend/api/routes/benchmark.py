"""Contract-only benchmark routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas.benchmark import (
    CompileRequest,
    CompileResponse,
    RunCreateRequest,
    RunListItem,
    RunResponse,
    TaskResponse,
)
from api.controllers.auth import get_current_user_controller
from database.models import User

router = APIRouter(tags=["benchmark"])


def _not_implemented() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Benchmark endpoint behavior is not implemented yet",
    )


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks() -> list[TaskResponse]:
    _not_implemented()


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str) -> TaskResponse:
    _not_implemented()


@router.post("/compile", response_model=CompileResponse)
def compile_source(payload: CompileRequest) -> CompileResponse:
    _not_implemented()


@router.post(
    "/runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_run(
    payload: RunCreateRequest,
    user: User = Depends(get_current_user_controller),
) -> RunResponse:
    _not_implemented()


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(
    run_id: int,
    user: User = Depends(get_current_user_controller),
) -> RunResponse:
    _not_implemented()


@router.get("/runs", response_model=list[RunListItem])
def list_runs(
    user: User = Depends(get_current_user_controller),
) -> list[RunListItem]:
    _not_implemented()