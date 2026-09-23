"""Deterministic recovery policy.

Core principle (worth restating, it's the crux of the "robustness" rubric
item): the LLM decides *what* to research. The application decides *how*
infrastructure failures are handled. None of the logic below asks an LLM
what to do about a 429 or a schema mismatch — it's a plain lookup table,
which is exactly what makes it testable and reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.models.evidence import FailureType


class RecoveryAction(str, Enum):
    RETRY = "retry"
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    FALLBACK_ALTERNATE_QUERY = "fallback_alternate_query"
    GIVE_UP = "give_up"


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    max_attempts: int
    backoff_seconds: float = 0.0


class RecoveryPolicy:
    """Maps a failure type + current retry count to a deterministic decision."""

    def __init__(self, max_retries: int = 2):
        self._max_retries = max_retries

    def decide(self, error_type: FailureType, attempt_number: int) -> RecoveryDecision:
        if attempt_number > self._max_retries:
            return RecoveryDecision(RecoveryAction.FALLBACK_ALTERNATE_QUERY, self._max_retries)

        if error_type == FailureType.RATE_LIMIT:
            return RecoveryDecision(
                RecoveryAction.RETRY_WITH_BACKOFF,
                self._max_retries,
                backoff_seconds=min(2 ** attempt_number, 8),
            )

        if error_type == FailureType.SCHEMA_ERROR:
            return RecoveryDecision(RecoveryAction.RETRY, self._max_retries)

        if error_type == FailureType.TIMEOUT:
            return RecoveryDecision(
                RecoveryAction.RETRY_WITH_BACKOFF,
                self._max_retries,
                backoff_seconds=min(2 ** attempt_number, 8),
            )

        if error_type == FailureType.NOT_FOUND:
            return RecoveryDecision(RecoveryAction.FALLBACK_ALTERNATE_QUERY, self._max_retries)

        return RecoveryDecision(RecoveryAction.FALLBACK_ALTERNATE_QUERY, self._max_retries)
