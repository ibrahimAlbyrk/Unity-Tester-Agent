import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

from .models import UnityResult, TestResults, PerformanceMetrics, FlakyTest, TestDiff


# C# Error documentation links
ERROR_DOCS = {
    "CS0103": "https://learn.microsoft.com/en-us/dotnet/csharp/misc/cs0103",
    "CS0246": "https://learn.microsoft.com/en-us/dotnet/csharp/misc/cs0246",
    "CS1002": "https://learn.microsoft.com/en-us/dotnet/csharp/misc/cs1002",
    "CS1513": "https://learn.microsoft.com/en-us/dotnet/csharp/misc/cs1513",
    "CS0029": "https://learn.microsoft.com/en-us/dotnet/csharp/misc/cs0029",
    "CS0117": "https://learn.microsoft.com/en-us/dotnet/csharp/misc/cs0117",
    "CS0019": "https://learn.microsoft.com/en-us/dotnet/csharp/misc/cs0019",
    "CS0266": "https://learn.microsoft.com/en-us/dotnet/csharp/misc/cs0266",
    "CS0111": "https://learn.microsoft.com/en-us/dotnet/csharp/misc/cs0111",
    "CS0120": "https://learn.microsoft.com/en-us/dotnet/csharp/misc/cs0120",
}


def get_error_link(code: str) -> str:
    """Get documentation URL for error code"""
    if code in ERROR_DOCS:
        return ERROR_DOCS[code]
    return f"https://www.google.com/search?q=unity+{code}"


