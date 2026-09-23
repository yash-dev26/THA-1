"""Planner.

Produces a structured, typed Plan *before* any tool executes, satisfying
the "visible planning" requirement. Uses the LLM to extract the subject
and produce plan step wording when available; falls back to a fixed
template plan (still fully typed) when no LLM credentials are configured,
so planning is deterministic and free to test.
"""

from __future__ import annotations

import re

from src.agent.llm import LLMClient
from src.models.plan import Plan, PlanStep, ToolName

_PLANNER_SYSTEM_PROMPT = """You are the planning module of MarketScout, a competitive \
intelligence research agent. Given a user's research goal, extract the subject company \
and produce a JSON object with this exact shape:

{
  "subject": "<company name>",
  "objective": "<one sentence objective>",
  "steps": [
    {"id": 1, "task": "<short task description>", "tool": "web_search"},
    {"id": 2, "task": "<short task description>", "tool": "web_search"},
    {"id": 3, "task": "<short task description>", "tool": "web_fetch"},
    {"id": 4, "task": "<short task description>", "tool": "internal"},
    {"id": 5, "task": "<short task description>", "tool": "calculator"},
    {"id": 6, "task": "<short task description>", "tool": "llm"}
  ]
}

Respond with ONLY the JSON object, no other text. The "tool" field must be one of: \
web_search, web_fetch, calculator, internal, llm."""


def _default_plan(subject: str) -> Plan:
    return Plan(
        objective=f"Analyze the competitive landscape for {subject}",
        steps=[
            PlanStep(id=1, task="Identify major competitors", tool=ToolName.WEB_SEARCH),
            PlanStep(id=2, task="Find recent developments per competitor", tool=ToolName.WEB_SEARCH),
            PlanStep(id=3, task="Fetch primary sources for evidence", tool=ToolName.WEB_FETCH),
            PlanStep(id=4, task="Validate extracted evidence", tool=ToolName.INTERNAL),
            PlanStep(id=5, task="Estimate illustrative pricing cost", tool=ToolName.CALCULATOR),
            PlanStep(id=6, task="Generate the competitive brief", tool=ToolName.LLM),
        ],
    )


_SENTENCE_STARTERS = {
    "analyze", "analyse", "compare", "research", "find", "identify",
    "investigate", "report", "summarize", "summarise", "look", "tell",
    "give", "show", "the", "a", "an", "please",
}


def _extract_subject_heuristic(goal: str) -> str:
    """Very small heuristic used only when no LLM is configured. Tries, in
    order: a possessive ("Stripe's competitive..."), a capitalized word
    after 'for'/'of', then the first capitalized token that isn't a common
    sentence-starting verb (so "Analyze Stripe's..." doesn't pick
    "Analyze")."""
    match = re.search(r"\b([A-Z][\w&.-]*)'s\b", goal)
    if match:
        return match.group(1)
    match = re.search(r"\bfor\s+([A-Z][\w&.-]*)", goal)
    if match:
        return match.group(1)
    match = re.search(r"\bof\s+([A-Z][\w&.-]*)", goal)
    if match:
        return match.group(1)
    for word in re.findall(r"\b[A-Z][\w&.-]{2,}\b", goal):
        if word.lower() not in _SENTENCE_STARTERS:
            return word
    return goal.split()[0]


class Planner:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    async def plan(self, goal: str) -> tuple[str, Plan]:
        """Returns (subject, plan)."""
        if self._llm.available:
            try:
                data = await self._llm.complete_json(_PLANNER_SYSTEM_PROMPT, goal)
                plan = Plan(objective=data["objective"], steps=data["steps"])
                return data["subject"], plan
            except Exception:
                # Deterministic fallback keeps the agent operational even if
                # the model returns malformed JSON — planning failures don't
                # get to crash the whole run.
                pass

        subject = _extract_subject_heuristic(goal)
        return subject, _default_plan(subject)
