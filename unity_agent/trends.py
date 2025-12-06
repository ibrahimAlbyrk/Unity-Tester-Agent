"""Historical test results tracking"""
import json
import subprocess
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import get_storage_dir
from .models import UnityResult, PerformanceMetrics, TestResults


@dataclass
class TrendEntry:
    timestamp: str
    commit_hash: str | None
    total: int
    passed: int
    failed: int
    pass_rate: float
    compile_time_ms: float
    test_time_ms: float
    flaky_tests: list[str] = field(default_factory=list)
    failed_test_names: list[str] = field(default_factory=list)

    @classmethod
    def from_result(cls, result: UnityResult, metrics: PerformanceMetrics | None = None) -> "TrendEntry":
        test_results = result.test_results
        if not test_results:
            return cls(
                timestamp=datetime.now().isoformat(),
                commit_hash=get_git_commit_hash(),
                total=0,
                passed=0,
                failed=0,
                pass_rate=0.0,
                compile_time_ms=metrics.compile_ms if metrics else 0.0,
                test_time_ms=metrics.test_run_ms if metrics else 0.0,
            )

        pass_rate = (test_results.passed / test_results.total * 100) if test_results.total > 0 else 0.0

        return cls(
            timestamp=datetime.now().isoformat(),
            commit_hash=get_git_commit_hash(),
            total=test_results.total,
            passed=test_results.passed,
            failed=test_results.failed,
            pass_rate=round(pass_rate, 2),
            compile_time_ms=metrics.compile_ms if metrics else 0.0,
            test_time_ms=metrics.test_run_ms if metrics else 0.0,
            flaky_tests=[ft.name for ft in (result.flaky_tests or [])],
            failed_test_names=[ft.name for ft in test_results.failed_tests],
        )


class TrendsManager:
    def __init__(self, project_path: str, max_history: int = 100):
        self.project_path = project_path
        self.max_history = max_history
        self.trends_dir = get_storage_dir(project_path) / "trends"
        self.trends_dir.mkdir(exist_ok=True)
        self.history_file = self.trends_dir / "history.json"

    def _load_history(self) -> list[dict]:
        if not self.history_file.exists():
            return []
        try:
            return json.loads(self.history_file.read_text())
        except json.JSONDecodeError:
            return []

    def _save_history(self, history: list[dict]):
        self.history_file.write_text(json.dumps(history, indent=2))

    def save(self, result: UnityResult, metrics: PerformanceMetrics | None = None):
        """Save current result to trend history"""
        entry = TrendEntry.from_result(result, metrics)
        history = self._load_history()

        history.append(asdict(entry))

        # Trim to max history
        if len(history) > self.max_history:
            history = history[-self.max_history:]

        self._save_history(history)
        return entry

    def get_history(self, limit: int | None = None) -> list[TrendEntry]:
        """Get trend history"""
        history = self._load_history()

        if limit:
            history = history[-limit:]

        return [TrendEntry(**h) for h in history]

    def get_latest(self) -> TrendEntry | None:
        """Get most recent trend entry"""
        history = self.get_history(limit=1)
        return history[0] if history else None

    def get_previous(self) -> TrendEntry | None:
        """Get second most recent (for diff comparison)"""
        history = self.get_history(limit=2)
        return history[0] if len(history) >= 2 else None

    def get_pass_rate_trend(self, limit: int = 10) -> list[float]:
        """Get pass rate history for charting"""
        history = self.get_history(limit=limit)
        return [h.pass_rate for h in history]

    def get_failed_test_history(self, test_name: str, limit: int = 10) -> list[bool]:
        """Get pass/fail history for specific test"""
        history = self.get_history(limit=limit)
        return [test_name in h.failed_test_names for h in history]

    def clear(self):
        """Clear all trend history"""
        if self.history_file.exists():
            self.history_file.unlink()


def get_git_commit_hash() -> str | None:
    """Get current git commit hash"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def save_trend(project_path: str, result: UnityResult, metrics: PerformanceMetrics | None = None) -> TrendEntry:
    """Convenience function to save trend"""
    manager = TrendsManager(project_path)
    return manager.save(result, metrics)


def get_trends(project_path: str, limit: int = 10) -> list[TrendEntry]:
    """Convenience function to get trends"""
    manager = TrendsManager(project_path)
    return manager.get_history(limit=limit)


def get_baseline(project_path: str) -> TrendEntry | None:
    """Get previous run for comparison"""
    manager = TrendsManager(project_path)
    return manager.get_previous()
