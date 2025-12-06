"""Rich-based interactive CLI for Unity Test Agent"""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich import box

from .models import UnityResult, TestResults, FailedTest
from .trends import TrendsManager
from .cli import CLIRenderer


class InteractiveCLI:
    def __init__(
        self,
        result: UnityResult,
        project_path: str,
        editor_path: str,
        config=None
    ):
        self.console = Console()
        self.result = result
        self.project_path = project_path
        self.editor_path = editor_path
        self.config = config
        self.cli = CLIRenderer(self.console)
        self.trends_manager = TrendsManager(project_path) if project_path else None
        self.show_trends = False

    def run(self):
        """Main interactive loop"""
        while True:
            self._clear_and_render()
            action = self._show_menu()

            if action == "q":
                break
            elif action == "d":
                self._show_test_detail()
            elif action == "r":
                self._retry_failed()
            elif action == "t":
                self.show_trends = not self.show_trends
            elif action == "a":
                self._show_all_failed()

    def _clear_and_render(self):
        """Clear screen and render current state"""
        self.console.clear()
        self._render_header()
        self._render_results()

        if self.show_trends:
            self._render_trends()

    def _render_header(self):
        """Render header"""
        from pathlib import Path
        project_name = Path(self.project_path).name

        content = f"[bold cyan]🎮 Unity Test Agent[/] [dim](Interactive Mode)[/]\n"
        content += f"[dim]Project:[/] {project_name}"

        self.console.print(Panel(content, box=box.ROUNDED, border_style="cyan"))
        self.console.print()

    def _render_results(self):
        """Render test results summary"""
        if not self.result or not self.result.test_results:
            self.console.print("[yellow]No test results available[/]")
            return

        results = self.result.test_results
        self.cli.results_panel(results)

        if results.failed_tests:
            self._render_failed_table(results.failed_tests)

        if self.result.flaky_tests:
            self.cli.flaky_tests(self.result.flaky_tests)

    def _render_failed_table(self, failed_tests: list[FailedTest]):
        """Render failed tests as numbered table"""
        self.console.print()

        table = Table(
            title=f"[bold red]Failed Tests ({len(failed_tests)})[/]",
            box=box.ROUNDED,
            border_style="red"
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Test Name", style="bold")
        table.add_column("Error", style="dim", max_width=50)

        for i, test in enumerate(failed_tests[:20], 1):
            short_name = test.name.split(".")[-1] if "." in test.name else test.name
            short_msg = ""
            if test.message:
                lines = test.message.strip().split("\n")
                short_msg = lines[0][:50] + "..." if len(lines[0]) > 50 else lines[0]

            table.add_row(str(i), short_name, short_msg)

        if len(failed_tests) > 20:
            table.add_row("...", f"[dim]+{len(failed_tests) - 20} more[/]", "")

        self.console.print(table)

    def _render_trends(self):
        """Render trends panel"""
        if not self.trends_manager:
            return

        pass_rates = self.trends_manager.get_pass_rate_trend(limit=10)
        if pass_rates:
            self.cli.trends_panel(pass_rates)

    def _show_menu(self) -> str:
        """Show action menu and get user choice"""
        self.console.print()

        has_failed = self.result and self.result.test_results and self.result.test_results.failed_tests
        trends_status = "[green]ON[/]" if self.show_trends else "[dim]OFF[/]"

        options = []
        options.append("[d] Detail  ")
        if has_failed:
            options.append("[r] Retry   ")
        options.append(f"[t] Trends {trends_status}  ")
        if has_failed:
            options.append("[a] All     ")
        options.append("[q] Quit")

        self.console.print(Panel("".join(options), box=box.ROUNDED, border_style="blue"))

        choice = Prompt.ask(
            "[bold]Action[/]",
            choices=["d", "r", "t", "a", "q"] if has_failed else ["d", "t", "q"],
            default="q"
        )
        return choice

    def _show_test_detail(self):
        """Show detailed info for a specific test"""
        if not self.result or not self.result.test_results:
            return

        failed = self.result.test_results.failed_tests
        if not failed:
            self.console.print("[yellow]No failed tests[/]")
            Prompt.ask("[dim]Press Enter to continue[/]")
            return

        max_idx = min(len(failed), 20)
        idx = IntPrompt.ask(
            f"[bold]Test number (1-{max_idx})[/]",
            default=1
        )

        if idx < 1 or idx > max_idx:
            self.console.print("[red]Invalid number[/]")
            Prompt.ask("[dim]Press Enter to continue[/]")
            return

        test = failed[idx - 1]
        self._render_test_detail(test)
        Prompt.ask("[dim]Press Enter to continue[/]")

    def _render_test_detail(self, test: FailedTest):
        """Render detailed test information"""
        self.console.clear()

        short_name = test.name.split(".")[-1] if "." in test.name else test.name

        self.console.print(Panel(
            f"[bold]{short_name}[/]\n[dim]{test.name}[/]",
            title="[bold]Test Detail[/]",
            box=box.ROUNDED,
            border_style="yellow"
        ))

        self.console.print()
        self.console.print("[bold]Error Message:[/]")
        self.console.print(Panel(
            test.message or "[dim]No message[/]",
            box=box.SIMPLE,
            border_style="red"
        ))

        if test.stack_trace:
            self.console.print()
            self.console.print("[bold]Stack Trace:[/]")
            self.console.print(Panel(
                test.stack_trace,
                box=box.SIMPLE,
                border_style="dim"
            ))

    def _show_all_failed(self):
        """Show all failed tests with full details"""
        if not self.result or not self.result.test_results:
            return

        failed = self.result.test_results.failed_tests
        if not failed:
            return

        self.console.clear()
        self.console.print(f"[bold red]All Failed Tests ({len(failed)})[/]\n")

        for i, test in enumerate(failed, 1):
            short_name = test.name.split(".")[-1] if "." in test.name else test.name
            self.console.print(f"[bold]{i}. {short_name}[/]")
            self.console.print(f"   [dim]{test.name}[/]")
            if test.message:
                msg_lines = test.message.strip().split("\n")
                for line in msg_lines[:3]:
                    self.console.print(f"   [red]{line}[/]")
            self.console.print()

        Prompt.ask("[dim]Press Enter to continue[/]")

    def _retry_failed(self):
        """Retry failed tests"""
        if not self.result or not self.result.test_results:
            return

        failed = self.result.test_results.failed_tests
        if not failed:
            self.console.print("[yellow]No failed tests to retry[/]")
            Prompt.ask("[dim]Press Enter to continue[/]")
            return

        if not Confirm.ask(f"[bold]Retry {len(failed)} failed tests?[/]", default=True):
            return

        self.console.print()
        self.console.print("[yellow]⟳ Retrying failed tests...[/]")

        from .retry import run_with_retry

        def on_retry(retry_num, tests):
            self.console.print(f"  [dim]Retry {retry_num}: {len(tests)} tests[/]")

        retries = 3
        if self.config and hasattr(self.config, 'test'):
            retries = self.config.test.retries or 3

        new_results, flaky = run_with_retry(
            self.editor_path,
            self.project_path,
            self.result.test_results,
            max_retries=retries,
            platform=self.config.test.platform if self.config else "EditMode",
            on_retry=on_retry
        )

        self.result.test_results = new_results
        if flaky:
            self.result.flaky_tests = (self.result.flaky_tests or []) + flaky

        self.console.print()
        if new_results.failed < len(failed):
            fixed = len(failed) - new_results.failed
            self.console.print(f"[green]✓ {fixed} tests fixed on retry[/]")
        else:
            self.console.print("[red]✗ All tests still failing[/]")

        Prompt.ask("[dim]Press Enter to continue[/]")


def run_interactive(result: UnityResult, project_path: str, editor_path: str, config=None):
    """Launch interactive CLI"""
    cli = InteractiveCLI(result, project_path, editor_path, config)
    cli.run()
