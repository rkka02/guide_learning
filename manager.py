from __future__ import annotations

import logging
from pathlib import Path
import time
import uuid
from typing import Any

from agents import ChatAgent, InteractiveAgent, LocateAgent, SummaryAgent
from llm.base import LLMClient
from models import GuideMessage, GuideSession, KnowledgePoint, LearningRecord
from prompting import PromptLoader
from storage import FileSessionStore


class GuideManager:
    """
    Orchestrates the complete Guided Learning workflow.

    Integrate this class into your project (API/WS/CLI/etc).
    """

    def __init__(
        self,
        *,
        llm: LLMClient,
        prompts_dir: Path,
        output_dir: Path,
        language: str = "en",
        model: str,
        temperature: float = 0.5,
        max_tokens: int = 8000,
        logger: logging.Logger | None = None,
    ):
        self.logger = logger or logging.getLogger("guide_learning.GuideManager")

        self.language = language
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.store = FileSessionStore(output_dir)
        self.prompt_loader = PromptLoader(prompts_dir)

        agent_kwargs = {
            "llm": llm,
            "prompt_loader": self.prompt_loader,
            "language": self.language,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        self.locate_agent = LocateAgent(agent_name="locate_agent", **agent_kwargs)
        self.interactive_agent = InteractiveAgent(agent_name="interactive_agent", **agent_kwargs)
        self.chat_agent = ChatAgent(agent_name="chat_agent", **agent_kwargs)
        self.summary_agent = SummaryAgent(agent_name="summary_agent", **agent_kwargs)

        self._sessions: dict[str, GuideSession] = {}

    # ---------------------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------------------

    def _load(self, session_id: str) -> GuideSession | None:
        if session_id in self._sessions:
            return self._sessions[session_id]
        session = self.store.load(session_id)
        if session:
            self._sessions[session_id] = session
        return session

    def _save(self, session: GuideSession) -> None:
        self.store.save(session)
        self._sessions[session.session_id] = session

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _learning_state(self, points: list[KnowledgePoint], current_index: int) -> dict[str, Any]:
        total = len(points)
        if total == 0:
            return {"success": False, "status": "empty", "error": "No knowledge points"}

        if current_index >= total:
            return {
                "success": True,
                "status": "completed",
                "current_index": current_index,
                "current_knowledge": None,
                "total_points": total,
                "progress": 100,
                "message": "Completed all knowledge points.",
            }

        current = points[current_index]
        progress = int((current_index / total) * 100)
        return {
            "success": True,
            "status": "learning",
            "current_index": current_index,
            "current_knowledge": current,
            "total_points": total,
            "remaining_points": total - current_index - 1,
            "progress": progress,
            "message": f"Starting knowledge point {current_index + 1}: {current.knowledge_title}",
        }

    def _inject_session_id(self, html: str, session_id: str) -> str:
        if not html:
            return html
        return html.replace("__SESSION_ID__", session_id)

    # ---------------------------------------------------------------------
    # Public API (backend)
    # ---------------------------------------------------------------------

    async def create_session(
        self,
        *,
        notebook_id: str,
        notebook_name: str,
        records: list[dict[str, Any]] | list[LearningRecord],
    ) -> dict[str, Any]:
        """
        Create a new guided learning session and generate a learning plan.
        """
        session_id = str(uuid.uuid4())[:8]
        parsed_records = [
            r if isinstance(r, LearningRecord) else LearningRecord.from_dict(r) for r in records
        ]

        locate = await self.locate_agent.process(
            notebook_id=notebook_id,
            notebook_name=notebook_name,
            records=parsed_records,
        )
        if not locate.get("success"):
            return {
                "success": False,
                "error": locate.get("error", "Locate failed"),
                "session_id": None,
            }

        points: list[KnowledgePoint] = locate.get("knowledge_points", [])
        if not points:
            return {"success": False, "error": "No knowledge points found", "session_id": None}

        session = GuideSession(
            session_id=session_id,
            notebook_id=notebook_id,
            notebook_name=notebook_name,
            created_at=time.time(),
            status="initialized",
            knowledge_points=points,
            current_index=0,
        )
        self._save(session)

        return {
            "success": True,
            "session_id": session_id,
            "knowledge_points": [p.to_dict() for p in points],
            "total_points": len(points),
        }

    async def start(self, *, session_id: str) -> dict[str, Any]:
        """
        Start learning: generate HTML for the first knowledge point.
        """
        session = self._load(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        state = self._learning_state(session.knowledge_points, 0)
        if not state.get("success"):
            return state

        knowledge: KnowledgePoint = state["current_knowledge"]
        html_result = await self.interactive_agent.process(knowledge=knowledge)

        session.status = "learning"
        session.current_index = 0
        raw_html = str(html_result.get("html", ""))
        session.current_html = self._inject_session_id(raw_html, session_id)
        session.chat_history.append(
            GuideMessage(role="system", content=state.get("message", ""), knowledge_index=0)
        )
        self._save(session)

        return {
            "success": True,
            "current_index": 0,
            "current_knowledge": knowledge.to_dict(),
            "html": session.current_html,
            "progress": state.get("progress", 0),
            "total_points": len(session.knowledge_points),
            "message": state.get("message", ""),
        }

    async def next(self, *, session_id: str) -> dict[str, Any]:
        """
        Move to the next knowledge point (or complete and summarize).
        """
        session = self._load(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        new_index = session.current_index + 1
        state = self._learning_state(session.knowledge_points, new_index)
        if not state.get("success"):
            return state

        if state.get("status") == "completed":
            summary = await self.summary_agent.process(
                notebook_name=session.notebook_name,
                knowledge_points=session.knowledge_points,
                chat_history=session.chat_history,
            )

            session.status = "completed"
            session.current_index = new_index
            session.summary_markdown = str(summary.get("summary_markdown", ""))
            session.chat_history.append(GuideMessage(role="system", content=state.get("message", "")))
            self._save(session)

            return {
                "success": True,
                "status": "completed",
                "summary": session.summary_markdown,
                "progress": 100,
                "message": state.get("message", ""),
            }

        knowledge: KnowledgePoint = state["current_knowledge"]
        html_result = await self.interactive_agent.process(knowledge=knowledge)
        session.current_index = new_index
        raw_html = str(html_result.get("html", ""))
        session.current_html = self._inject_session_id(raw_html, session_id)
        msg = f"Entering knowledge point {new_index + 1}: {knowledge.knowledge_title}"
        session.chat_history.append(GuideMessage(role="system", content=msg, knowledge_index=new_index))
        self._save(session)

        return {
            "success": True,
            "current_index": new_index,
            "current_knowledge": knowledge.to_dict(),
            "html": session.current_html,
            "progress": state.get("progress", 0),
            "total_points": len(session.knowledge_points),
            "remaining_points": state.get("remaining_points", 0),
            "message": msg,
        }

    async def chat(self, *, session_id: str, message: str) -> dict[str, Any]:
        """
        Chat about the current knowledge point.
        """
        session = self._load(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        if session.status != "learning":
            return {"success": False, "error": f"Invalid session status: {session.status}"}

        idx = session.current_index
        knowledge = session.knowledge_points[idx]
        history = [m for m in session.chat_history if m.knowledge_index == idx]

        session.chat_history.append(GuideMessage(role="user", content=message, knowledge_index=idx))
        result = await self.chat_agent.process(
            knowledge=knowledge,
            chat_history=history,
            user_question=message,
        )
        answer = str(result.get("answer", ""))
        session.chat_history.append(GuideMessage(role="assistant", content=answer, knowledge_index=idx))
        self._save(session)

        return {"success": True, "answer": answer, "knowledge_index": idx}

    async def fix_html(self, *, session_id: str, bug_description: str) -> dict[str, Any]:
        """
        Ask the InteractiveAgent to fix/regenerate the current HTML.
        """
        session = self._load(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}

        knowledge = session.knowledge_points[session.current_index]
        result = await self.interactive_agent.process(
            knowledge=knowledge,
            retry_with_bug=bug_description,
        )
        if result.get("success"):
            raw_html = str(result.get("html", session.current_html))
            session.current_html = self._inject_session_id(raw_html, session_id)
            self._save(session)

        return {
            "success": bool(result.get("success")),
            "html": str(result.get("html", "")),
            "error": result.get("error"),
        }

    def get_session(self, *, session_id: str) -> dict[str, Any] | None:
        session = self._load(session_id)
        return session.to_dict() if session else None

    def get_current_html(self, *, session_id: str) -> str | None:
        session = self._load(session_id)
        return session.current_html if session else None
