"""LangGraph node implementations.

Each node is a plain async function: `(state, deps) -> partial state update`.
Deps (tools, recovery policy, LLM client, logger) are bound via functools.partial
when the graph is built (see graph.py), so nodes stay pure and easy to unit test
by calling them directly with a fake state and fake tools.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import Any

from src.agent.llm import LLMClient
from src.agent.recovery import RecoveryAction, RecoveryPolicy
from src.agent.state import AgentState
from src.logging import AgentLogger
from src.models.evidence import (
    Confidence,
    Evidence,
    FailureType,
    ToolFailure,
    WebDocument,
)
from src.models.report import (
    ComparisonRow,
    CompetitiveReport,
    CompetitorProfile,
    EvidenceRow,
)
from src.tools.base import ToolError
from src.tools.calculator import CalculatorTool
from src.tools.web_fetch import WebFetchTool
from src.tools.web_search import WebSearchTool

MAX_COMPETITORS = 3

# Illustrative-only transaction volume used to make a flat-rate percentage
# concrete and comparable. Not a claim about any real merchant's volume —
# see docs/assumptions.md.
ILLUSTRATIVE_VOLUME_USD = 100_000

_PERCENT_FEE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _infer_owner(text: str, competitors: list[str], subject: str) -> str:
    """Attributes a fetched document to whichever known competitor (or the
    subject) it's most plausibly about, using simple first-word name
    matching. Shared by evidence validation and pricing estimation so both
    steps attribute documents to competitors the same way."""
    candidates = competitors + [subject]
    return next((c for c in candidates if c.lower().split()[0] in text.lower()), subject)


async def node_plan(state: AgentState, *, planner, logger: AgentLogger) -> dict[str, Any]:
    subject, plan = await planner.plan(state["goal"])
    logger.plan(plan)
    return {
        "subject": subject,
        "plan": plan,
        "current_step": 0,
        "failures": [],
        "retries": {},
        "search_results": [],
        "documents": [],
        "evidence": [],
        "pricing_estimates": {},
        "final_report": None,
        "error": None,
    }


async def _search_with_recovery(
    query: str,
    *,
    search_tool: WebSearchTool,
    recovery: RecoveryPolicy,
    logger: AgentLogger,
    retries: dict[str, int],
    failures: list[ToolFailure],
    step_id: int,
):
    """Runs a single search query with the deterministic recovery loop.
    Returns SearchResults on success, or None if all recovery attempts
    (including the final fallback) failed."""
    attempt = 0
    alt_query = query
    while True:
        attempt += 1
        try:
            logger.tool_call("web_search", alt_query)
            result = await search_tool.execute(alt_query)
            logger.tool_success(f"{len(result.results)} results returned")
            return result
        except ToolError as exc:
            error_type = FailureType(exc.error_type) if exc.error_type in FailureType.__members__ else FailureType.UNKNOWN
            failure = ToolFailure(
                tool="web_search",
                step_id=step_id,
                error_type=error_type,
                message=exc.message,
                occurred_at=datetime.now(UTC),
            )
            decision = recovery.decide(error_type, attempt)
            logger.tool_failure(exc.error_type, exc.message)

            key = f"web_search:{step_id}"
            retries[key] = retries.get(key, 0) + 1

            if decision.action == RecoveryAction.GIVE_UP:
                failures.append(failure)
                logger.recovery("give_up", success=False)
                return None

            if decision.action == RecoveryAction.FALLBACK_ALTERNATE_QUERY:
                failure.recovered = True
                failure.recovery_action = "fallback_alternate_query"
                failures.append(failure)
                logger.recovery("fallback_alternate_query", success=True)
                # Alternate strategy: broaden the query and try once more,
                # outside the normal retry budget. If this also fails we give up.
                try:
                    alt_query = query.split(" recent")[0]
                    result = await search_tool.execute(alt_query)
                    logger.tool_success(f"(fallback) {len(result.results)} results returned")
                    return result
                except ToolError:
                    return None

            # RETRY or RETRY_WITH_BACKOFF
            failure.recovered = True
            failure.recovery_action = decision.action.value
            failures.append(failure)
            if decision.backoff_seconds:
                await asyncio.sleep(decision.backoff_seconds if decision.backoff_seconds < 1 else 0)
            logger.recovery(decision.action.value, success=True)
            # loop again and retry the (same) query


async def node_identify_competitors(
    state: AgentState, *, search_tool: WebSearchTool, recovery: RecoveryPolicy, logger: AgentLogger
) -> dict[str, Any]:
    logger.step_header(1, len(state["plan"].steps), "Identify major competitors")
    retries = dict(state.get("retries", {}))
    failures = list(state.get("failures", []))

    query = f"{state['subject']} competitors"
    result = await _search_with_recovery(
        query,
        search_tool=search_tool,
        recovery=recovery,
        logger=logger,
        retries=retries,
        failures=failures,
        step_id=1,
    )

    competitors: list[str] = []
    search_results = list(state.get("search_results", []))
    if result:
        search_results.extend(result.results)
        for r in result.results[:MAX_COMPETITORS]:
            name = r.title.split(" - ")[0].split(" - a ")[0].strip()
            if name.lower() != state["subject"].lower():
                competitors.append(name)

    if not competitors:
        # Deterministic last-resort fallback so the run can still finish
        # end-to-end even if every recovery path failed.
        competitors = ["Competitor A", "Competitor B"]

    return {
        "competitors": competitors[:MAX_COMPETITORS],
        "search_results": search_results,
        "retries": retries,
        "failures": failures,
        "current_step": 1,
    }


async def node_research_developments(
    state: AgentState, *, search_tool: WebSearchTool, recovery: RecoveryPolicy, logger: AgentLogger
) -> dict[str, Any]:
    logger.step_header(2, len(state["plan"].steps), "Research recent developments per competitor")
    retries = dict(state.get("retries", {}))
    failures = list(state.get("failures", []))
    search_results = list(state.get("search_results", []))

    for competitor in state["competitors"]:
        query = f"{competitor} recent product developments pricing"
        result = await _search_with_recovery(
            query,
            search_tool=search_tool,
            recovery=recovery,
            logger=logger,
            retries=retries,
            failures=failures,
            step_id=2,
        )
        if result:
            search_results.extend(result.results)

    return {"search_results": search_results, "retries": retries, "failures": failures, "current_step": 2}


async def node_fetch_evidence(
    state: AgentState, *, fetch_tool: WebFetchTool, recovery: RecoveryPolicy, logger: AgentLogger
) -> dict[str, Any]:
    logger.step_header(3, len(state["plan"].steps), "Fetch primary sources")
    retries = dict(state.get("retries", {}))
    failures = list(state.get("failures", []))
    documents: list[WebDocument] = []

    # Fetch each *unique* candidate URL surfaced by search — never treat the
    # search snippet itself as evidence.
    seen_urls: set[str] = set()
    for result in state.get("search_results", []):
        url = str(result.url)
        if url in seen_urls:
            continue
        seen_urls.add(url)

        attempt = 0
        while True:
            attempt += 1
            try:
                logger.tool_call("web_fetch", url)
                doc = await fetch_tool.execute(url)
                logger.tool_success(f"{len(doc.text)} characters extracted")
                documents.append(doc)
                break
            except ToolError as exc:
                error_type = (
                    FailureType(exc.error_type) if exc.error_type in FailureType.__members__ else FailureType.UNKNOWN
                )
                logger.tool_failure(exc.error_type, exc.message)
                decision = recovery.decide(error_type, attempt)
                key = f"web_fetch:{url}"
                retries[key] = retries.get(key, 0) + 1
                failures.append(
                    ToolFailure(
                        tool="web_fetch",
                        error_type=error_type,
                        message=exc.message,
                        occurred_at=datetime.now(UTC),
                        recovered=decision.action != RecoveryAction.GIVE_UP,
                        recovery_action=decision.action.value,
                    )
                )
                if decision.action in (RecoveryAction.GIVE_UP, RecoveryAction.FALLBACK_ALTERNATE_QUERY):
                    logger.recovery(decision.action.value, success=False)
                    break  # skip this URL, move on
                logger.recovery(decision.action.value, success=True)
                # retry loop continues

    return {"documents": documents, "retries": retries, "failures": failures, "current_step": 3}


async def node_validate_evidence(state: AgentState, *, logger: AgentLogger) -> dict[str, Any]:
    logger.step_header(4, len(state["plan"].steps), "Validate extracted evidence")
    evidence: list[Evidence] = []

    for doc in state.get("documents", []):
        owner = _infer_owner(doc.text, state["competitors"], state["subject"])

        sentences = [s.strip() for s in doc.text.replace("\n", " ").split(". ") if s.strip()]
        claim_sentence = sentences[0] if sentences else doc.text[:160]

        evidence.append(
            Evidence(
                claim=claim_sentence.rstrip(".") + ".",
                competitor=owner,
                source_url=doc.url,
                confidence=Confidence.MEDIUM if len(sentences) > 1 else Confidence.LOW,
                excerpt=claim_sentence[:200],
            )
        )

    logger.tool_success(f"{len(evidence)} claims validated")
    return {"evidence": evidence, "current_step": 4}


async def node_estimate_pricing(
    state: AgentState, *, calculator: CalculatorTool, logger: AgentLogger
) -> dict[str, Any]:
    """Where the calculator tool actually earns its place in the pipeline:
    scans fetched documents for an explicit percentage-based fee mention
    (e.g. "approximately 2.9% of transaction volume") and, when found, asks
    the calculator — not the LLM — to compute an illustrative cost on a
    fixed representative volume. This keeps numeric computation out of the
    model's hands, consistent with how RecoveryPolicy keeps infrastructure
    decisions out of the model's hands: the LLM decides what to research,
    the application computes exact numbers. See docs/assumptions.md for why
    the volume and any percentages are illustrative, not verified pricing.
    """
    logger.step_header(5, len(state["plan"].steps), "Estimate illustrative pricing cost")
    estimates: dict[str, str] = {}

    for doc in state.get("documents", []):
        match = _PERCENT_FEE_RE.search(doc.text)
        if not match:
            continue
        owner = _infer_owner(doc.text, state["competitors"], state["subject"])
        if owner in estimates:
            continue  # already estimated for this competitor from an earlier document

        pct = float(match.group(1))
        expression = f"{ILLUSTRATIVE_VOLUME_USD} * {pct} / 100"
        try:
            logger.tool_call("calculator", expression)
            cost = await calculator.execute(expression)
            logger.tool_success(f"${cost:,.2f} on ${ILLUSTRATIVE_VOLUME_USD:,} illustrative volume")
            estimates[owner] = (
                f"~${cost:,.0f} per ${ILLUSTRATIVE_VOLUME_USD:,} processed "
                f"(illustrative, based on a {pct:g}% rate mentioned in sources)"
            )
        except ToolError as exc:
            logger.tool_failure(exc.error_type, exc.message)

    if not estimates:
        logger.tool_success("No explicit percentage-fee mentions found in fetched sources")

    return {"pricing_estimates": estimates, "current_step": 5}


_SYNTHESIS_SYSTEM_PROMPT = """You are the synthesis module of MarketScout. Given a subject \
company, a list of competitors, and a list of evidence claims (each tied to a source URL), \
produce a JSON object with this exact shape:

