"""Auto-retry and flaky test detection"""
import json
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from .config import get_storage_dir
from .models import TestResults, FlakyTest
from .test_runner import run_filtered_tests


class FlakyTestTracker:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.storage = get_storage_dir(project_path) / "trends"
        self.flaky_file = self.storage / "flaky_tests.json"

    def _load_data(self) -> dict[str, dict]:
        if not self.flaky_file.exists():
            return {}
        try:
            return json.loads(self.flaky_file.read_text())
        except json.JSONDecodeError:
            return {}

    def _save_data(self, data: dict):
        self.flaky_file.write_text(json.dumps(data, indent=2))

    def record_result(self, test_name: str, passed: bool):
        """Record a test result"""
        data = self._load_data()

        if test_name not in data:
            data[test_name] = {"pass_count": 0, "fail_count": 0}

        if passed:
            data[test_name]["pass_count"] += 1
        else:
            data[test_name]["fail_count"] += 1

        self._save_data(data)

    def get_flaky_tests(self, threshold: float = 0.3) -> list[FlakyTest]:
        """Get tests that have flakiness score above threshold"""
        data = self._load_data()
        flaky = []

        for name, stats in data.items():
            total = stats["pass_count"] + stats["fail_count"]
            if total >= 2:  # Need at least 2 runs to determine flakiness
                score = stats["fail_count"] / total
                if 0 < score < (1 - threshold):  # Flaky = sometimes pass, sometimes fail
                    flaky.append(FlakyTest(
                        name=name,
                        pass_count=stats["pass_count"],
                        fail_count=stats["fail_count"]
                    ))

        return sorted(flaky, key=lambda x: x.flakiness_score, reverse=True)

    def is_known_flaky(self, test_name: str, threshold: float = 0.3) -> bool:
        """Check if test is known to be flaky"""
        data = self._load_data()
        if test_name not in data:
            return False

        stats = data[test_name]
        total = stats["pass_count"] + stats["fail_count"]
        if total < 2:
            return False

        score = stats["fail_count"] / total
        return 0 < score < (1 - threshold)

    def clear(self):
        """Clear flaky test data"""
        if self.flaky_file.exists():
            self.flaky_file.unlink()


def run_with_retry(
    editor_path: str,
    project_path: str,
    initial_results: TestResults,
    max_retries: int = 3,
    platform: str = "EditMode",
    on_retry: Callable[[int, list[str]], None] | None = None
) -> tuple[TestResults, list[FlakyTest]]:
    """
    Retry failed tests and detect flaky ones.

    Returns:
        - Final TestResults (with flaky tests removed from failures)
        - List of detected flaky tests
    """
    if max_retries <= 0 or not initial_results.failed_tests:
        return initial_results, []

    tracker = FlakyTestTracker(project_path)
    failed_test_names = [ft.name for ft in initial_results.failed_tests]
    flaky_tests = []
    still_failing = set(failed_test_names)

    for retry_num in range(1, max_retries + 1):
        if not still_failing:
            break

        if on_retry:
            on_retry(retry_num, list(still_failing))

        # Re-run only the failing tests
        retry_results = run_filtered_tests(
            editor_path,
            project_path,
            list(still_failing),
            platform=platform
        )

        # If no tests ran (filter didn't match or parse failed), skip
        if retry_results.total == 0:
            continue

        # Check which tests passed this time (flaky!)
        retry_failed_names = {ft.name for ft in retry_results.failed_tests}

        # Only mark tests as passed if Unity ran all expected tests
        # (prevents false positives when filter doesn't match some tests)
        all_tests_ran = retry_results.total >= len(still_failing)

        for test_name in list(still_failing):
            if test_name in retry_failed_names:
                # Still failing
                tracker.record_result(test_name, passed=False)
            elif all_tests_ran:
                # Test passed on retry - it's flaky
                tracker.record_result(test_name, passed=True)
                still_failing.discard(test_name)

                for ft in initial_results.failed_tests:
                    if ft.name == test_name:
                        flaky_tests.append(FlakyTest(
                            name=test_name,
                            pass_count=1,
                            fail_count=1
                        ))
                        break

    # Build final results
    final_failed = [ft for ft in initial_results.failed_tests if ft.name in still_failing]

    final_results = TestResults(
        total=initial_results.total,
        passed=initial_results.total - len(final_failed),
        failed=len(final_failed),
        warnings=initial_results.warnings,
        failed_tests=final_failed,
        filter_pattern=initial_results.filter_pattern
    )

    return final_results, flaky_tests


def get_known_flaky_tests(project_path: str, threshold: float = 0.3) -> list[str]:
    """Get list of known flaky test names"""
    tracker = FlakyTestTracker(project_path)
    return [ft.name for ft in tracker.get_flaky_tests(threshold)]


def should_retry_test(project_path: str, test_name: str) -> bool:
    """Check if a test should be retried based on history"""
    tracker = FlakyTestTracker(project_path)
    return tracker.is_known_flaky(test_name)
