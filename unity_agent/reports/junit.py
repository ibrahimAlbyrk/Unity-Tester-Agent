"""NUnit to JUnit XML format converter"""
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime


def nunit_to_junit(nunit_xml_path: str) -> str:
    """Convert NUnit XML format to JUnit XML format"""
    try:
        tree = ET.parse(nunit_xml_path)
        nunit_root = tree.getroot()
    except (ET.ParseError, FileNotFoundError) as e:
        raise ValueError(f"Failed to parse NUnit XML: {e}")

    # Create JUnit root element
    junit_root = ET.Element("testsuites")

    # Get overall stats from NUnit
    total = int(nunit_root.get("total", 0))
    failures = int(nunit_root.get("failed", 0))
    duration = float(nunit_root.get("duration", 0))
    timestamp = nunit_root.get("start-time", datetime.now().isoformat())

    junit_root.set("tests", str(total))
    junit_root.set("failures", str(failures))
    junit_root.set("time", str(duration))
    junit_root.set("timestamp", timestamp)

    # Group test cases by assembly/namespace
    test_suites = {}

    for test_case in nunit_root.iter("test-case"):
        fullname = test_case.get("fullname", "Unknown")
        classname = test_case.get("classname", "")

        # Use classname as suite name, or extract from fullname
        if not classname and "." in fullname:
            parts = fullname.rsplit(".", 1)
            classname = parts[0] if len(parts) > 1 else "Default"

        suite_name = classname or "Default"

        if suite_name not in test_suites:
            test_suites[suite_name] = []

        test_suites[suite_name].append(test_case)

    # Create JUnit test suites
    for suite_name, test_cases in test_suites.items():
        suite = ET.SubElement(junit_root, "testsuite")
        suite.set("name", suite_name)
        suite.set("tests", str(len(test_cases)))

        suite_failures = 0
        suite_time = 0.0

        for tc in test_cases:
            testcase = ET.SubElement(suite, "testcase")
            testcase.set("name", tc.get("name", "Unknown"))
            testcase.set("classname", tc.get("classname", suite_name))

            tc_time = float(tc.get("duration", 0))
            testcase.set("time", str(tc_time))
            suite_time += tc_time

            result = tc.get("result", "")

            if result == "Failed":
                suite_failures += 1
                failure_elem = tc.find("failure")

                if failure_elem is not None:
                    junit_failure = ET.SubElement(testcase, "failure")

                    message_elem = failure_elem.find("message")
                    if message_elem is not None and message_elem.text:
                        junit_failure.set("message", message_elem.text.strip()[:200])

                    stack_elem = failure_elem.find("stack-trace")
                    if stack_elem is not None and stack_elem.text:
                        junit_failure.text = stack_elem.text
                else:
                    junit_failure = ET.SubElement(testcase, "failure")
                    junit_failure.set("message", "Test failed")

            elif result == "Skipped":
                skipped = ET.SubElement(testcase, "skipped")
                reason = tc.find(".//reason/message")
                if reason is not None and reason.text:
                    skipped.set("message", reason.text)

        suite.set("failures", str(suite_failures))
        suite.set("time", str(suite_time))

    return ET.tostring(junit_root, encoding="unicode", xml_declaration=True)


def save_junit_report(nunit_xml_path: str, output_path: str):
    """Convert NUnit XML and save as JUnit XML"""
    junit_xml = nunit_to_junit(nunit_xml_path)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(junit_xml)

    return output_path


def create_junit_from_results(results, output_path: str):
    """Create JUnit XML directly from TestResults object"""
    from ..models import TestResults

    junit_root = ET.Element("testsuites")
    junit_root.set("tests", str(results.total))
    junit_root.set("failures", str(results.failed))
    junit_root.set("timestamp", datetime.now().isoformat())

    # Single test suite
    suite = ET.SubElement(junit_root, "testsuite")
    suite.set("name", "Unity Tests")
    suite.set("tests", str(results.total))
    suite.set("failures", str(results.failed))

    # Add failed tests
    for failed in results.failed_tests:
        testcase = ET.SubElement(suite, "testcase")

        # Extract class and method name
        if "." in failed.name:
            parts = failed.name.rsplit(".", 1)
            testcase.set("classname", parts[0])
            testcase.set("name", parts[1])
        else:
            testcase.set("classname", "Unity")
            testcase.set("name", failed.name)

        testcase.set("time", str(failed.duration))

        failure = ET.SubElement(testcase, "failure")
        failure.set("message", failed.message[:200] if failed.message else "Test failed")
        failure.text = failed.stack_trace

    # Add placeholder for passed tests (JUnit format expects all tests)
    passed_count = results.passed
    for i in range(min(passed_count, 10)):  # Limit to avoid huge files
        testcase = ET.SubElement(suite, "testcase")
        testcase.set("classname", "Unity")
        testcase.set("name", f"passed_test_{i+1}")
        testcase.set("time", "0.001")

    junit_xml = ET.tostring(junit_root, encoding="unicode", xml_declaration=True)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(junit_xml)

    return output_path
