"""Contract-only benchmark routes."""

from fastapi import APIRouter, HTTPException, status

from api.schemas.benchmark import (
    CompileRequest,
    CompileResponse,
    RunCreateRequest,
    RunListItem,
    RunResponse,
    TaskResponse,
)

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
def create_run(payload: RunCreateRequest) -> RunResponse:
    _not_implemented()


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: int) -> RunResponse:
    _not_implemented()


@router.get("/runs", response_model=list[RunListItem])
def list_runs() -> list[RunListItem]:
    _not_implemented()