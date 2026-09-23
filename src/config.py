"""Central configuration. Loaded from environment variables (see .env.example)."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class FailureInjectionMode(str, Enum):
    NONE = "none"
    MALFORMED_SEARCH_RESPONSE = "malformed_search_response"
    FETCH_TIMEOUT = "fetch_timeout"
    RATE_LIMIT = "rate_limit"


class Settings(BaseModel):
    groq_api_key: str | None = None
    model_name: str = "llama-3.3-70b-versatile"

    # Search provider. If no key is configured, tools fall back to an
    # offline fixture provider (see tools/web_search.py) so the agent is
    # runnable and testable without any external credentials.
    tavily_api_key: str | None = None

    max_search_retries: int = 2
    max_fetch_retries: int = 2
    http_timeout_seconds: float = 15.0

    failure_injection_mode: FailureInjectionMode = FailureInjectionMode.NONE

    log_dir: Path = Path("logs")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            groq_api_key=os.environ.get("GROQ_API_KEY"),
            model_name=os.environ.get("MARKETSCOUT_MODEL", "llama-3.3-70b-versatile"),
            tavily_api_key=os.environ.get("TAVILY_API_KEY"),
            max_search_retries=int(os.environ.get("MAX_SEARCH_RETRIES", "2")),
            max_fetch_retries=int(os.environ.get("MAX_FETCH_RETRIES", "2")),
            http_timeout_seconds=float(os.environ.get("HTTP_TIMEOUT_SECONDS", "15")),
            failure_injection_mode=FailureInjectionMode(
                os.environ.get("FAILURE_INJECTION_MODE", "none")
            ),
        )
