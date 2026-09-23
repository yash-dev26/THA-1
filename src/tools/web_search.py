"""web_search tool.

Architecture note: the *provider* (what actually calls out to Tavily, or
returns offline fixture JSON) is deliberately separated from the *tool*
(what validates the provider's raw response against `SearchResults` and
converts provider errors into typed `ToolError`s). This is the seam where
failure injection and offline/online switching both happen, without the
graph nodes needing to know which mode is active.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx
from pydantic import ValidationError

from src.config import FailureInjectionMode, Settings
from src.models.evidence import SearchResults
from src.tools.base import ToolError
from src.tools.fixtures import OFFLINE_SEARCH_FIXTURES


class SearchProvider(Protocol):
    async def raw_search(self, query: str) -> dict[str, Any]:
        ...


class OfflineFixtureSearchProvider:
    """Deterministic offline provider. Lets the whole agent run, and its
    tests pass, with zero external API keys — useful for grading without
    credentials, and for reproducible CI."""

    async def raw_search(self, query: str) -> dict[str, Any]:
        q = query.lower()
        for key, payload in OFFLINE_SEARCH_FIXTURES.items():
            if key in q:
                return payload
        # generic fallback so arbitrary queries still return *something* valid
        return {
            "results": [
                {
                    "title": f"Overview: {query}",
                    "url": "https://example.com/overview",
                    "snippet": f"General public information related to '{query}'.",
                    "source": "example.com",
                }
            ]
        }


class TavilySearchProvider:
    """Real provider backed by the Tavily search API."""

    def __init__(self, api_key: str, timeout: float = 15.0):
        self._api_key = api_key
        self._timeout = timeout

    async def raw_search(self, query: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": self._api_key, "query": query, "max_results": 5},
            )
            resp.raise_for_status()
            data = resp.json()
            # Normalize Tavily's schema into our provider-neutral shape.
            return {
                "results": [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                        "source": httpx.URL(r.get("url", "https://unknown")).host or "unknown",
                    }
                    for r in data.get("results", [])
                ]
            }


class WebSearchTool:
    name = "web_search"

    def __init__(self, settings: Settings, provider: SearchProvider | None = None, injection_budget: int = 1):
        self._settings = settings
        self._provider = provider or self._default_provider(settings)
        # Failure injection fires this many times, then the tool behaves
        # normally — this mirrors a real transient provider glitch (one bad
        # response, not a permanently broken API) so the recovery path has
        # something to actually succeed against, matching the "retry
        # succeeded" demo transcript in the design doc.
        self._injections_remaining = injection_budget

    @staticmethod
    def _default_provider(settings: Settings) -> SearchProvider:
        if settings.tavily_api_key:
            return TavilySearchProvider(settings.tavily_api_key, settings.http_timeout_seconds)
        return OfflineFixtureSearchProvider()

    async def execute(self, query: str) -> SearchResults:
        raw = await self._provider.raw_search(query)
        raw = self._maybe_inject_failure(raw)

        if raw.get("__rate_limited__"):
            raise ToolError("RATE_LIMIT", "Search provider returned HTTP 429")

        try:
            return SearchResults(query=query, results=raw["results"])
        except (ValidationError, KeyError) as exc:
            raise ToolError(
                "SCHEMA_ERROR", f"Search response failed schema validation: {exc}"
            ) from exc

    def _maybe_inject_failure(self, raw: dict[str, Any]) -> dict[str, Any]:
        mode = self._settings.failure_injection_mode
        if mode == FailureInjectionMode.NONE or self._injections_remaining <= 0:
            return raw

        if mode == FailureInjectionMode.MALFORMED_SEARCH_RESPONSE:
            self._injections_remaining -= 1
            # Realistic provider drift: field names changed upstream
            # (title -> headline, url -> link), no more "results" key.
            return {
                "items": [
                    {"headline": r.get("title", ""), "link": r.get("url", "")}
                    for r in raw.get("results", [])
                ]
            }
        if mode == FailureInjectionMode.RATE_LIMIT:
            self._injections_remaining -= 1
            return {"__rate_limited__": True}
        return raw
