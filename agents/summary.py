from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from models import GuideMessage, KnowledgePoint


class SummaryAgent(BaseAgent):
    """Generates a learning summary after completing all knowledge points."""

    def _format_points(self, points: list[KnowledgePoint]) -> str:
        out: list[str] = []
        for idx, p in enumerate(points, 1):
            out.append(
                "\n".join(
                    [
                        f"### Knowledge Point {idx}: {p.knowledge_title}",
                        f"**Content Summary**: {p.knowledge_summary}",
                        f"**Potential Difficulty**: {p.user_difficulty}",
                        "",
                    ]
                )
            )
        return "\n".join(out) if out else "(No knowledge points)"

    def _format_history(self, history: list[GuideMessage]) -> str:
        if not history:
            return "(No interactions)"

        lines: list[str] = []
        current_idx: int | None = None
        for m in history:
            if m.knowledge_index is not None and m.knowledge_index != current_idx:
                current_idx = m.knowledge_index
                lines.append(f"\n--- During knowledge point {current_idx + 1} ---\n")

            if m.role == "user":
                lines.append(f"**User Question**: {m.content}")
            elif m.role == "assistant":
                lines.append(f"**Assistant Answer**: {m.content}")
            else:
                lines.append(f"_System Message: {m.content}_")

        return "\n\n".join(lines)

    async def process(
        self,
        *,
        notebook_name: str,
        knowledge_points: list[KnowledgePoint],
        chat_history: list[GuideMessage],
    ) -> dict[str, Any]:
        prompts = self.prompts()
        user_prompt = prompts.user_template.format(
            notebook_name=notebook_name,
            total_points=len(knowledge_points),
            all_knowledge_points=self._format_points(knowledge_points),
            full_chat_history=self._format_history(chat_history),
        )

        try:
            response = await self.call_llm(system_prompt=prompts.system, user_prompt=user_prompt)
            return {"success": True, "summary_markdown": response.strip()}
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "summary_markdown": f"# Learning Summary\n\nCompleted: **{notebook_name}**",
            }

