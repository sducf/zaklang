from datetime import datetime

from pydantic import BaseModel, ConfigDict

# Benchmark Run Schemas

# Fields shared by benchmark run request and responses
# These describe the configuration used for one ZakBench experiment -H
class BenchmarkRunBase(BaseModel):
    # Matches the task id from ZakBench, such as "array_sum"
    # or "palindrome". -H
    task_id: str

    # Language condition used for the experiment.
    # Expected values are currently "python" or "zak". -H
    language: str

    # Name of the model used to generate the solution. -H
    model_name: str

    # Optional inference settings.
    # If these are not provided, the inference server can use its defaults. -H
    temperature: float | None = None
    max_tokens: int | None = None


# Data required when creating a new benchmark run.
# Database-generated fields such as id and timestamps are not supplied here. -H
class BenchmarkRunCreate(BenchmarkRunBase):
    pass


# Data returned when reading a benchmark run from the database. -H
class BenchmarkRunRead(BenchmarkRunBase):
    # Allows Pydantic to create this schema directly from
    # a SQLAlchemy BenchmarkRun object. -H
    model_config = ConfigDict(from_attributes=True)

    id: int

    # Status is controlled by the backend rather than the client.
    # Examples include pending, running, completed, or failed. -H
    status: str

    started_at: datetime
    completed_at: datetime | None = None



# Attempt Schemas


# Fields describing one model generation attempt.
# Attempt 1 is the original response, while later attempts can represent
# repair requests after a failed generation. -H
class AttemptBase(BaseModel):
    # Identifies the benchmark run this attempt belongs to. -H
    run_id: int

    # Order of the generation attempt within the benchmark run. -H
    attempt_number: int

    # Exact prompt that was sent to the language model. -H
    prompt_text: str

    # Code returned by the language model. -H
    generated_code: str

    # Token counts returned by llama.cpp.
    # These values are important for comparing Zak and Python. -H
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    # Reason the model stopped generating, if provided by the
    # inference server. -H
    finish_reason: str | None = None

    # Time required for the model request in milliseconds. -H
    latency_ms: float | None = None


# Data used when storing a new model generation attempt. -H
class AttemptCreate(AttemptBase):
    pass


# Data returned when reading an attempt from PostgreSQL. -H
class AttemptRead(AttemptBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime



# Evaluation Schemas


# Fields describing the evaluation of one generated solution.
# Evaluation happens after the model has returned its code. -H
class EvaluationBase(BaseModel):
    # Identifies the generation attempt being evaluated. -H
    attempt_id: int

    # Indicates whether Zak compilation/transpilation succeeded.
    # Python runs may leave this null when compilation is not applicable. -H
    compile_success: bool | None = None

    # Compiler output or compiler error information.
    # This can later be included in a repair prompt. -H
    compiler_output: str | None = None

    # Python produced after successfully transpiling Zak.
    # This remains null for normal Python benchmark runs. -H
    transpiled_code: str | None = None

    # Hidden test results for this generated solution. -H
    tests_passed: int | None = None
    tests_total: int | None = None

    # True when the generated program satisfies the required
    # correctness checks. -H
    correct: bool | None = None

    # Time required to execute and test the generated code,
    # measured in milliseconds. -H
    execution_ms: float | None = None


# Data used when saving a new evaluation result. -H
class EvaluationCreate(EvaluationBase):
    pass


# Data returned when reading an evaluation from PostgreSQL. -H
class EvaluationRead(EvaluationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime