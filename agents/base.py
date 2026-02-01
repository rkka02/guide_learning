from __future__ import annotations

import logging
from typing import Any

from ..llm.base import LLMClient, LLMError, Message
from ..prompting import PromptBundle, PromptLoader


class BaseAgent:
    """
    Minimal base agent:
    - loads prompts (system + user_template)
    - calls an injected LLM client
    """

    def __init__(
        self,
        *,
        agent_name: str,
        llm: LLMClient,
        prompt_loader: PromptLoader,
        language: str,
        model: str,
        temperature: float,
        max_tokens: int,
        logger: logging.Logger | None = None,
    ):
        self.agent_name = agent_name
        self.llm = llm
        self.prompt_loader = prompt_loader
        self.language = language
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.logger = logger or logging.getLogger(f"portable_guide.{agent_name}")

    def prompts(self) -> PromptBundle:
        return self.prompt_loader.load(self.agent_name, self.language)

    async def call_llm(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        messages: list[Message] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            return await self.llm.complete(
                messages=messages,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format=response_format,
            )
        except LLMError:
            raise
        except Exception as e:  # pragma: no cover
            raise LLMError(str(e)) from e

