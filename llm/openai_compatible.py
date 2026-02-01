from __future__ import annotations

import os
from typing import Any, Sequence

import httpx

from .base import LLMClient, LLMError, Message
from ..env import load_env


class OpenAICompatibleClient(LLMClient):
    """
    Minimal OpenAI-compatible Chat Completions client.

    Works with:
    - OpenAI (if using /v1/chat/completions)
    - Many OpenAI-compatible providers (local or hosted)

    Env helpers (optional):
      - LLM_API_KEY (or OPENAI_API_KEY)
      - LLM_BASE_URL (or LLM_HOST) (default: https://api.openai.com/v1)
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_s: float = 60.0,
        default_headers: dict[str, str] | None = None,
        verify_ssl: bool = True,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.default_headers = default_headers or {}
        self.verify_ssl = verify_ssl

    @classmethod
    def from_env(cls) -> "OpenAICompatibleClient":
        # Best-effort .env loading (no-op if missing).
        load_env()

        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        if not api_key:
            raise ValueError("Missing API key. Set LLM_API_KEY (or OPENAI_API_KEY).")
        base_url = os.getenv("LLM_BASE_URL") or os.getenv("LLM_HOST") or "https://api.openai.com/v1"
        return cls(api_key=api_key, base_url=base_url)

    async def complete(
        self,
        *,
        messages: Sequence[Message],
        model: str,
        temperature: float,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.default_headers,
        }

        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if max_tokens is not None:
            max_tokens_field = os.getenv("LLM_MAX_TOKENS_FIELD", "max_tokens")
            payload[max_tokens_field] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format

        async with httpx.AsyncClient(timeout=self.timeout_s, verify=self.verify_ssl) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.is_error:
                    # Retry once with max_completion_tokens if max_tokens is rejected.
                    text = resp.text
                    if (
                        resp.status_code == 400
                        and "max_tokens" in text
                        and "max_completion_tokens" in text
                    ):
                        payload.pop("max_tokens", None)
                        payload["max_completion_tokens"] = max_tokens
                        resp = await client.post(url, headers=headers, json=payload)

                    if resp.is_error:
                        raise LLMError(
                            f"LLM request failed: {resp.status_code} {resp.reason_phrase} - {resp.text}"
                        )
                data = resp.json()
            except LLMError:
                raise
            except Exception as e:  # pragma: no cover
                raise LLMError(f"LLM request failed: {e}") from e

        try:
            return str(data["choices"][0]["message"]["content"])
        except Exception as e:  # pragma: no cover
            raise LLMError(f"Unexpected LLM response shape: {data}") from e
