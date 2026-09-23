"""LangGraph state machine wiring.

This is the controlled state machine described in the design doc: an
explicit sequence of nodes (plan -> identify competitors -> research ->
fetch -> validate -> synthesize) rather than an unrestricted agent loop
deciding its own control flow. Recovery is handled deterministically
*inside* the search/fetch nodes (see nodes.py + recovery.py) and is fully
visible in the logged transcript and in `state["failures"]` /
`state["retries"]`, which is what tests assert against.
"""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, StateGraph

from src.agent.llm import LLMClient
from src.agent.nodes import (
    node_estimate_pricing,
    node_fetch_evidence,
    node_identify_competitors,
    node_plan,
    node_research_developments,
    node_synthesize,
    node_validate_evidence,
)
from src.agent.planner import Planner
from src.agent.recovery import RecoveryPolicy
from src.agent.state import AgentState
from src.config import Settings
from src.logging import AgentLogger
from src.tools.calculator import CalculatorTool
from src.tools.web_fetch import WebFetchTool
from src.tools.web_search import WebSearchTool


def build_graph(settings: Settings, logger: AgentLogger):
    llm = LLMClient(settings)
    planner = Planner(llm)
    search_tool = WebSearchTool(settings)
    fetch_tool = WebFetchTool(settings)
    calculator = CalculatorTool()
    recovery = RecoveryPolicy(max_retries=max(settings.max_search_retries, settings.max_fetch_retries))

    graph = StateGraph(AgentState)

    graph.add_node("plan", partial(node_plan, planner=planner, logger=logger))
    graph.add_node(
        "identify_competitors",
        partial(node_identify_competitors, search_tool=search_tool, recovery=recovery, logger=logger),
    )
    graph.add_node(
        "research_developments",
        partial(node_research_developments, search_tool=search_tool, recovery=recovery, logger=logger),
    )
    graph.add_node(
        "fetch_evidence",
        partial(node_fetch_evidence, fetch_tool=fetch_tool, recovery=recovery, logger=logger),
    )
    graph.add_node("validate_evidence", partial(node_validate_evidence, logger=logger))
    graph.add_node(
        "estimate_pricing", partial(node_estimate_pricing, calculator=calculator, logger=logger)
    )
    graph.add_node("synthesize", partial(node_synthesize, llm=llm, logger=logger))

    graph.set_entry_point("plan")
    graph.add_edge("plan", "identify_competitors")
    graph.add_edge("identify_competitors", "research_developments")
    graph.add_edge("research_developments", "fetch_evidence")
    graph.add_edge("fetch_evidence", "validate_evidence")
    graph.add_edge("validate_evidence", "estimate_pricing")
    graph.add_edge("estimate_pricing", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


async def run_agent(goal: str, settings: Settings, logger: AgentLogger) -> AgentState:
    app = build_graph(settings, logger)
    logger.banner("MarketScout", "Competitive Intelligence Agent")
    logger.goal(goal)
    initial_state: AgentState = {"goal": goal}
    final_state = await app.ainvoke(initial_state)
    logger.complete()
    return final_state
