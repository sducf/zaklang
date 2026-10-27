"""Application behavior for public benchmark metadata."""

import json
from pathlib import Path
import re
import sys
from typing import Any

from fastapi import HTTPException, status

from api.schemas.benchmark import (
    TASK_ID_PATTERN,
    CompileResponse,
    CompilerError,
    TaskResponse,
)


TASK_ID = re.compile(TASK_ID_PATTERN)
TASKS_ROOT = Path(__file__).resolve().parents[3] / "zakbench" / "tasks"
REPOSITORY_ROOT = TASKS_ROOT.parent.parent


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
