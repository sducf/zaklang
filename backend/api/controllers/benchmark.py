"""Application behavior for public benchmark metadata."""

import json
from pathlib import Path
import re
import sys
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.schemas.benchmark import (
    TASK_ID_PATTERN,
    AttemptResponse,
    CompileResponse,
    CompilerError,
    ExecutionOutcome,
    Language,
    RunListItem,
    RunResponse,
    RunStatus,
    TaskResponse,
)
from database.models import Attempt, BenchmarkRun, Evaluation, User


TASK_ID = re.compile(TASK_ID_PATTERN)
TASKS_ROOT = Path(__file__).resolve().parents[3] / "zakbench" / "tasks"
REPOSITORY_ROOT = TASKS_ROOT.parent.parent
MODEL_NAME = "Llama 3.1 8B Instruct"


def _read_task(task_id: str, task_file: Path) -> TaskResponse:
    """Read one public task definition without loading hidden tests."""
    try:
        definition: dict[str, Any] = json.loads(
            task_file.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not read task definition for {task_id}",
        ) from exc

    if not isinstance(definition, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid task definition for {task_id}",
        )

    if definition.get("id") != task_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task definition ID does not match directory for {task_id}",
        )

    try:
        return TaskResponse(
            id=definition["id"],
            title=definition["title"],
            category=definition["category"],
            prompt=definition["prompt"],
            function_name=definition["functionName"],
            inputs=definition["inputs"],
            output_type=definition["outputType"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid task definition for {task_id}",
        ) from exc


def list_tasks_controller() -> list[TaskResponse]:
    """Return all public task definitions in deterministic order."""
    try:
        task_directories = sorted(
            path for path in TASKS_ROOT.iterdir() if path.is_dir()
        )
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not list benchmark tasks",
        ) from exc

    return [
        _read_task(path.name, path / "task.json")
        for path in task_directories
        if TASK_ID.fullmatch(path.name) and (path / "task.json").is_file()
    ]


def get_task_controller(task_id: str) -> TaskResponse:
    """Return one public task definition by its validated identifier."""
    if not TASK_ID.fullmatch(task_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    task_file = TASKS_ROOT / task_id / "task.json"
    if not task_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return _read_task(task_id, task_file)


def compile_controller(source: str) -> CompileResponse:
    """Compile and transpile Zak source without executing generated Python."""
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))

    from compiler.src import TranspileError, compile as compile_zak, transpile

    result = compile_zak(source)
    if not result.ok:
        return CompileResponse(
            ok=False,
            errors=[_compiler_error(error) for error in result.errors],
            python=None,
        )

    if result.ast is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Compiler returned a successful result without an AST",
        )

    try:
        python_source = transpile(result.ast)
    except TranspileError as exc:
        return CompileResponse(
            ok=False,
            errors=[_compiler_error(error) for error in exc.errors],
            python=None,
        )

    return CompileResponse(ok=True, errors=[], python=python_source)


def _compiler_error(error: Any) -> CompilerError:
    """Convert a compiler diagnostic to the public API shape."""
    return CompilerError(
        line=error.line,
        col=error.col,
        code=error.code,
        message=error.message,
    )


def create_queued_run(
    db: Session,
    user: User,
    task_id: str,
    language: Language,
    temperature: float | None = None,
) -> BenchmarkRun:
    """Add a queued run and flush it so its ID is available to the caller."""
    run = BenchmarkRun(
        user_id=user.id,
        task_id=task_id,
        language=language.value,
        model_name=MODEL_NAME,
        temperature=temperature,
        status=RunStatus.QUEUED.value,
    )
    db.add(run)
    db.flush()
    return run


def run_to_response(run: BenchmarkRun) -> RunResponse:
    """Convert a persisted run and its related rows to the public response."""
    attempts = [
        _attempt_to_response(attempt)
        for attempt in sorted(run.attempts, key=lambda item: item.attempt_number)
    ]
    return RunResponse(
        id=run.id,
        task_id=run.task_id,
        language=Language(run.language),
        model_name=run.model_name,
        temperature=run.temperature,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=RunStatus(run.status),
        attempts_used=len(attempts),
        prompt_tokens_total=sum(
            attempt.prompt_tokens or 0 for attempt in attempts
        ),
        completion_tokens_total=sum(
            attempt.completion_tokens or 0 for attempt in attempts
        ),
        total_tokens=sum(attempt.total_tokens or 0 for attempt in attempts),
        latency_ms_total=sum(attempt.latency_ms or 0 for attempt in attempts),
        attempts=attempts,
    )


def run_to_list_item(run: BenchmarkRun) -> RunListItem:
    """Convert a persisted run to the user-scoped list response."""
    return RunListItem(
        id=run.id,
        task_id=run.task_id,
        language=Language(run.language),
        status=RunStatus(run.status),
        attempts_used=len(run.attempts),
    )


def _attempt_to_response(attempt: Attempt) -> AttemptResponse:
    evaluation = attempt.evaluation
    compile_errors = _compile_errors_from_storage(
        evaluation.compiler_output if evaluation else None
    )
    return AttemptResponse(
        index=attempt.attempt_number,
        completion_text=attempt.generated_code,
        prompt_tokens=attempt.prompt_tokens,
        completion_tokens=attempt.completion_tokens,
        total_tokens=attempt.total_tokens,
        latency_ms=attempt.latency_ms,
        compile_ok=evaluation.compile_success if evaluation else None,
        compile_errors=compile_errors,
        transpiled_python=evaluation.transpiled_code if evaluation else None,
        tests_passed=evaluation.tests_passed if evaluation else None,
        tests_total=evaluation.tests_total if evaluation else None,
        exec_outcome=(
            ExecutionOutcome(evaluation.exec_outcome)
            if evaluation and evaluation.exec_outcome
            else None
        ),
    )


def _compile_errors_from_storage(value: str | None) -> list[CompilerError]:
    if not value:
        return []
    try:
        raw_errors = json.loads(value)
        return [CompilerError.model_validate(error) for error in raw_errors]
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored compiler errors are invalid",
        ) from exc
