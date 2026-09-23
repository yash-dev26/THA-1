"""web_fetch tool.

This is the tool that turns a candidate URL (found via web_search) into an
actual fetched document. Evidence is only ever built from `WebDocument`,
never from a `SearchResult` snippet — that distinction is enforced by the
type system in src/models/evidence.py, not just by convention.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

import httpx

from src.config import FailureInjectionMode, Settings
from src.models.evidence import WebDocument
from src.tools.base import ToolError
from src.tools.fixtures import OFFLINE_FETCH_FIXTURES


class FetchProvider(Protocol):
    async def raw_fetch(self, url: str) -> tuple[str, str]:
        """Returns (title, text)."""
        ...


class OfflineFixtureFetchProvider:
    async def raw_fetch(self, url: str) -> tuple[str, str]:
        fixture = OFFLINE_FETCH_FIXTURES.get(url)
        if fixture is None:
            # Still succeed for unknown URLs so ad-hoc runs don't dead-end;
            # a real HTTP provider would 404 here instead.
            return (url, f"No offline content available for {url}.")
        return (fixture["title"], fixture["text"])


class HttpFetchProvider:
    def __init__(self, timeout: float = 15.0):
        self._timeout = timeout

    async def raw_fetch(self, url: str) -> tuple[str, str]:
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            # Minimal extraction; a production build would use readability/trafilatura.
            text = resp.text
            title = url
            if "<title>" in text and "</title>" in text:
                title = text.split("<title>")[1].split("</title>")[0].strip()
            return (title, text)


class WebFetchTool:
    name = "web_fetch"

    def __init__(self, settings: Settings, provider: FetchProvider | None = None, injection_budget: int = 1):
        self._settings = settings
        self._provider = provider or self._default_provider(settings)
        self._injections_remaining = injection_budget

    @staticmethod
    def _default_provider(settings: Settings) -> FetchProvider:
        if settings.tavily_api_key:
            # Any online mode uses a real HTTP fetch, independent of the search provider.
            return HttpFetchProvider(settings.http_timeout_seconds)
        return OfflineFixtureFetchProvider()

    async def execute(self, url: str) -> WebDocument:
        if (
            self._settings.failure_injection_mode == FailureInjectionMode.FETCH_TIMEOUT
            and self._injections_remaining > 0
        ):
            self._injections_remaining -= 1
            raise ToolError("TIMEOUT", f"Fetching {url} timed out after "
                             f"{self._settings.http_timeout_seconds}s")

        try:
            title, text = await self._provider.raw_fetch(url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise ToolError("NOT_FOUND", f"{url} returned 404") from exc
            raise ToolError("UNKNOWN", f"HTTP error fetching {url}: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ToolError("TIMEOUT", f"Timed out fetching {url}") from exc

        return WebDocument(
            url=url,
            title=title,
            text=text,
            fetched_at=datetime.now(UTC),
        )
