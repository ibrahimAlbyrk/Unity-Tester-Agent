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
from unity_agent.groups import GroupManager, get_group_manager
from unity_agent.deps import DependencyAnalyzer, export_dependencies
from unity_agent.verify import verify_fix, save_failed_details
from unity_agent.error_context import build_error_context, build_compilation_error_context


def _print_editor_not_found(console: Console, json_mode: bool = False):
    """Print helpful error when Unity editor is not found"""
    if json_mode:
        import json
        print(json.dumps({
            "error": "Unity editor not found",
            "suggestions": [
                "Check ProjectSettings/ProjectVersion.txt exists",
                "Set editor_path in .unity-agent.yaml",
                "Use -e /path/to/Unity flag"
            ]
        }))
    else:
        console.print("[red]Error:[/] Unity editor not found")
        console.print("\n[dim]Suggestions:[/]")
        console.print("  • Check [cyan]ProjectSettings/ProjectVersion.txt[/] exists")
        console.print("  • Set [cyan]editor_path[/] in .unity-agent.yaml")
        console.print("  • Use [cyan]-e /path/to/Unity[/] flag")


def main():
    parser = argparse.ArgumentParser(
        description="Unity Test Agent - Compile and test Unity projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -p ./MyProject                    Run tests with default settings
  %(prog)s -p ./MyProject -j --with-context  JSON output for AI agents
  %(prog)s -p ./MyProject -i --retries 3     Interactive debug mode
  %(prog)s -p ./MyProject --group player     Run specific test group
"""
    )

    # Required - support both positional and flag
    required = parser.add_argument_group("Required")
    required.add_argument("project", nargs="?", help="Unity project path")
    required.add_argument("-p", "--project-path", help="Unity project path (alternative to positional)")

    # Output modes
    output = parser.add_argument_group("Output Modes")
    output.add_argument("-j", "--json", action="store_true", help="JSON output (for agents)")
    output.add_argument("-i", "--interactive", action="store_true", help="Interactive TUI mode")
    output.add_argument("--with-context", action="store_true", help="Include detailed error context")

    # Test options
    testing = parser.add_argument_group("Testing")
    testing.add_argument("--filter", help="Test filter pattern (e.g., 'PlayerTests.*')")
    testing.add_argument("--platform", choices=["EditMode", "PlayMode"], default="EditMode", help="Test platform")
    testing.add_argument("--group", help="Run test group(s) (comma-separated)")
    testing.add_argument("--list-groups", action="store_true", help="List available test groups")
    testing.add_argument("--retries", type=int, default=0, help="Retry failed tests N times")
    testing.add_argument("--flaky-threshold", type=float, default=0.3, help="Flaky threshold (0.0-1.0)")

    # Agent features
    agent = parser.add_argument_group("Agent Features")
    agent.add_argument("--verify-fix", metavar="TESTS", help="Verify fix for test(s)")
    agent.add_argument("--export-deps", metavar="PATH", help="Export dependency graph to JSON")
    agent.add_argument("--show-deps", metavar="CLASS", help="Show dependencies for a class")

    # Reports
    reports = parser.add_argument_group("Reports & History")
    reports.add_argument("--junit", metavar="PATH", help="Export JUnit XML to path")
    reports.add_argument("--show-trends", action="store_true", help="Show pass rate trends")
    reports.add_argument("--diff", action="store_true", help="Compare with previous run")

    # Cache & config
    config_grp = parser.add_argument_group("Cache & Config")
    config_grp.add_argument("-e", "--editor-path", help="Unity editor path (auto-detect if not set)")
    config_grp.add_argument("--no-cache", action="store_true", help="Disable cache")
    config_grp.add_argument("--clear-cache", action="store_true", help="Clear cache before run")
    config_grp.add_argument("--init", action="store_true", help="Create default config file")
    config_grp.add_argument("--wizard", action="store_true", help="Interactive setup wizard")
    config_grp.add_argument("--show-config", action="store_true", help="Show effective config")

    args = parser.parse_args()

    # Resolve project path (positional or -p flag)
    if args.project:
        args.project_path = args.project
    elif not args.project_path:
        parser.error("Project path required: provide as positional or use -p flag")

    # Handle init / wizard
    if args.wizard:
        from unity_agent.config import run_setup_wizard
        run_setup_wizard(args.project_path)
        return 0

    if args.init:
        from unity_agent.config import create_default_config
        config_path = create_default_config(args.project_path)
        print(f"Created config: {config_path}")
        return 0

    # Handle show-config
    if args.show_config:
        return run_show_config(args)

    # Handle clear cache
    if args.clear_cache:
        from unity_agent.cache import invalidate_cache
        invalidate_cache(args.project_path)
        if args.json:
            import json
            print(json.dumps({"cache_cleared": True}))
            return 0
        print("Cache cleared")

    # Load config and merge CLI args
    config = load_config(args.project_path)
    config = merge_cli_args(config, args)

    # Ensure storage directory exists
    get_storage_dir(args.project_path)

    # Handle list-groups
    if args.list_groups:
        return run_list_groups(args, config)

    # Handle export-deps
    if args.export_deps:
        return run_export_deps(args)

    # Handle show-deps
    if args.show_deps:
        return run_show_deps(args)

    # Handle verify-fix
    if args.verify_fix:
        return run_verify_fix(args, config)

    # Handle group filter
    if args.group:
        group_mgr = get_group_manager(config)
        group_names = [g.strip() for g in args.group.split(",")]
        filter_pattern = group_mgr.get_filter_pattern(group_names)
        if filter_pattern:
            config.test.filter = filter_pattern
        else:
            # Build smart error message
            available = group_mgr.get_available_groups()
            not_found = [g for g in group_names if not group_mgr.has_group(g)]

            if args.json:
                import json
                error_data = {
                    "error": f"Group(s) not found: {', '.join(not_found)}",
                    "groups_not_found": not_found,
                    "available_groups": available
                }
                # Add suggestions
                suggestions = []
                for nf in not_found:
                    suggestions.extend(group_mgr.suggest_similar(nf))
                if suggestions:
                    error_data["suggestions"] = list(set(suggestions))
                print(json.dumps(error_data))
            else:
                console = Console()
                console.print(f"[red]Error:[/] Group(s) not found: [yellow]{', '.join(not_found)}[/]")
                if available:
                    console.print(f"\n[dim]Available groups:[/] {', '.join(available)}")
                # Show suggestions
                suggestions = []
                for nf in not_found:
                    suggestions.extend(group_mgr.suggest_similar(nf))
                if suggestions:
                    console.print(f"[dim]Did you mean:[/] [cyan]{', '.join(set(suggestions))}[/]")
                console.print(f"\n[dim]List groups:[/] ./tester.sh --list-groups")
            return 1

    if args.json:
        return run_json_mode(args, config)
    elif args.interactive:
        return run_interactive_mode(args, config)
    else:
        return run_ui_mode(args, config)


def run_show_config(args):
    """Show effective merged config"""
    from pathlib import Path
    import yaml

    console = Console()
    config = load_config(args.project_path)
    config = merge_cli_args(config, args)

    # Check config sources
    project_cfg = Path(args.project_path) / ".unity-agent.yaml"
    global_cfg = Path.home() / ".unity-agent.yaml"

    console.print("[cyan bold]Effective Configuration[/]\n")

    # Show sources
    sources = []
    if project_cfg.exists():
        sources.append(f"[green]✓[/] Project: {project_cfg}")
    if global_cfg.exists():
        sources.append(f"[green]✓[/] Global: {global_cfg}")
    sources.append("[dim]+ CLI arguments[/]")

    console.print("[dim]Sources (in merge order):[/]")
    for src in sources:
        console.print(f"  {src}")
    console.print()

    # Print config as YAML
    config_dict = config.to_dict()
    yaml_str = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
    console.print(yaml_str)

    return 0


def run_list_groups(args, config: Config):
    """List available test groups"""
    console = Console()
    cli = CLIRenderer(console)

    group_mgr = get_group_manager(config)
    groups = group_mgr.list_groups()

    if not groups:
        # Try auto-detection
        auto_groups = GroupManager.auto_detect_groups(args.project_path)
        if auto_groups:
            console.print("[dim]No groups configured. Auto-detected groups:[/]\n")
            for name, patterns in auto_groups.items():
                console.print(f"  [cyan]{name}[/]: {', '.join(patterns[:3])}")
            console.print("\n[dim]Add these to .unity-agent.yaml under test_groups:[/]")
        else:
            console.print("[yellow]No test groups configured or detected[/]")
        return 0

    cli.groups_panel(groups)
    return 0


def run_export_deps(args):
    """Export dependency graph to JSON"""
    console = Console()
    console.print(f"[dim]Analyzing dependencies in {args.project_path}...[/]")

    export_dependencies(args.project_path, args.export_deps)
    console.print(f"[green]✓[/] Exported to {args.export_deps}")
    return 0


def run_show_deps(args):
    """Show dependencies for a class"""
    console = Console()
    cli = CLIRenderer(console)

    analyzer = DependencyAnalyzer(args.project_path)
    analyzer.analyze()

    deps_info = analyzer.get_class_deps(args.show_deps)
    cli.deps_panel(args.show_deps, deps_info)
    return 0


def run_verify_fix(args, config: Config):
    """Verify fix for specific tests"""
    console = Console()
    cli = CLIRenderer(console)

    # Detect editor
    editor_path = config.project.editor_path or detect_unity_editor(args.project_path)
    if not editor_path:
        _print_editor_not_found(console, args.json if hasattr(args, 'json') else False)
        return 1

    test_names = [t.strip() for t in args.verify_fix.split(",")]
    console.print(f"[dim]Verifying fix for: {', '.join(test_names)}[/]\n")

    report = verify_fix(
        editor_path,
        args.project_path,
        test_names,
        platform=config.test.platform
    )

    if args.json:
        print(report.to_json())
    else:
        cli.verify_panel(report)

    return 0 if report.all_fixed else 1


def run_json_mode(args, config: Config):
    """Run in JSON-only mode"""
    import json

    result, metrics = run_pipeline(args, config)

    # Build output dict
    output = asdict(result)

    # Add trends if requested
    if args.show_trends and result.test_results:
        trends_mgr = TrendsManager(args.project_path)
        history = trends_mgr.get_history(limit=10)
        output["trends"] = [
            {
                "timestamp": h.timestamp,
                "pass_rate": h.pass_rate,
                "total": h.total,
                "passed": h.passed,
                "failed": h.failed
            }
            for h in history
        ]

    # Add diff if requested
    if args.diff and result.test_results:
        baseline = get_baseline(args.project_path)
        diff = compare_results(result.test_results, baseline)
        if diff:
            output["diff"] = asdict(diff)

    print(json.dumps(output, indent=2))
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
        # Show first error context if available
        if args.with_context and result.compilation_errors and result.compilation_errors[0].context:
            cli.error_context_panel(result.compilation_errors[0].context)
    elif result.test_results:
        cli.results_panel(result.test_results)
        cli.failed_tests(result.test_results)

        # Show first error context if available
        if args.with_context and result.test_results.failed_tests:
            first_fail = result.test_results.failed_tests[0]
            if first_fail.context:
                cli.error_context_panel(first_fail.context)

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

    # Store detected path in config for retry
    if editor_path and not config.project.editor_path:
        config.project.editor_path = editor_path

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

        # Add error context if requested
        if hasattr(args, 'with_context') and args.with_context:
            for err in errors:
                err.context = build_compilation_error_context(
                    err.code, err.file, err.line, err.message, args.project_path
                )

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

    # Add error context if requested
    if hasattr(args, 'with_context') and args.with_context:
        for ft in test_results.failed_tests:
            ft.context = build_error_context(ft.message, ft.stack_trace, args.project_path)

    # Save failed test details for verification
    if test_results.failed_tests:
        save_failed_details(args.project_path, test_results.failed_tests)

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
