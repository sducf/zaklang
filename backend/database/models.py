from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# Base class used by SQLAlchemy for all database models
# Every table class below inherits from this class -H
class Base(DeclarativeBase):
    pass

# Stores one complete benchmark experiment
# A benchmark run represents one task being tested in one language
# with a specific model and inference configuration -H
class BenchmarkRun(Base):
    __tablename__ = "benchmark_run"

    # Unique database identifier for the benchmark run -H
    id: Mapped[int] = mapped_column(primary_key=True)

    # Matches the task id defined by Zakbench, such as "array_sum"
    # or "palindrome" the task definition itself remains in Zakbench -H
    task_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Indicates which language condition is being tested
    # Expected values are currently "python" or "zak" -H
    language: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Record the model used for this benchmark run so results can
    # later be compared across different models if needed -H
    model_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Sampling temperature used for this run.
    # This can be null when the inference server uses its default value. -H
    temperature: Mapped[float | None] = mapped_column(
    Float,
    nullable=True,
    )

    max_tokens:Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Tracks the overall state of the benchmark run
    # Examples could include pending, running, completed, or failed -H
    status: Mapped[str]=mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )

    # Timestamp for when the benchmark run began -H
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Filled in when the benchmark run finishes -H
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # One benchmark run can contain multiple attemps
    # This is important because a failed Zak generation may require
    # additional repair attempts that must also count toward token cost -H
    attempts: Mapped[list["Attempt"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan"
    )

# Stores each individual model generation made during a benchmark run
# Attempt 1 is the original generation later attempts can represent repairs -H
class Attempt(Base):
    __tablename__ = "attempts"

    # Unique identifier for this generation attempt -H
    id: Mapped[int] = mapped_column(primary_key=True)

    # Connects this attempt to the benchmark run that created it -H
    run_id: Mapped[int] = mapped_column(
        ForeignKey("benchmark_run.id"),
        nullable=False,
    )

    # Indicates the order of attempts within the run:
    # 1 = original generation, 2+ = repair attempts -H
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Stores the full prompt sent to the model
    # Keeping the exact prompt helps make experiments reproducible -H
    prompt_text: Mapped[str]= mapped_column(
        Text,
        nullable=False,
    )

    # Stores the code returned by the language model -H
    generated_code: Mapped[str]= mapped_column(
        Text,
        nullable=False,
    )

    # Token counts returned by the inference server
    # These measurements are central to the Zak vs. Python comparison -H
    prompt_tokens: Mapped[int | None]= mapped_column(
        Integer,
        nullable=True,
    )

    completion_tokens: Mapped[int | None]= mapped_column(
        Integer,
        nullable=True,
    )

    total_tokens: Mapped[int | None]= mapped_column(
        Integer,
        nullable=True,
    )

    # Record why the model stopped generating if the inference
    # server provides that information -H
    finish_reason: Mapped[str | None]= mapped_column(
        String(100),
        nullable=True,
    )

    # Stores how long the model request took in milliseconds -H
    latency_ms: Mapped[float | None]= mapped_column(
        Float,
        nullable=True,
    )

    # Timestamp for when this attempt was recorded -H
    created_at: Mapped[datetime]= mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

     # Relationship back to the benchmark run. -H
    run: Mapped["BenchmarkRun"] = relationship(
        back_populates="attempts",
    )

    # Each attempt receives at most one evaluation result. -H
    evaluation: Mapped["Evaluation | None"] = relationship(
        back_populates="attempt",
        uselist=False,
        cascade="all, delete-orphan",
    )


# Stores the correctness and execution results for a generated solution.
# This keeps model generation data separate from evaluation data. -H
class Evaluation(Base):
    __tablename__ = "evaluations"

    # Unique identifier for the evaluation. -H
    id: Mapped[int] = mapped_column(primary_key=True)

    # Connects this evaluation to the attempt being evaluated.
    # unique=True enforces one evaluation per attempt. -H
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempts.id"),
        nullable=False,
        unique=True,
    )

    # Indicates whether compilation/transpilation succeeded.
    # For Zak this represents whether the Zak program compiled successfully.
    # Python runs may leave this value null if compilation is not applicable. -H
    compile_success: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    # Stores compiler errors or other compiler output.
    # This can later be used to create repair prompts. -H
    compiler_output: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Stores the Python output produced by the Zak transpiler.
    # This remains null for normal Python benchmark runs. -H
    transpiled_code: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Number of hidden tests passed by the generated solution. -H
    tests_passed: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Total number of hidden tests executed. -H
    tests_total: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Final correctness result for this attempt.
    # True means the generated solution passed the required evaluation. -H
    correct: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    # Measures how long execution/testing took in milliseconds. -H
    execution_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Timestamp for when the evaluation was stored. -H
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship back to the generation attempt. -H
    attempt: Mapped["Attempt"] = relationship(
        back_populates="evaluation",
    )
