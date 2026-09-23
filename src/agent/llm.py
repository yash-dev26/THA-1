"""Thin LLM client wrapper.

Centralizing this means planner.py and nodes.py (synthesis) don't each
reimplement API-key handling and JSON extraction. When no GROQ_API_KEY is
configured, `LLMClient.available` is False and callers fall back to
deterministic heuristics — this keeps the agent runnable (and its tests
fast and free) without any credentials.

Backed by Groq's OpenAI-compatible chat completions API (fast inference,
open-weight models such as Llama 3.3). Swapping providers only touches
this file — planner.py and nodes.py depend on `LLMClient`, not on Groq
directly.
"""

from __future__ import annotations

import json
from typing import Any

from src.config import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = None
        if settings.groq_api_key:
            from groq import AsyncGroq  # imported lazily so the package is optional offline

            self._client = AsyncGroq(api_key=settings.groq_api_key)

    @property
    def available(self) -> bool:
        return self._client is not None

    async def complete_json(self, system: str, prompt: str, max_tokens: int = 1500) -> Any:
        """Calls the model and parses a JSON object from its response.
        Raises if unavailable or if the model didn't return valid JSON —
        callers are expected to catch and fall back to a heuristic."""
        if not self._client:
            raise RuntimeError("LLM client not configured (no GROQ_API_KEY)")

        response = await self._client.chat.completions.create(
            model=self._settings.model_name,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        text = response.choices[0].message.content or ""
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
