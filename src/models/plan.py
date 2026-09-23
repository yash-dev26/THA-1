"""Typed planning models.

The planner produces a structured, inspectable plan *before* any tool is
executed. Nothing here is free text — every field is typed so the plan can
be validated, logged, and tested like any other piece of application state.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ToolName(str, Enum):
    WEB_SEARCH = "web_search"
    WEB_FETCH = "web_fetch"
    CALCULATOR = "calculator"
    INTERNAL = "internal"
    LLM = "llm"


class PlanStep(BaseModel):
    id: int
    task: str = Field(..., description="Human-readable description of the step's goal")
    tool: ToolName


class Plan(BaseModel):
    objective: str
    steps: list[PlanStep]

    def summary_lines(self) -> list[str]:
        """Actionable plan summary for logs/CLI. No chain-of-thought, just the plan."""
        return [f"{i}. {step.task}" for i, step in enumerate(self.steps, start=1)]
