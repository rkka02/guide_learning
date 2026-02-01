from __future__ import annotations

from typing import Any, Literal, Protocol, Sequence, TypedDict


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMClient(Protocol):
    async def complete(
        self,
        *,
        messages: Sequence[Message],
        model: str,
        temperature: float,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str: ...


class LLMError(RuntimeError):
    """Raised when the LLM request fails or returns an invalid payload."""