{
  "executive_summary": "<2-4 sentence summary>",
  "competitors": [
    {"name": "<competitor>", "focus": "<one phrase>", "evidence_claims": ["<claim>", ...], "source_urls": ["<url>", ...]}
  ],
  "comparison_table": [
    {"dimension": "Target market", "values": {"<competitor>": "<value>", ...}},
    {"dimension": "Pricing model", "values": {"<competitor>": "<value>", ...}},
    {"dimension": "Developer tooling", "values": {"<competitor>": "<value>", ...}}
  ]
}

Base every claim ONLY on the evidence provided. Do not invent facts not present in the \
evidence. Respond with ONLY the JSON object."""


async def node_synthesize(state: AgentState, *, llm: LLMClient, logger: AgentLogger) -> dict[str, Any]:
    logger.step_header(6, len(state["plan"].steps), "Generate competitive brief")
    subject = state["subject"]
    competitors = state["competitors"]
    evidence = state.get("evidence", [])
    pricing_estimates = state.get("pricing_estimates", {})

    report: CompetitiveReport | None = None
    if llm.available:
        try:
            prompt = (
                f"Subject: {subject}\nCompetitors: {', '.join(competitors)}\n\nEvidence:\n"
                + "\n".join(f"- [{e.competitor}] {e.claim} (source: {e.source_url})" for e in evidence)
            )
            data = await llm.complete_json(_SYNTHESIS_SYSTEM_PROMPT, prompt)
            comparison_table = [ComparisonRow(**r) for r in data["comparison_table"]]
            comparison_table.append(_pricing_comparison_row(competitors, pricing_estimates))
            report = CompetitiveReport(
                subject=subject,
                executive_summary=data["executive_summary"],
                competitors=[CompetitorProfile(**c) for c in data["competitors"]],
                comparison_table=comparison_table,
                evidence_table=[
                    EvidenceRow(claim=e.claim, source_url=e.source_url, confidence=e.confidence)
                    for e in evidence
                ],
            )
        except Exception:
            report = None  # fall through to deterministic synthesis below

    if report is None:
        report = _deterministic_synthesis(subject, competitors, evidence, pricing_estimates)

    logger.tool_success("Report synthesized")
    return {"final_report": report, "current_step": 6}


def _pricing_comparison_row(competitors: list[str], pricing_estimates: dict[str, str]) -> ComparisonRow:
    """Built directly from the calculator's output, not asked of the LLM —
    the numbers are computed by node_estimate_pricing, this just renders
    them into the report's comparison table."""
    return ComparisonRow(
        dimension=f"Illustrative cost per ${ILLUSTRATIVE_VOLUME_USD:,} processed",
        values={c: pricing_estimates.get(c, "n/a (no rate % found in sources)") for c in competitors},
    )


