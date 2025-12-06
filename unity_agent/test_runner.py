import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal
from .models import TestResults, FailedTest


def run_tests(
    editor_path: str,
    project_path: str,
    platform: Literal["EditMode", "PlayMode"] = "EditMode",
    filter_pattern: str | None = None,
    keep_xml: bool = False
) -> tuple[TestResults, str | None]:
    """Run Unity tests and return results + optional XML path"""
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        results_path = f.name

    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
        log_path = f.name

    cmd = [
        editor_path,
        "-batchmode",
        "-nographics",
        "-projectPath", project_path,
        "-runTests",
        "-testPlatform", platform,
        "-testResults", results_path,
        "-logFile", log_path
    ]

    # Add test filter if specified
    if filter_pattern:
        cmd.extend(["-testFilter", filter_pattern])

    subprocess.run(cmd)

    results = parse_test_results(results_path)

    # Cleanup log
    Path(log_path).unlink(missing_ok=True)

    # Keep or cleanup XML
    xml_path = None
    if keep_xml:
        xml_path = results_path
    else:
        Path(results_path).unlink(missing_ok=True)

    return results, xml_path


def run_filtered_tests(
    editor_path: str,
    project_path: str,
    test_names: list[str],
    platform: Literal["EditMode", "PlayMode"] = "EditMode"
) -> TestResults:
    """Run specific tests by name (for retry)"""
    if not test_names:
        return TestResults(total=0, passed=0, failed=0, warnings=0)

    # Unity testFilter accepts comma-separated names or patterns
    filter_pattern = ",".join(test_names)
    results, _ = run_tests(editor_path, project_path, platform, filter_pattern)
    return results


def parse_test_results(xml_path: str) -> TestResults:
    """Parse NUnit XML test results"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except (ET.ParseError, FileNotFoundError):
        return TestResults(total=0, passed=0, failed=0, warnings=0)

    # NUnit XML format
    total = int(root.get("total", 0))
    passed = int(root.get("passed", 0))
    failed = int(root.get("failed", 0))
    warnings = int(root.get("warnings", 0)) if root.get("warnings") else 0

    failed_tests = []
    for test_case in root.iter("test-case"):
        if test_case.get("result") == "Failed":
            name = test_case.get("fullname", test_case.get("name", "Unknown"))
            duration = float(test_case.get("duration", 0))

            failure = test_case.find("failure")
            message = ""
            stack_trace = ""

            if failure is not None:
                msg_elem = failure.find("message")
                stack_elem = failure.find("stack-trace")
                message = msg_elem.text if msg_elem is not None and msg_elem.text else ""
                stack_trace = stack_elem.text if stack_elem is not None and stack_elem.text else ""

            failed_tests.append(FailedTest(
                name=name,
                message=message,
                stack_trace=stack_trace,
                duration=duration
            ))

    return TestResults(
        total=total,
        passed=passed,
        failed=failed,
        warnings=warnings,
        failed_tests=failed_tests
    )


def get_all_test_names(xml_path: str) -> list[str]:
    """Extract all test names from NUnit XML"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except (ET.ParseError, FileNotFoundError):
        return []

    return [
        tc.get("fullname", tc.get("name", ""))
        for tc in root.iter("test-case")
        if tc.get("fullname") or tc.get("name")
    ]
