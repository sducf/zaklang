from datetime import datetime

from pydantic import BaseModel, ConfigDict


# Fields shared by benchmark run requests and responses. -H
class BenchmarkRunBase(BaseModel):
    # Matches a ZakBench task id such as "array_sum". -H
    task_id: str

    # Expected values are currently "python" or "zak". -H
    language: str

    # Name of the model used for generation. -H
    model_name: str

    # Optional inference settings. -H
    temperature: float | None = None
    max_tokens: int | None = None


# Data required when creating a benchmark run. -H
class BenchmarkRunCreate(BenchmarkRunBase):
    pass


# Data returned when reading a benchmark run. -H
class BenchmarkRunRead(BenchmarkRunBase):
    # Allows Pydantic to read values directly from SQLAlchemy models. -H
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    started_at: datetime
    completed_at: datetime | None = None


# Fields describing one model generation attempt. -H
class AttemptBase(BaseModel):
    run_id: int

    # 1 = initial generation, 2+ = repair attempts. -H
    attempt_number: int

    # Exact prompt sent to the model. -H
    prompt_text: str

    # Code returned by the model. -H
    generated_code: str

    # Token counts returned by llama.cpp. -H
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    finish_reason: str | None = None

    # Model request time in milliseconds. -H
    latency_ms: float | None = None


# Data required when saving a generation attempt. -H
class AttemptCreate(AttemptBase):
    pass


# Data returned when reading an attempt. -H
class AttemptRead(AttemptBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


# Fields describing the evaluation of one generated solution. -H
class EvaluationBase(BaseModel):
    attempt_id: int

    # Whether Zak compilation/transpilation succeeded.
    # Python attempts may leave this null. -H
    compile_success: bool | None = None

    # Compiler messages or errors that may later be used
    # to construct repair prompts. -H
    compiler_output: str | None = None

    # Python produced by the Zak transpiler.
    # Null for normal Python benchmark runs. -H
    transpiled_code: str | None = None

    # Hidden test results. -H
    tests_passed: int | None = None
    tests_total: int | None = None

    # True when the generated program satisfies the evaluation. -H
    correct: bool | None = None

    # Execution and testing duration in milliseconds. -H
    execution_ms: float | None = None


# Data required when storing an evaluation. -H
class EvaluationCreate(EvaluationBase):
    pass


# Data returned when reading an evaluation. -H
class EvaluationRead(EvaluationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime