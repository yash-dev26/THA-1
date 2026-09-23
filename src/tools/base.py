"""Common tool abstraction (Protocol) shared by all tools.

Every tool takes a typed Pydantic input and returns a typed Pydantic
output. This makes tools replaceable, mockable in tests, and easy to
register generically instead of hand-wiring each one into the graph.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class Tool(Protocol):
    name: str

    async def execute(self, input: BaseModel) -> BaseModel:
        ...


class ToolError(Exception):
    """Raised by a tool implementation. Carries a structured error_type
    string that the RecoveryPolicy uses to decide how to respond, so
    recovery logic never has to string-match exception messages."""

    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
