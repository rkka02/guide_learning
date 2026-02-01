from __future__ import annotations

import json
from typing import Any

from .base import BaseAgent
from ..models import KnowledgePoint, LearningRecord


class LocateAgent(BaseAgent):
    """Builds a progressive learning plan (knowledge points) from user records."""

    def _format_records(self, records: list[LearningRecord], *, max_output_chars: int = 2000) -> str:
        formatted: list[str] = []
        for idx, record in enumerate(records, 1):
            output = record.output
            if len(output) > max_output_chars:
                output = output[:max_output_chars] + "\n...[truncated]..."

            formatted.append(
                "\n".join(
                    [
                        f"### Record {idx} [{record.type.upper()}]",
                        f"**Title**: {record.title}",
                        "",
                        "**User Question/Input**:",
                        record.user_query,
                        "",
                        "**System Output**:",
                        output,
                        "---",
                    ]
                )
            )
        return "\n".join(formatted)

    async def process(
        self,
        *,
        notebook_id: str,
        notebook_name: str,
        records: list[LearningRecord],
    ) -> dict[str, Any]:
        if not records:
            return {"success": False, "error": "No records provided", "knowledge_points": []}

        prompts = self.prompts()
        records_content = self._format_records(records)
        user_prompt = prompts.user_template.format(
            notebook_id=notebook_id,
            notebook_name=notebook_name,
            record_count=len(records),
            records_content=records_content,
        )

        # Try JSON-enforced output first; if provider/model doesn't support it, fall back.
        response_text: str
        try:
            response_text = await self.call_llm(
                system_prompt=prompts.system,
                user_prompt=user_prompt,
                response_format={"type": "json_object"},
            )
        except Exception:
            response_text = await self.call_llm(
                system_prompt=prompts.system,
                user_prompt=user_prompt,
                response_format=None,
            )

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"LocateAgent JSON parsing failed: {e}",
                "raw_response": response_text,
                "knowledge_points": [],
            }

        raw_points: Any
        if isinstance(parsed, list):
            raw_points = parsed
        elif isinstance(parsed, dict):
            raw_points = (
                parsed.get("knowledge_points")
                or parsed.get("points")
                or parsed.get("data")
                or parsed.get("items")
                or []
            )
        else:
            raw_points = []

        points: list[KnowledgePoint] = []
        if isinstance(raw_points, list):
            for item in raw_points:
                if isinstance(item, dict):
                    kp = KnowledgePoint(
                        knowledge_title=str(item.get("knowledge_title", "")).strip() or "Untitled",
                        knowledge_summary=str(item.get("knowledge_summary", "")).strip(),
                        user_difficulty=str(item.get("user_difficulty", "")).strip(),
                    )
                    points.append(kp)

        return {"success": True, "knowledge_points": points, "total_points": len(points)}

