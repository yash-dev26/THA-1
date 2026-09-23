"""Small reproducible evaluation harness.

Usage:
    python -m evals.run_evals
    python -m evals.run_evals --inject-failure malformed_search_response

Runs every scenario in evals/datasets/scenarios.json against the real
agent graph (offline fixtures by default, so this needs no API keys) and
prints a metrics table. Not an elaborate benchmark — just enough to make
the run reproducible and give a single glance at planning/tool/recovery
health across scenarios.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.agent.graph import run_agent
from src.config import FailureInjectionMode, Settings
from src.logging import AgentLogger
from evals.metrics import compute_metrics

SCENARIOS_PATH = Path(__file__).parent / "datasets" / "scenarios.json"


async def run_all(inject_failure: str | None) -> list[dict]:
    scenarios = json.loads(SCENARIOS_PATH.read_text())
    settings = Settings()
    if inject_failure:
        settings.failure_injection_mode = FailureInjectionMode(inject_failure)

    logger = AgentLogger(quiet=True)
    results = []
    for scenario in scenarios:
        final_state = await run_agent(scenario["goal"], settings, logger)
        metrics = compute_metrics(scenario["goal"], final_state)
        results.append(metrics.as_dict())
    return results


def render(results: list[dict]) -> None:
    console = Console()
    table = Table(title="MarketScout Evaluation Results")
    for col in ["goal", "planning_success", "tool_success_rate", "recovery_success",
                "citation_coverage", "final_schema_valid"]:
        table.add_column(col)
    for r in results:
        table.add_row(
            r["goal"][:40] + ("…" if len(r["goal"]) > 40 else ""),
            str(r["planning_success"]),
            str(r["tool_success_rate"]),
            str(r["recovery_success"]),
            str(r["citation_coverage"]),
            str(r["final_schema_valid"]),
        )
    console.print(table)

    n = len(results)
    console.print(
        f"\nplanning_success: {sum(r['planning_success'] for r in results)}/{n}   "
        f"recovery_success: {sum(r['recovery_success'] for r in results)}/{n}   "
        f"final_schema_valid: {sum(r['final_schema_valid'] for r in results)}/{n}   "
        f"avg_citation_coverage: {sum(r['citation_coverage'] for r in results) / n:.2f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inject-failure", choices=[m.value for m in FailureInjectionMode], default=None
    )
    args = parser.parse_args()
    results = asyncio.run(run_all(args.inject_failure))
    render(results)


if __name__ == "__main__":
    main()
