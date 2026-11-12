"""Public request and response models for benchmark API endpoints."""

from datetime import datetime
from typing import Any
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

TASK_ID_PATTERN = r"^[a-z0-9_]+$"
MIN_SEED = 0
MAX_SEED = 2**31 - 1
MIN_TEMPERATURE = 0.0
MAX_TEMPERATURE = 2.0


class Language(str, Enum):
    ZAK = "zak"
    PYTHON = "python"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"


class ExecutionOutcome(str, Enum):
    """Outcome of executing one generated attempt."""

    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    OOM = "oom"
    CRASH = "crash"
    NOT_RUN = "not_run"


class TaskInput(BaseModel):
    name: str
    type: str


class TaskResponse(BaseModel):
    id: str
    title: str
    category: str
    prompt: str
    function_name: str
    inputs: list[TaskInput]
    output_type: str


class CompileRequest(BaseModel):
    source: str = Field(min_length=1, max_length=20_000)


class CompilerError(BaseModel):
    line: int = Field(ge=1)
    col: int = Field(ge=1)
    code: str
    message: str


class CompileResponse(BaseModel):
    ok: bool
    errors: list[CompilerError]
    python: str | None


class RunCreateRequest(BaseModel):
    task_id: str = Field(pattern=TASK_ID_PATTERN)
    language: Language
    temperature: float | None = Field(
        default=None, ge=MIN_TEMPERATURE, le=MAX_TEMPERATURE
    )
    seed: int | None = Field(default=None, ge=MIN_SEED, le=MAX_SEED)
    source: str | None = Field(default=None, max_length=20_000)


class PairCreateRequest(BaseModel):
    task_id: str = Field(pattern=TASK_ID_PATTERN)
    temperature: float | None = Field(
        default=None, ge=MIN_TEMPERATURE, le=MAX_TEMPERATURE
    )
    seed: int | None = Field(default=None, ge=MIN_SEED, le=MAX_SEED)


class PairCreateResponse(BaseModel):
    pair_id: UUID
    run_ids: list[int] = Field(min_length=2, max_length=2)


class AttemptResponse(BaseModel):
    """Public result and resource-usage details for one generation attempt."""

    index: int = Field(ge=1)
    completion_text: str
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_ms: float | None = Field(default=None, ge=0)
    compile_ok: bool | None
    compile_errors: list[CompilerError]
    transpiled_python: str | None
    tests_passed: int | None = Field(default=None, ge=0)
    tests_total: int | None = Field(default=None, ge=0)
    exec_outcome: ExecutionOutcome | None


class RunResponse(BaseModel):
    """Aggregate result for a run, including its individual attempts."""

    id: int
    pair_id: UUID | None
    task_id: str
    language: Language
    model_name: str
    temperature: float | None
    seed: int
    spec_version: str | None
    prompt_version: str
    max_attempts: int
    started_at: datetime
    completed_at: datetime | None
    status: RunStatus
    attempts_used: int = Field(ge=0)
    # These totals are derived across attempts; per-attempt values stay nested.
    prompt_tokens_total: int = Field(ge=0)
    completion_tokens_total: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    latency_ms_total: float = Field(ge=0)
    attempts: list[AttemptResponse]


class RunListItem(BaseModel):
    id: int
    pair_id: UUID | None
    task_id: str
    language: Language
    seed: int
    spec_version: str | None
    prompt_version: str
    max_attempts: int
    status: RunStatus
    attempts_used: int = Field(ge=0)


class SuiteResponse(BaseModel):
    id: int
    cli_suite_run_id: str
    suite: str
    model_name: str
    seed: int
    prompt_version: str
    spec_version: str | None
    max_attempts: int
    status: str
    created_at: datetime
    finished_at: datetime | None


class SuiteDetailResponse(SuiteResponse):
    # Output of zakbench/evaluation/summary.py summarize(). None until the
    # suite has completed, because a partial suite has incomplete pairs.
    summary: dict[str, Any] | None
    # task_id -> pair_id for every run stored with the suite, so each task can open its pair.
    pairs: dict[str, UUID] = Field(default_factory=dict)
