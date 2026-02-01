from __future__ import annotations

from typing import Any

from .base import BaseAgent
from ..models import GuideMessage, KnowledgePoint


class ChatAgent(BaseAgent):
    """Answers user questions during learning, focusing on the current knowledge point."""

    def _format_history(self, history: list[GuideMessage], *, max_messages: int = 10) -> str:
        if not history:
            return "(No chat history)"

        lines: list[str] = []
        for msg in history[-max_messages:]:
            if msg.role == "user":
                lines.append(f"**User**: {msg.content}")
            elif msg.role == "assistant":
                lines.append(f"**Assistant**: {msg.content}")
            else:
                lines.append(f"_System: {msg.content}_")
        return "\n\n".join(lines)

    async def process(
        self,
        *,
        knowledge: KnowledgePoint,
        chat_history: list[GuideMessage],
        user_question: str,
    ) -> dict[str, Any]:
        if not user_question.strip():
            return {"success": False, "error": "Question cannot be empty", "answer": ""}

        prompts = self.prompts()
        user_prompt = prompts.user_template.format(
            knowledge_title=knowledge.knowledge_title,
            knowledge_summary=knowledge.knowledge_summary,
            user_difficulty=knowledge.user_difficulty,
            chat_history=self._format_history(chat_history),
            user_question=user_question,
        )

        try:
            response = await self.call_llm(system_prompt=prompts.system, user_prompt=user_prompt)
            return {"success": True, "answer": response.strip()}
        except Exception as e:
            return {"success": False, "error": str(e), "answer": "Failed to answer. Please retry."}

