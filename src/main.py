"""CLI entrypoint.

    python -m src.main --goal "Analyze Stripe's competitive landscape"
    python -m src.main --goal "..." --inject-failure malformed_search_response
    python -m src.main --goal "..." --out report.md
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console

from src.agent.graph import run_agent
from src.config import FailureInjectionMode, Settings
from src.logging import AgentLogger


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MarketScout — Competitive Intelligence Agent")
    parser.add_argument("--goal", required=True, help="Natural-language research goal")
    parser.add_argument(
        "--inject-failure",
        choices=[m.value for m in FailureInjectionMode],
        default=None,
        help="Deliberately induce a specific tool failure to demonstrate recovery",
    )
    parser.add_argument("--out", default=None, help="Write the final report markdown to this path")
    parser.add_argument("--quiet", action="store_true", help="Suppress step-by-step trace output")
    return parser.parse_args(argv)


async def _main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.from_env()
    if args.inject_failure:
        settings.failure_injection_mode = FailureInjectionMode(args.inject_failure)

    logger = AgentLogger(Console(), quiet=args.quiet)
    final_state = await run_agent(args.goal, settings, logger)

    report = final_state.get("final_report")
    if report is None:
        logger.console.print("[red]No report was generated.[/red]")
        return 1

    markdown = report.to_markdown()
    if not args.quiet:
        logger.console.print(markdown)

    if args.out:
        with open(args.out, "w") as f:
            f.write(markdown)
        logger.console.print(f"[bold]Report written to {args.out}[/bold]")

    failures = final_state.get("failures", [])
    if failures and not args.quiet:
        logger.console.print(f"[dim]{len(failures)} tool failure(s) encountered and handled during this run.[/dim]")

    return 0


def main() -> None:
    sys.exit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
