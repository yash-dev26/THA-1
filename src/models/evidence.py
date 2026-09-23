"""Evidence and tool-result models.

Design rule enforced at the type level: a `SearchResult` (a snippet) can
never be treated as `Evidence`. Only a fetched `WebDocument` can become
`Evidence`. This is what forces the agent to actually fetch primary sources
instead of hallucinating from search snippets.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class Confidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class SearchResult(BaseModel):
    """A single result from web_search. NOT authoritative evidence."""

    title: str
    url: HttpUrl
    snippet: str
    source: str


class SearchResults(BaseModel):
    query: str
    results: list[SearchResult]


class WebDocument(BaseModel):
    """The result of actually fetching a page. This is what evidence is built from."""

    url: HttpUrl
    title: str
    text: str
    fetched_at: datetime


class Evidence(BaseModel):
    """A single validated claim, traceable to a fetched document."""

    claim: str
    competitor: str
    source_url: HttpUrl
    confidence: Confidence
    excerpt: str = Field(..., description="Short supporting excerpt from the source document")


class FailureType(str, Enum):
    RATE_LIMIT = "RATE_LIMIT"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    TIMEOUT = "TIMEOUT"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN = "UNKNOWN"


class ToolFailure(BaseModel):
    tool: str
    step_id: int | None = None
    error_type: FailureType
    message: str
    occurred_at: datetime
    recovered: bool = False
    recovery_action: str | None = None
