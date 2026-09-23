"""Integration tests for the full graph. The network is always mocked here
(via the offline fixture providers that ship in src/tools/fixtures.py) —
these tests never make a real HTTP call, so they're fast and deterministic
in CI regardless of network access."""

from src.agent.graph import run_agent
from src.config import FailureInjectionMode, Settings
from src.logging import AgentLogger


async def test_normal_run_produces_a_grounded_report():
    settings = Settings()  # offline fixtures, no LLM — fully deterministic
    logger = AgentLogger(quiet=True)

    final_state = await run_agent(
        "Analyze Stripe's competitive landscape in developer payments", settings, logger
    )

    assert final_state["subject"] == "Stripe"
    assert len(final_state["competitors"]) >= 1
    assert final_state["final_report"] is not None

    report = final_state["final_report"]
    assert report.subject == "Stripe"
    assert len(report.competitors) == len(final_state["competitors"])
    # Every evidence row must carry a real source URL — no unsourced claims.
    for row in report.evidence_table:
        assert str(row.source_url).startswith("http")


async def test_calculator_is_actually_invoked_and_feeds_the_comparison_table():
    """The calculator tool must earn its place in the pipeline, not just
    exist. The offline Adyen/Paddle pricing fixtures each contain an
    explicit illustrative percentage-fee mention, so node_estimate_pricing
    should find them, call the calculator, and node_synthesize should
    render the results as a comparison row — using the calculator's
    numbers verbatim rather than asking the LLM to compute them."""
    settings = Settings()
    logger = AgentLogger(quiet=True)

    final_state = await run_agent("Analyze Stripe's competitive landscape", settings, logger)

    assert final_state["pricing_estimates"], "expected at least one competitor to get a pricing estimate"
    assert "Adyen" in final_state["pricing_estimates"]
    assert "$2,900" in final_state["pricing_estimates"]["Adyen"]

    report = final_state["final_report"]
    pricing_rows = [r for r in report.comparison_table if "cost" in r.dimension.lower()]
    assert len(pricing_rows) == 1
    assert "$2,900" in pricing_rows[0].values.get("Adyen", "")


async def test_malformed_search_response_triggers_recovery_and_still_completes():
    """This is the core robustness demonstration: the search provider
    returns a malformed response, Pydantic validation rejects it, the
    RecoveryPolicy retries, the retry succeeds, and the run completes with
    a valid final report — exactly the failure -> recovery -> success path
    required by the brief."""
    settings = Settings(failure_injection_mode=FailureInjectionMode.MALFORMED_SEARCH_RESPONSE)
    logger = AgentLogger(quiet=True)

    final_state = await run_agent("Analyze Stripe's competitive landscape", settings, logger)

    assert len(final_state["failures"]) >= 1
    failure = final_state["failures"][0]
    assert failure.error_type.value == "SCHEMA_ERROR"
    assert failure.recovered is True

    # Despite the induced failure, the run still reaches a valid report.
    assert final_state["final_report"] is not None
    assert final_state["final_report"].subject == "Stripe"


async def test_fetch_timeout_injection_is_handled_without_crashing_the_run():
    settings = Settings(failure_injection_mode=FailureInjectionMode.FETCH_TIMEOUT)
    logger = AgentLogger(quiet=True)

    final_state = await run_agent("Analyze Adyen's competitive landscape", settings, logger)

    assert final_state["final_report"] is not None
    fetch_failures = [f for f in final_state["failures"] if f.tool == "web_fetch"]
    assert len(fetch_failures) >= 1
    assert fetch_failures[0].error_type.value == "TIMEOUT"


async def test_ambiguous_goal_still_produces_a_report_via_fallback_competitors():
    """No named company in the goal -> the heuristic subject extractor
    falls back to the first content word, and competitor discovery falls
    back to placeholder competitors rather than crashing the graph."""
    settings = Settings()
    logger = AgentLogger(quiet=True)

    final_state = await run_agent("competitive landscape review", settings, logger)

    assert final_state["final_report"] is not None
    assert len(final_state["competitors"]) >= 1
