from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

RUNNER_LIMITATION = (
    "Controlled subprocess execution only. This is not a sandbox or hostile-code "
    "isolation, and it is not proof of production or AWS behavior."
)


class RunnerLanguage(StrEnum):
    JAVA = "java"
    PYTHON = "python"
    RELATIONAL = "relational"


class CapabilityState(StrEnum):
    SUPPORTED = "supported"
    MISSING = "missing"
    INCOMPATIBLE = "incompatible"


class RunnerOperation(StrEnum):
    COMPILE = "compile"
    TEST = "test"


@dataclass(frozen=True)
class DeclaredInput:
    logical_path: str
    declared_type: str
    content_ref: str
    content_hash: str


@dataclass(frozen=True)
class ProcessLimits:
    wall_seconds: float
    cpu_seconds: float
    memory_bytes: int
    process_count: int
    output_bytes: int
    file_bytes: int
    temp_bytes: int


@dataclass(frozen=True)
class OutputChunk:
    phase: str
    stream: str
    sequence: int
    content: str
    truncated: bool


@dataclass(frozen=True)
class RunnerProcessOutcome:
    pid: int
    pgid: int
    exit_code: int | None
    signal: int | None
    timed_out_or_limited: bool
    cancelled: bool
    chunks: tuple[OutputChunk, ...]
    duration_ms: int
    cpu_ms: int | None = None
