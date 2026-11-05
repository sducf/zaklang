"""Contract-only benchmark routes."""

from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from api.schemas.benchmark import (
    CompileRequest,
    CompileResponse,
    Language,
    PairCreateRequest,
    PairCreateResponse,
    RunCreateRequest,
    RunListItem,
    RunResponse,
    TASK_ID_PATTERN,
    TaskResponse,
)
from api.controllers.auth import get_current_user_controller
from api.controllers.benchmark import (
    compile_controller,
    create_queued_pair,
    create_queued_run,
    execute_run_in_background,
    get_run_for_user,
    get_pair_for_user,
    get_task_controller,
    list_tasks_controller,
    list_runs_for_user,
    run_to_response,
)
from database.models import User
from database.db import get_db

router = APIRouter(tags=["benchmark"])


def _not_implemented() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Benchmark endpoint behavior is not implemented yet",
    )


@router.get("/tasks", response_model=list[TaskResponse])
def list_tasks() -> list[TaskResponse]:
    return list_tasks_controller()


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str = Path(pattern=TASK_ID_PATTERN),
) -> TaskResponse:
    return get_task_controller(task_id)


@router.post("/compile", response_model=CompileResponse)
def compile_source(payload: CompileRequest) -> CompileResponse:
    return compile_controller(payload.source)


@router.post(
    "/runs/pair",
    response_model=PairCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_run_pair(
    payload: PairCreateRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user_controller),
    db: Session = Depends(get_db),
) -> PairCreateResponse:
    get_task_controller(payload.task_id)
    pair_id, runs = create_queued_pair(
        db,
        user,
        payload.task_id,
        temperature=payload.temperature,
        seed=payload.seed,
    )
    db.commit()
    for run in runs:
        db.refresh(run)
        background_tasks.add_task(
            execute_run_in_background,
            run.id,
            payload.task_id,
            Language(run.language),
            None,
            payload.temperature,
            payload.seed,
        )
    return PairCreateResponse(
        pair_id=pair_id,
        run_ids=[run.id for run in runs],
    )


@router.post(
    "/runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_run(
    payload: RunCreateRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user_controller),
    db: Session = Depends(get_db),
) -> RunResponse:
    get_task_controller(payload.task_id)
    run = create_queued_run(
        db,
        user,
        payload.task_id,
        payload.language,
        temperature=payload.temperature,
        seed=payload.seed,
    )
    db.commit()
    db.refresh(run)
    background_tasks.add_task(
        execute_run_in_background,
        run.id,
        payload.task_id,
        payload.language,
        payload.source,
        payload.temperature,
        payload.seed,
    )
    return run_to_response(run)


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(
    run_id: int,
    user: User = Depends(get_current_user_controller),
    db: Session = Depends(get_db),
) -> RunResponse:
    return get_run_for_user(db, user, run_id)


@router.get("/pairs/{pair_id}", response_model=list[RunResponse])
def get_pair(
    pair_id: UUID,
    user: User = Depends(get_current_user_controller),
    db: Session = Depends(get_db),
) -> list[RunResponse]:
    return get_pair_for_user(db, user, pair_id)


@router.get("/runs", response_model=list[RunListItem])
def list_runs(
    user: User = Depends(get_current_user_controller),
    db: Session = Depends(get_db),
) -> list[RunListItem]:
    return list_runs_for_user(db, user)
