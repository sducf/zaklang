"""Public request and response models for benchmark API endpoints."""

from enum import Enum

from pydantic import BaseModel, Field


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
    source: str = Field(min_length=1)


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
    task_id: str
    language: Language
    source: str | None = None


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
    exec_outcome: str | None


class RunResponse(BaseModel):
    """Aggregate result for a run, including its individual attempts."""

    id: int
    task_id: str
    language: Language
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
    task_id: str
    language: Language
    status: RunStatus
    attempts_used: int = Field(ge=0)