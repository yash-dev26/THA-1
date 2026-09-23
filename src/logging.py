"""Structured console logging/tracing.

Two responsibilities kept separate on purpose: `AgentLogger` renders
human-readable progress to the CLI (the transcript shown in the README),
while every event it prints is *also* backed by typed state (Plan,
ToolFailure, RecoveryDecision) that a test can assert on independently of
the printed text. The console output is a view, not the source of truth.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from src.models.plan import Plan


class AgentLogger:
    def __init__(self, console: Console | None = None, quiet: bool = False):
        self.console = console or Console()
        self.quiet = quiet

    def banner(self, title: str, subtitle: str) -> None:
        if self.quiet:
            return
        self.console.print(Panel.fit(f"[bold]{title}[/bold]\n{subtitle}", border_style="cyan"))

    def goal(self, goal: str) -> None:
        if self.quiet:
            return
        self.console.print(f"\n[bold]GOAL[/bold]\n{goal}\n")

    def plan(self, plan: Plan) -> None:
        if self.quiet:
            return
        self.console.print("[bold]PLAN[/bold]")
        for line in plan.summary_lines():
            self.console.print(f"  {line}")
        self.console.print()

    def step_header(self, step_num: int, total: int, description: str) -> None:
        if self.quiet:
            return
        self.console.print(f"[bold cyan]STEP {step_num} / {total}[/bold cyan] — {description}")

    def tool_call(self, tool: str, arg: str) -> None:
        if self.quiet:
            return
        self.console.print(f"  → {tool}({arg!r})")

    def tool_success(self, message: str) -> None:
        if self.quiet:
            return
        self.console.print(f"  [green]✓[/green] {message}")

    def tool_failure(self, error_type: str, message: str) -> None:
        if self.quiet:
            return
        self.console.print(f"  [yellow]⚠[/yellow] {error_type}: {message}")

    def recovery(self, action: str, success: bool) -> None:
        if self.quiet:
            return
        icon = "[green]✓[/green]" if success else "[red]✗[/red]"
        self.console.print(f"  [bold]RECOVERY[/bold] → {action} {icon}")

    def complete(self) -> None:
        if self.quiet:
            return
        self.console.print("\n[bold green]✓ Complete[/bold green]\n")
