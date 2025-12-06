from dataclasses import dataclass, field, asdict
from typing import Literal, Any
import json


@dataclass
class CompilationError:
    file: str
    line: int
    code: str
    message: str
    count: int = 1
    context: Any = None  # ErrorContext, set later to avoid circular import


@dataclass
class FailedTest:
    name: str
    message: str
    stack_trace: str
    duration: float = 0.0
    context: Any = None  # ErrorContext, set later to avoid circular import


@dataclass
class TestResults:
    total: int
    passed: int
    failed: int
    warnings: int
    failed_tests: list[FailedTest] = field(default_factory=list)
    filter_pattern: str | None = None


@dataclass
class PerformanceMetrics:
    editor_detect_ms: float = 0.0
    compile_ms: float = 0.0
    test_run_ms: float = 0.0
    total_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FlakyTest:
    name: str
    pass_count: int = 0
    fail_count: int = 0

    @property
    def total_runs(self) -> int:
        return self.pass_count + self.fail_count

    @property
    def flakiness_score(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.fail_count / self.total_runs


@dataclass
class TestDiff:
    new_failures: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    still_failing: list[str] = field(default_factory=list)
    pass_rate_before: float = 0.0
    pass_rate_after: float = 0.0

    @property
    def pass_rate_delta(self) -> float:
        return self.pass_rate_after - self.pass_rate_before


@dataclass
class UnityResult:
    success: bool
    stage: Literal["compilation", "tests"]
    compilation_errors: list[CompilationError] | None = None
    test_results: TestResults | None = None
    performance: PerformanceMetrics | None = None
    flaky_tests: list[FlakyTest] | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
