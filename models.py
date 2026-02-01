from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Literal


Role = Literal["system", "user", "assistant"]
SessionStatus = Literal["initialized", "learning", "completed"]


@dataclass(frozen=True)
class LearningRecord:
    """Input record for Guided Learning (portable equivalent of a notebook record)."""

    id: str
    type: str
    title: str
    user_query: str
    output: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LearningRecord":
        return cls(
            id=str(data.get("id", "")),
            type=str(data.get("type", "unknown")),
            title=str(data.get("title", "")),
            user_query=str(data.get("user_query", "")),
            output=str(data.get("output", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "user_query": self.user_query,
            "output": self.output,
        }


@dataclass(frozen=True)
class KnowledgePoint:
    """A single knowledge point in a learning plan."""

    knowledge_title: str
    knowledge_summary: str
    user_difficulty: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgePoint":
        return cls(
            knowledge_title=str(data.get("knowledge_title", "")),
            knowledge_summary=str(data.get("knowledge_summary", "")),
            user_difficulty=str(data.get("user_difficulty", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_title": self.knowledge_title,
            "knowledge_summary": self.knowledge_summary,
            "user_difficulty": self.user_difficulty,
        }


@dataclass(frozen=True)
class GuideMessage:
    """A chat message stored in a session."""

    role: Role
    content: str
    timestamp: float = field(default_factory=time.time)
    knowledge_index: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuideMessage":
        return cls(
            role=data.get("role", "user"),
            content=str(data.get("content", "")),
            timestamp=float(data.get("timestamp", time.time())),
            knowledge_index=data.get("knowledge_index"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.knowledge_index is not None:
            payload["knowledge_index"] = self.knowledge_index
        return payload


@dataclass
class GuideSession:
    """Guided learning session state (persisted as JSON)."""

    session_id: str
    notebook_id: str
    notebook_name: str
    created_at: float = field(default_factory=time.time)
    status: SessionStatus = "initialized"
    knowledge_points: list[KnowledgePoint] = field(default_factory=list)
    current_index: int = 0
    chat_history: list[GuideMessage] = field(default_factory=list)
    current_html: str = ""
    summary_markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "notebook_id": self.notebook_id,
            "notebook_name": self.notebook_name,
            "created_at": self.created_at,
            "status": self.status,
            "knowledge_points": [kp.to_dict() for kp in self.knowledge_points],
            "current_index": self.current_index,
            "chat_history": [m.to_dict() for m in self.chat_history],
            "current_html": self.current_html,
            "summary_markdown": self.summary_markdown,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuideSession":
        points = [KnowledgePoint.from_dict(p) for p in (data.get("knowledge_points") or [])]
        messages = [GuideMessage.from_dict(m) for m in (data.get("chat_history") or [])]

        # Backward-compat: some implementations use "summary" instead of "summary_markdown".
        summary = data.get("summary_markdown") or data.get("summary") or ""

        return cls(
            session_id=str(data.get("session_id", "")),
            notebook_id=str(data.get("notebook_id", "")),
            notebook_name=str(data.get("notebook_name", "")),
            created_at=float(data.get("created_at", time.time())),
            status=data.get("status", "initialized"),
            knowledge_points=points,
            current_index=int(data.get("current_index", 0)),
            chat_history=messages,
            current_html=str(data.get("current_html", "")),
            summary_markdown=str(summary),
        )

