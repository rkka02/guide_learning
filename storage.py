from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models import GuideSession


class FileSessionStore:
    """
    JSON-file session store.

    - File per session: session_{session_id}.json
    - Atomic writes: write temp file then replace
    """

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def session_path(self, session_id: str) -> Path:
        return self.output_dir / f"session_{session_id}.json"

    def save(self, session: GuideSession) -> None:
        path = self.session_path(session.session_id)
        tmp_path = path.with_suffix(path.suffix + ".tmp")

        payload = session.to_dict()
        tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(path)

    def load(self, session_id: str) -> GuideSession | None:
        path = self.session_path(session_id)
        if not path.exists():
            return None
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return GuideSession.from_dict(data)