def _deterministic_synthesis(
    subject: str,
    competitors: list[str],
    evidence: list[Evidence],
    pricing_estimates: dict[str, str] | None = None,
) -> CompetitiveReport:
    """Template-based synthesis used when no LLM is configured. Still fully
    evidence-grounded — it just doesn't paraphrase with a model."""
    pricing_estimates = pricing_estimates or {}
    profiles = []
    for comp in competitors:
        comp_evidence = [e for e in evidence if e.competitor == comp]
        profiles.append(
            CompetitorProfile(
                name=comp,
                focus=comp_evidence[0].claim[:80] if comp_evidence else "No evidence gathered",
                evidence_claims=[e.claim for e in comp_evidence] or ["No claims validated"],
                source_urls=[e.source_url for e in comp_evidence] or [],
            )
        )

    summary = (
        f"{subject} operates in a competitive market alongside {', '.join(competitors)}. "
        f"{len(evidence)} evidence-backed claims were gathered from public sources; "
        f"see the comparison and evidence tables below for sourced detail."
    )

    comparison_table = [
        ComparisonRow(
            dimension="Evidence claims gathered",
            values={c: str(len([e for e in evidence if e.competitor == c])) for c in competitors},
        ),
        _pricing_comparison_row(competitors, pricing_estimates),
    ]

    evidence_table = [
        EvidenceRow(claim=e.claim, source_url=e.source_url, confidence=e.confidence) for e in evidence
    ]

    return CompetitiveReport(
        subject=subject,
        executive_summary=summary,
        competitors=profiles,
        comparison_table=comparison_table,
        evidence_table=evidence_table,
    )
