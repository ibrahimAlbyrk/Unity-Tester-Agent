#!/usr/bin/env python3
import argparse
import sys
import time
from dataclasses import asdict
from rich.console import Console

from unity_agent.config import load_config, merge_cli_args, get_storage_dir, Config
from unity_agent.models import UnityResult, PerformanceMetrics, TestResults
from unity_agent.version import detect_unity_editor
from unity_agent.compiler import compile_project
from unity_agent.test_runner import run_tests
from unity_agent.cache import CacheManager, get_cached_compile, set_cached_compile
from unity_agent.trends import save_trend, get_trends, get_baseline, TrendsManager
from unity_agent.retry import run_with_retry
from unity_agent.reports.diff import compare_results, get_diff_from_history
from unity_agent.reports.junit import save_junit_report, create_junit_from_results
from unity_agent.cli import CLIRenderer


def main():
    parser = argparse.ArgumentParser(
        description="Unity Test Agent - Compile and test Unity projects",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Required
    parser.add_argument("-p", "--project-path", required=True, help="Unity project path")

    # Optional - Basic
    parser.add_argument("-e", "--editor-path", help="Unity editor path (auto-detect if not provided)")
    parser.add_argument("-j", "--json", action="store_true", help="Output only JSON")

    # Test options
    parser.add_argument("--filter", help="Test filter pattern (e.g., 'PlayerTests.*')")
    parser.add_argument("--platform", choices=["EditMode", "PlayMode"], default="EditMode", help="Test platform")

    # Cache options
    parser.add_argument("--no-cache", action="store_true", help="Disable cache")
    parser.add_argument("--clear-cache", action="store_true", help="Clear cache before run")

    # Output options
    parser.add_argument("--junit", metavar="PATH", help="Export JUnit XML to path")

    # Retry options
    parser.add_argument("--retries", type=int, default=0, help="Retry failed tests N times")
    parser.add_argument("--flaky-threshold", type=float, default=0.3, help="Flaky test threshold (0.0-1.0)")

    # Trends options
    parser.add_argument("--show-trends", action="store_true", help="Show pass rate trends")
    parser.add_argument("--diff", action="store_true", help="Show diff vs previous run")

    # Interactive mode
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive TUI")

    # Init
    parser.add_argument("--init", action="store_true", help="Create default config file")

    args = parser.parse_args()

    # Handle init
    if args.init:
        from unity_agent.config import create_default_config
        config_path = create_default_config(args.project_path)
        print(f"Created config: {config_path}")
        return 0

    # Handle clear cache
    if args.clear_cache:
        from unity_agent.cache import invalidate_cache
        invalidate_cache(args.project_path)
        print("Cache cleared")
        if args.json:
            return 0

    # Load config and merge CLI args
    config = load_config(args.project_path)
    config = merge_cli_args(config, args)

    # Ensure storage directory exists
    get_storage_dir(args.project_path)

    if args.json:
        return run_json_mode(args, config)
    elif args.interactive:
        return run_interactive_mode(args, config)
    else:
        return run_ui_mode(args, config)


def run_json_mode(args, config: Config):
    """Run in JSON-only mode"""
    result, metrics = run_pipeline(args, config)
    print(result.to_json())
    return 0 if result.success else 1


def run_interactive_mode(args, config: Config):
    """Run in interactive Rich CLI mode"""
    console = Console()
    cli = CLIRenderer(console)
    current_progress = None

    def on_step_start(step: int, total: int, message: str):
        nonlocal current_progress
        current_progress = cli.step_start(step, total, message)
        current_progress.start()

    def on_step_complete(step: int, total: int, message: str, success: bool):
        nonlocal current_progress
        if current_progress:
            current_progress.stop()
            current_progress = None
        cli.step_complete(step, total, message, success)

    cli.header(args.project_path)
    result, metrics = run_pipeline(
        args, config,
        on_step_start=on_step_start,
        on_step_complete=on_step_complete,
        cli=cli
    )

    from unity_agent.interactive import run_interactive
    run_interactive(result, args.project_path, config.project.editor_path or "", config)

    return 0 if result.success else 1


def run_ui_mode(args, config: Config):
    """Run with Rich CLI UI"""
    console = Console()
    cli = CLIRenderer(console)
    current_progress = None

    def on_step_start(step: int, total: int, message: str):
        nonlocal current_progress
        current_progress = cli.step_start(step, total, message)
        current_progress.start()

    def on_step_complete(step: int, total: int, message: str, success: bool):
        nonlocal current_progress
        if current_progress:
            current_progress.stop()
            current_progress = None
        cli.step_complete(step, total, message, success)

    cli.header(args.project_path)

    result, metrics = run_pipeline(
        args,
        config,
        on_step_start=on_step_start,
        on_step_complete=on_step_complete,
        cli=cli
    )

    # Show results
    if result.stage == "compilation" and result.compilation_errors:
        cli.compilation_errors(result.compilation_errors)
    elif result.test_results:
        cli.results_panel(result.test_results)
        cli.failed_tests(result.test_results)

        # Show flaky tests
        if result.flaky_tests:
            cli.flaky_tests(result.flaky_tests)

        # Show diff
        if args.diff:
            baseline = get_baseline(args.project_path)
            diff = compare_results(result.test_results, baseline)
            if diff:
                cli.diff_panel(diff)

        # Show trends
        if args.show_trends:
            trends_mgr = TrendsManager(args.project_path)
            pass_rates = trends_mgr.get_pass_rate_trend(limit=10)
            cli.trends_panel(pass_rates)

    # Show performance metrics
    if metrics:
        cli.performance_panel(metrics)

    cli.final_status(result.success)
    cli.json_output(result)

    return 0 if result.success else 1


def run_pipeline(
    args,
    config: Config,
    on_step_start=None,
    on_step_complete=None,
    cli: CLIRenderer = None
) -> tuple[UnityResult, PerformanceMetrics]:
    """Execute the full pipeline"""
    metrics = PerformanceMetrics()
    total_start = time.perf_counter()

    # Step 1: Detect Editor
    if on_step_start:
        on_step_start(1, 3, "Detecting Unity Editor...")

    step_start = time.perf_counter()
    editor_path = config.project.editor_path or detect_unity_editor(args.project_path)
    metrics.editor_detect_ms = (time.perf_counter() - step_start) * 1000

    if not editor_path:
        if on_step_complete:
            on_step_complete(1, 3, "Editor not found", False)
        return UnityResult(success=False, stage="compilation", compilation_errors=[]), metrics

    # Extract version
    import re
    match = re.search(r"(\d{4}\.\d+\.\d+[a-z]\d+)", editor_path)
    version = match.group(1) if match else "Unknown"

    if on_step_complete:
        on_step_complete(1, 3, f"Editor detected ({version})", True)

    # Step 2: Compile
    if on_step_start:
        on_step_start(2, 3, "Compiling scripts...")

    step_start = time.perf_counter()

    # Check cache
    cached_compile = None
    if config.cache.enabled:
        cached_compile = get_cached_compile(args.project_path, config.cache.ttl)
        if cached_compile:
            if cli:
                cli.cache_hit("compilation")

    if cached_compile:
        compile_success = cached_compile["success"]
        from unity_agent.models import CompilationError
        errors = [CompilationError(**e) for e in cached_compile.get("errors", [])]
    else:
        compile_success, errors = compile_project(editor_path, args.project_path)
        # Save to cache
        if config.cache.enabled:
            set_cached_compile(args.project_path, compile_success, errors, config.cache.ttl)

    metrics.compile_ms = (time.perf_counter() - step_start) * 1000

    if not compile_success:
        if on_step_complete:
            on_step_complete(2, 3, f"Compilation failed ({len(errors)} errors)", False)

        result = UnityResult(
            success=False,
            stage="compilation",
            compilation_errors=errors,
            performance=metrics
        )

        # Save trend
        if config.trends.enabled:
            save_trend(args.project_path, result, metrics)

        return result, metrics

    if on_step_complete:
        on_step_complete(2, 3, "Compilation successful", True)

    # Step 3: Run Tests
    if on_step_start:
        on_step_start(3, 3, "Running tests...")

    step_start = time.perf_counter()

    # Run tests with filter
    filter_pattern = config.test.filter or args.filter
    keep_xml = bool(args.junit)

    test_results, xml_path = run_tests(
        editor_path,
        args.project_path,
        platform=config.test.platform,
        filter_pattern=filter_pattern,
        keep_xml=keep_xml
    )

    # JUnit export
    if args.junit and xml_path:
        save_junit_report(xml_path, args.junit)

    # Retry failed tests
    flaky_tests = []
    retries = config.test.retries or args.retries
    if retries > 0 and test_results.failed_tests:
        def on_retry(retry_num, tests):
            if cli:
                cli.retry_status(retry_num, retries, len(tests))

        test_results, flaky_tests = run_with_retry(
            editor_path,
            args.project_path,
            test_results,
            max_retries=retries,
            platform=config.test.platform,
            on_retry=on_retry
        )

    metrics.test_run_ms = (time.perf_counter() - step_start) * 1000
    metrics.total_ms = (time.perf_counter() - total_start) * 1000

    success = test_results.failed == 0
    msg = f"Tests completed ({test_results.passed}/{test_results.total} passed)"

    if on_step_complete:
        on_step_complete(3, 3, msg, success)

    result = UnityResult(
        success=success,
        stage="tests",
        test_results=test_results,
        performance=metrics,
        flaky_tests=flaky_tests if flaky_tests else None
    )

    # Save trend
    if config.trends.enabled:
        save_trend(args.project_path, result, metrics)

    return result, metrics


if __name__ == "__main__":
    sys.exit(main())
