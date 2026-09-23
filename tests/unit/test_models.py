from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.models.evidence import (
    Confidence,
    Evidence,
    SearchResult,
    SearchResults,
    WebDocument,
)
from src.models.plan import Plan, PlanStep, ToolName
from src.models.report import CompetitiveReport, CompetitorProfile


def test_plan_step_requires_valid_tool_name():
    with pytest.raises(ValidationError):
        PlanStep(id=1, task="do something", tool="not_a_real_tool")


def test_plan_summary_lines_are_numbered_and_readable():
    plan = Plan(
        objective="test",
        steps=[
            PlanStep(id=1, task="Identify competitors", tool=ToolName.WEB_SEARCH),
            PlanStep(id=2, task="Fetch sources", tool=ToolName.WEB_FETCH),
        ],
    )
    assert plan.summary_lines() == ["1. Identify competitors", "2. Fetch sources"]


def test_search_result_requires_valid_url():
    with pytest.raises(ValidationError):
        SearchResult(title="x", url="not-a-url", snippet="y", source="z")


def test_search_results_rejects_malformed_shape():
    # This is exactly the malformed-response shape used by failure injection.
    with pytest.raises(ValidationError):
        SearchResults(query="q", results=[{"headline": "x", "link": "https://example.com"}])


def test_evidence_is_only_constructible_from_a_document_not_a_snippet():
    doc = WebDocument(
        url="https://example.com/a",
        title="A",
        text="Some fetched page text.",
        fetched_at=datetime.now(UTC),
    )
    evidence = Evidence(
        claim="Some fetched page text.",
        competitor="Acme",
        source_url=doc.url,
        confidence=Confidence.MEDIUM,
        excerpt="Some fetched page text.",
    )
    assert evidence.source_url == doc.url


def test_report_to_markdown_includes_all_sections():
    report = CompetitiveReport(
        subject="Stripe",
        executive_summary="Summary text.",
        competitors=[
            CompetitorProfile(
                name="Adyen",
                focus="Enterprise payments",
                evidence_claims=["Claim one."],
                source_urls=["https://adyen.com"],
            )
        ],
        comparison_table=[],
        evidence_table=[],
    )
    md = report.to_markdown()
    assert "# Competitive Landscape: Stripe" in md
    assert "## Executive Summary" in md
    assert "### Adyen" in md
    assert "Claim one." in md
