"""Test results diff/comparison"""
from dataclasses import dataclass, field
from ..models import TestResults, TestDiff
from ..trends import TrendEntry, TrendsManager


def compare_results(current: TestResults, baseline: TrendEntry | None) -> TestDiff | None:
    """Compare current results with baseline"""
    if baseline is None:
        return None

    current_failed = {ft.name for ft in current.failed_tests}
    baseline_failed = set(baseline.failed_test_names)

    # Calculate differences
    new_failures = list(current_failed - baseline_failed)
    fixed = list(baseline_failed - current_failed)
    still_failing = list(current_failed & baseline_failed)

    # Pass rates
    current_pass_rate = (current.passed / current.total * 100) if current.total > 0 else 0.0
    baseline_pass_rate = baseline.pass_rate

    return TestDiff(
        new_failures=sorted(new_failures),
        fixed=sorted(fixed),
        still_failing=sorted(still_failing),
        pass_rate_before=baseline_pass_rate,
        pass_rate_after=round(current_pass_rate, 2)
    )


def get_diff_from_history(project_path: str, current: TestResults) -> TestDiff | None:
    """Compare current results with previous run from history"""
    manager = TrendsManager(project_path)
    baseline = manager.get_previous()
    return compare_results(current, baseline)


def format_diff_summary(diff: TestDiff) -> str:
    """Format diff as text summary"""
    lines = []

    delta = diff.pass_rate_delta
    delta_str = f"+{delta:.1f}%" if delta >= 0 else f"{delta:.1f}%"
    arrow = "↑" if delta >= 0 else "↓"

    lines.append(f"{arrow} Pass Rate: {diff.pass_rate_before:.1f}% → {diff.pass_rate_after:.1f}% ({delta_str})")
    lines.append("")

    if diff.fixed:
        lines.append(f"✓ Fixed ({len(diff.fixed)}):")
        for name in diff.fixed[:5]:
            short = name.split(".")[-1] if "." in name else name
            lines.append(f"  {short}")
        if len(diff.fixed) > 5:
            lines.append(f"  ... and {len(diff.fixed) - 5} more")
        lines.append("")

    if diff.new_failures:
        lines.append(f"✗ New Failures ({len(diff.new_failures)}):")
        for name in diff.new_failures[:5]:
            short = name.split(".")[-1] if "." in name else name
            lines.append(f"  {short}")
        if len(diff.new_failures) > 5:
            lines.append(f"  ... and {len(diff.new_failures) - 5} more")
        lines.append("")

    if diff.still_failing:
        lines.append(f"⚠ Still Failing ({len(diff.still_failing)})")

    return "\n".join(lines)


def has_regressions(diff: TestDiff) -> bool:
    """Check if there are new failures"""
    return len(diff.new_failures) > 0


def has_improvements(diff: TestDiff) -> bool:
    """Check if tests were fixed"""
    return len(diff.fixed) > 0
