"""Metrics computed against a single completed agent run (final AgentState)."""

from __future__ import annotations

from dataclasses import dataclass

from src.agent.state import AgentState


@dataclass
class ScenarioMetrics:
    goal: str
    planning_success: bool
    tool_success_rate: float
    recovery_success: bool
    citation_coverage: float
    final_schema_valid: bool

    def as_dict(self) -> dict:
        return {
            "goal": self.goal,
            "planning_success": self.planning_success,
            "tool_success_rate": round(self.tool_success_rate, 3),
            "recovery_success": self.recovery_success,
            "citation_coverage": round(self.citation_coverage, 3),
            "final_schema_valid": self.final_schema_valid,
        }


def compute_metrics(goal: str, state: AgentState) -> ScenarioMetrics:
    plan = state.get("plan")
    planning_success = bool(plan and len(plan.steps) > 0)

    failures = state.get("failures", [])
    recovered = [f for f in failures if f.recovered]
    # If there were failures, recovery succeeded only if every one of them
    # was marked recovered *and* the run still produced a final report.
    recovery_success = (
        True if not failures else (len(recovered) == len(failures) and state.get("final_report") is not None)
    )

    total_search_calls = max(len(state.get("search_results", [])), 1)
    tool_failures = len(failures)
    tool_success_rate = max(0.0, 1.0 - (tool_failures / (total_search_calls + tool_failures)))

    report = state.get("final_report")
    if report and report.evidence_table:
        cited = sum(1 for row in report.evidence_table if str(row.source_url).startswith("http"))
        citation_coverage = cited / len(report.evidence_table)
    else:
        citation_coverage = 0.0

    final_schema_valid = report is not None

    return ScenarioMetrics(
        goal=goal,
        planning_success=planning_success,
        tool_success_rate=tool_success_rate,
        recovery_success=recovery_success,
        citation_coverage=citation_coverage,
        final_schema_valid=final_schema_valid,
    )
