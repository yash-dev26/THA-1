"""Explicit typed agent state.

Deliberately not a free-form dict. Every field the graph reads or writes
is declared here, which is what makes execution observable, loggable, and
testable — you can assert on `state["failures"]` in a test the same way
you'd assert on any other typed value.
"""

from __future__ import annotations

from typing import TypedDict

from src.models.evidence import Evidence, SearchResult, ToolFailure, WebDocument
from src.models.plan import Plan
from src.models.report import CompetitiveReport


class AgentState(TypedDict, total=False):
    goal: str
    subject: str
    competitors: list[str]

    plan: Plan
    current_step: int

    search_results: list[SearchResult]
    documents: list[WebDocument]
    evidence: list[Evidence]

    pricing_estimates: dict[str, str]

    failures: list[ToolFailure]
    retries: dict[str, int]

    final_report: CompetitiveReport | None
    error: str | None
