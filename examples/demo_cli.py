from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import tempfile


# Allow running this file directly without installing the package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from portable_guide import GuideManager  # noqa: E402
from portable_guide.env import load_env  # noqa: E402
from portable_guide.llm.fake import FakeLLMClient  # noqa: E402


async def main() -> None:
    # Best-effort .env loading (handy when switching FakeLLM <-> real LLM).
    env_path = os.getenv("GUIDE_ENV_PATH")
    if env_path:
        load_env(Path(env_path))
    else:
        repo_env = ROOT / ".env"
        if repo_env.exists():
            load_env(repo_env)
        else:
            load_env()

    llm = FakeLLMClient()
    prompts_dir = Path(__file__).resolve().parents[1] / "prompts"

    with tempfile.TemporaryDirectory() as tmp:
        manager = GuideManager(
            llm=llm,
            prompts_dir=prompts_dir,
            output_dir=Path(tmp),
            language="en",
            model="fake",
            temperature=0.0,
            max_tokens=2000,
        )

        records = [
            {
                "id": "r1",
                "type": "solve",
                "title": "Example",
                "user_query": "Explain X simply.",
                "output": "X is ...",
            }
        ]

        created = await manager.create_session(
            notebook_id="cross_notebook",
            notebook_name="Demo Notebook",
            records=records,
        )
        assert created["success"]
        session_id = created["session_id"]
        print("Created session:", session_id)
        print("Knowledge points:", [p["knowledge_title"] for p in created["knowledge_points"]])

        started = await manager.start(session_id=session_id)
        assert started["success"]
        print("Start progress:", started["progress"])
        print("HTML length:", len(started["html"]))

        chat1 = await manager.chat(session_id=session_id, message="What should I focus on?")
        print("Chat answer:", chat1["answer"])

        # Walk through the whole plan (works regardless of how many points the planner produced).
        while True:
            moved = await manager.next(session_id=session_id)
            if moved.get("status") == "completed":
                print(
                    "Completed:",
                    moved.get("status"),
                    "summary length:",
                    len(moved.get("summary", "")),
                )
                break

            print("Next -> index:", moved.get("current_index"), "progress:", moved.get("progress"))
            chat2 = await manager.chat(session_id=session_id, message="Any pitfalls?")
            print("Chat answer:", chat2["answer"])


if __name__ == "__main__":
    asyncio.run(main())