class CLIRenderer:
    def __init__(self, console: Console = None):
        self.console = console or Console()
        self.start_time = None

    def header(self, project_path: str, editor_version: str | None = None):
        project_name = Path(project_path).name
        version_text = f"Editor: Unity {editor_version}" if editor_version else "Editor: Detecting..."

        content = f"[bold cyan]🎮 Unity Test Agent[/]\n"
        content += f"[dim]Project:[/] {project_name}\n"
        content += f"[dim]{version_text}[/]"

        self.console.print(Panel(content, box=box.ROUNDED, border_style="cyan"))
        self.console.print()

    def step_start(self, step: int, total: int, message: str) -> Progress:
        self.start_time = time.time()
        progress = Progress(
            TextColumn(f"[bold blue]\\[{step}/{total}][/]"),
            SpinnerColumn("dots"),
            TextColumn(f"[yellow]{message}[/]"),
            console=self.console,
            transient=True
        )
        return progress

    def step_complete(self, step: int, total: int, message: str, success: bool = True):
        elapsed = time.time() - self.start_time if self.start_time else 0
        icon = "[green]✓[/]" if success else "[red]✗[/]"
        color = "green" if success else "red"
        self.console.print(f"[bold blue]\\[{step}/{total}][/] {icon} [{color}]{message}[/] [dim]({elapsed:.1f}s)[/]")

    def step_error(self, step: int, total: int, message: str):
        self.step_complete(step, total, message, success=False)

    def retry_status(self, retry_num: int, max_retries: int, test_count: int):
        """Show retry progress"""
        self.console.print(f"  [yellow]↻[/] Retry {retry_num}/{max_retries}: Re-running {test_count} failed tests...")

    def results_panel(self, results: TestResults):
        total = results.total
        passed = results.passed
        failed = results.failed

        if total == 0:
            self.console.print(Panel("[yellow]No tests found[/]", title="Results", box=box.ROUNDED))
            return

        pass_rate = (passed / total) * 100 if total > 0 else 0
        bar_width = 30
        filled = int((pass_rate / 100) * bar_width)

        bar = "[green]█[/]" * filled + "[red]░[/]" * (bar_width - filled)

        content = f"[bold]Total:[/] {total}  [green]Passed:[/] {passed}  [red]Failed:[/] {failed}\n"
        content += f"{bar}  [bold]{pass_rate:.1f}%[/] passed"

        border_color = "green" if failed == 0 else "red"
        self.console.print()
        self.console.print(Panel(content, title="[bold]Results[/]", box=box.ROUNDED, border_style=border_color))

    def failed_tests(self, results: TestResults, max_show: int = 5):
        if not results.failed_tests:
            return

        self.console.print()
        total_failed = len(results.failed_tests)
        showing = min(max_show, total_failed)

        self.console.print(f"[bold red]Failed Tests ({showing}/{total_failed}):[/]")

        for test in results.failed_tests[:max_show]:
            short_name = test.name.split(".")[-1] if "." in test.name else test.name
            self.console.print(f"  [red]✗[/] [bold]{short_name}[/]")
            if test.message:
                msg_lines = test.message.strip().split("\n")
                short_msg = msg_lines[0][:60] + "..." if len(msg_lines[0]) > 60 else msg_lines[0]
                self.console.print(f"    [dim]{short_msg}[/]")

        if total_failed > max_show:
            self.console.print(f"  [dim]... and {total_failed - max_show} more failed tests[/]")

    def compilation_errors(self, errors: list, max_show: int = 5):
        if not errors:
            return

        self.console.print()
        total = len(errors)
        showing = min(max_show, total)

        self.console.print(f"[bold red]Compilation Errors ({showing}/{total}):[/]")

        for err in errors[:max_show]:
            self.console.print(f"  [red]✗[/] [bold]{err.file}[/]:[cyan]{err.line}[/]")

            # Error code with clickable link
            link = get_error_link(err.code)
            self.console.print(f"    [link={link}][yellow]{err.code}[/][/link]: {err.message}")

            if err.count > 1:
                self.console.print(f"    [dim](repeated {err.count}x)[/]")

        if total > max_show:
            self.console.print(f"  [dim]... and {total - max_show} more errors[/]")

    def flaky_tests(self, flaky: list[FlakyTest], max_show: int = 5):
        """Show detected flaky tests"""
        if not flaky:
            return

        self.console.print()
        total = len(flaky)
        showing = min(max_show, total)

        self.console.print(f"[bold yellow]⚠ Flaky Tests Detected ({showing}/{total}):[/]")

        for ft in flaky[:max_show]:
            short_name = ft.name.split(".")[-1] if "." in ft.name else ft.name
            score = ft.flakiness_score * 100
            self.console.print(f"  [yellow]~[/] {short_name} [dim]({score:.0f}% flaky)[/]")

        if total > max_show:
            self.console.print(f"  [dim]... and {total - max_show} more flaky tests[/]")

    def diff_panel(self, diff: TestDiff):
        """Show test diff compared to previous run"""
        if diff is None:
            return

        self.console.print()

        delta = diff.pass_rate_delta
        delta_str = f"+{delta:.1f}%" if delta >= 0 else f"{delta:.1f}%"
        arrow = "↑" if delta >= 0 else "↓"
        delta_color = "green" if delta >= 0 else "red"

        lines = []
        lines.append(f"[bold]{arrow}[/] Pass Rate: {diff.pass_rate_before:.1f}% → {diff.pass_rate_after:.1f}% [{delta_color}]({delta_str})[/]")

        if diff.fixed:
            lines.append("")
            lines.append(f"[green]✓ Fixed ({len(diff.fixed)}):[/]")
            for name in diff.fixed[:3]:
                short = name.split(".")[-1] if "." in name else name
                lines.append(f"  [green]{short}[/]")
            if len(diff.fixed) > 3:
                lines.append(f"  [dim]... and {len(diff.fixed) - 3} more[/]")

        if diff.new_failures:
            lines.append("")
            lines.append(f"[red]✗ New Failures ({len(diff.new_failures)}):[/]")
            for name in diff.new_failures[:3]:
                short = name.split(".")[-1] if "." in name else name
                lines.append(f"  [red]{short}[/]")
            if len(diff.new_failures) > 3:
                lines.append(f"  [dim]... and {len(diff.new_failures) - 3} more[/]")

        if diff.still_failing:
            lines.append("")
            lines.append(f"[dim]⚠ Still Failing: {len(diff.still_failing)}[/]")

        border_color = "green" if not diff.new_failures else "red"
        content = "\n".join(lines)
        self.console.print(Panel(content, title="[bold]Diff (vs last run)[/]", box=box.ROUNDED, border_style=border_color))

    def performance_panel(self, metrics: PerformanceMetrics):
        """Show performance metrics"""
        if metrics is None:
            return

        self.console.print()

        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("Metric", style="dim")
        table.add_column("Time", justify="right")

        table.add_row("Editor Detection", f"{metrics.editor_detect_ms:.0f}ms")
        table.add_row("Compilation", f"{metrics.compile_ms:.0f}ms")
        table.add_row("Test Execution", f"{metrics.test_run_ms:.0f}ms")
        table.add_row("[bold]Total[/]", f"[bold]{metrics.total_ms:.0f}ms[/]")

        self.console.print(Panel(table, title="[bold]Performance[/]", box=box.ROUNDED, border_style="blue"))

    def trends_panel(self, pass_rates: list[float]):
        """Show ASCII trend chart"""
        if not pass_rates or len(pass_rates) < 2:
            return

        self.console.print()

        # Simple ASCII sparkline
        chars = "▁▂▃▄▅▆▇█"
        min_val = min(pass_rates)
        max_val = max(pass_rates)
        range_val = max_val - min_val if max_val != min_val else 1

        sparkline = ""
        for rate in pass_rates:
            idx = int((rate - min_val) / range_val * (len(chars) - 1))
            sparkline += chars[idx]

        latest = pass_rates[-1]
        trend = "↑" if len(pass_rates) > 1 and pass_rates[-1] > pass_rates[-2] else "↓"

        content = f"Pass Rate Trend (last {len(pass_rates)} runs):\n"
        content += f"[cyan]{sparkline}[/]\n"
        content += f"Latest: [bold]{latest:.1f}%[/] {trend}"

        self.console.print(Panel(content, title="[bold]Trends[/]", box=box.ROUNDED, border_style="blue"))

    def json_output(self, result: UnityResult):
        self.console.print()
        self.console.print(result.to_json())

    def final_status(self, success: bool):
        self.console.print()
        if success:
            self.console.print("[bold green]✓ All tests passed![/]")
        else:
            self.console.print("[bold red]✗ Tests failed or compilation errors[/]")

    def cache_hit(self, cache_type: str):
        """Show cache hit message"""
        self.console.print(f"  [dim]💾 Using cached {cache_type} results[/]")
