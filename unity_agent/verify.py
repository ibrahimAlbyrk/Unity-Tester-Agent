import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

from .test_runner import run_filtered_tests
from .trends import TrendsManager


@dataclass
class VerifyResult:
    test_name: str
    passed: bool
    previous_error: str | None = None
    current_error: str | None = None
    is_fixed: bool = False
    was_failing: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VerifyReport:
    results: list[VerifyResult]
    all_fixed: bool = False
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "verify_results": [r.to_dict() for r in self.results],
            "all_fixed": self.all_fixed,
            "summary": self.summary
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def get_previous_failures(project_path: str) -> dict[str, str]:
    """Get map of test_name -> error_message from last run"""
    trends = TrendsManager(project_path)
    latest = trends.get_latest()

    if not latest:
        return {}

    failed_map = {}
    failed_names = latest.get("failed_test_names", [])

    # Try to get error messages from stored data
    history_path = Path(project_path) / ".unity-agent" / "trends" / "failed_details.json"
    if history_path.exists():
        try:
            data = json.loads(history_path.read_text())
            for name in failed_names:
                if name in data:
                    failed_map[name] = data[name].get("message", "Unknown error")
                else:
                    failed_map[name] = "Unknown error (no details stored)"
        except Exception:
            for name in failed_names:
                failed_map[name] = "Unknown error"
    else:
        for name in failed_names:
            failed_map[name] = "Unknown error"

    return failed_map


def save_failed_details(project_path: str, failed_tests: list):
    """Save failed test details for future verification"""
    storage_path = Path(project_path) / ".unity-agent" / "trends"
    storage_path.mkdir(parents=True, exist_ok=True)

    details_path = storage_path / "failed_details.json"

    existing = {}
    if details_path.exists():
        try:
            existing = json.loads(details_path.read_text())
        except Exception:
            pass

    for test in failed_tests:
        existing[test.name] = {
            "message": test.message,
            "stack_trace": test.stack_trace[:500] if test.stack_trace else None
        }

    details_path.write_text(json.dumps(existing, indent=2))


def verify_fix(
    editor_path: str,
    project_path: str,
    test_names: list[str],
    platform: Literal["EditMode", "PlayMode"] = "EditMode"
) -> VerifyReport:
    """Run specific tests and compare with previous failures"""
    previous_failures = get_previous_failures(project_path)

    # Run the specified tests
    results = run_filtered_tests(editor_path, project_path, test_names, platform)

    # Build verification results
    verify_results = []
    fixed_count = 0
    total_verifiable = 0

    # Create map of current failures
    current_failures = {t.name: t.message for t in results.failed_tests}

    for test_name in test_names:
        was_failing = test_name in previous_failures
        now_passing = test_name not in current_failures
        is_fixed = was_failing and now_passing

        if was_failing:
            total_verifiable += 1
            if is_fixed:
                fixed_count += 1

        result = VerifyResult(
            test_name=test_name,
            passed=now_passing,
            previous_error=previous_failures.get(test_name),
            current_error=current_failures.get(test_name),
            is_fixed=is_fixed,
            was_failing=was_failing
        )
        verify_results.append(result)

    all_fixed = fixed_count == total_verifiable and total_verifiable > 0

    # Build summary
    if total_verifiable == 0:
        summary = f"Ran {len(test_names)} test(s). None were previously failing."
    else:
        summary = f"Fixed {fixed_count}/{total_verifiable} previously failing test(s)."
        if all_fixed:
            summary += " All fixes verified!"

    return VerifyReport(
        results=verify_results,
        all_fixed=all_fixed,
        summary=summary
    )


def quick_verify(
    editor_path: str,
    project_path: str,
    test_name: str,
    platform: Literal["EditMode", "PlayMode"] = "EditMode"
) -> bool:
    """Quick single test verification - returns True if fixed"""
    report = verify_fix(editor_path, project_path, [test_name], platform)
    return report.all_fixed
