from __future__ import annotations

import html as _html
import json
import re
from typing import Any

from agents.base import BaseAgent
from models import KnowledgePoint


class InteractiveAgent(BaseAgent):
    """Generates a JSON-driven interactive HTML page for a knowledge point."""

    def _payload_from_knowledge(self, knowledge: KnowledgePoint) -> dict[str, Any]:
        title = knowledge.knowledge_title or "Knowledge Point"
        summary = knowledge.knowledge_summary or ""
        difficulty = knowledge.user_difficulty or "Beginner"
        return {
            "title": title,
            "concept": summary,
            "key_points": [
                "Summarize the core idea in your own words.",
                "Identify the key inputs, outputs, and assumptions.",
                f"Common difficulty: {difficulty}",
            ],
            "example_problem": f"Explain {title} with a simple example.",
            "example_answer": summary,
            "check_question": f"In one paragraph, explain {title}.",
            "next_hint": "If this makes sense, move to the next knowledge point.",
        }

    def _extract_json(self, response: str) -> dict[str, Any] | None:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        fenced = re.search(r"```json\s*([\s\S]*?)\s*```", response, flags=re.IGNORECASE)
        if fenced:
            try:
                return json.loads(fenced.group(1).strip())
            except json.JSONDecodeError:
                pass

        inline = re.search(r"({[\s\S]*})", response)
        if inline:
            try:
                return json.loads(inline.group(1))
            except json.JSONDecodeError:
                return None

        return None

    def _normalize_payload(self, payload: dict[str, Any] | None, knowledge: KnowledgePoint) -> dict[str, Any]:
        fallback = self._payload_from_knowledge(knowledge)
        if not payload or not isinstance(payload, dict):
            return fallback

        required = [
            "title",
            "concept",
            "key_points",
            "example_problem",
            "example_answer",
            "check_question",
            "next_hint",
        ]
        for key in required:
            if key not in payload:
                payload[key] = fallback[key]

        if not isinstance(payload.get("key_points"), list):
            payload["key_points"] = fallback["key_points"]

        return payload

    def _render_html(self, payload: dict[str, Any]) -> str:
        title = _html.escape(str(payload.get("title", "")))
        concept = _html.escape(str(payload.get("concept", ""))).replace("\n", "<br>")
        example_problem = _html.escape(str(payload.get("example_problem", ""))).replace("\n", "<br>")
        example_answer = _html.escape(str(payload.get("example_answer", ""))).replace("\n", "<br>")
        check_question_raw = str(payload.get("check_question", ""))
        check_question = _html.escape(check_question_raw).replace("\n", "<br>")
        check_question_js = json.dumps(check_question_raw)
        next_hint = _html.escape(str(payload.get("next_hint", ""))).replace("\n", "<br>")
        key_points = payload.get("key_points") or []
        key_points_html = "\n".join(f"<li>{_html.escape(str(item))}</li>" for item in key_points)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #F8FAFC;
      color: #0F172A;
      padding: 16px;
    }}
    .container {{ max-width: 960px; margin: 0 auto; width: 100%; }}
    .card {{
      background: #fff;
      border: 1px solid #E2E8F0;
      border-radius: 16px;
      padding: 16px;
      margin: 12px 0;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }}
    h1 {{ font-size: 1.35rem; margin: 0; color: #1E40AF; }}
    h2 {{ font-size: 1.05rem; margin: 0 0 8px; color: #2563EB; }}
    .muted {{ color: #475569; line-height: 1.7; }}
    .pill {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      background: #EEF2FF;
      border: 1px solid #C7D2FE;
      color: #3730A3;
      font-size: 12px;
    }}
    .row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    @media (max-width: 720px) {{
      .row {{ grid-template-columns: 1fr; }}
    }}
    textarea, input {{
      width: 100%;
      border: 1px solid #CBD5E1;
      border-radius: 12px;
      padding: 10px;
      font-family: inherit;
    }}
    button {{
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px solid #CBD5E1;
      background: #F8FAFC;
      cursor: pointer;
    }}
    button:hover {{ background: #EEF2FF; }}
    .hidden {{ display: none; }}
    .status {{
      font-size: 12px;
      color: #64748B;
      margin-top: 6px;
    }}
    .answer-box {{
      border: 1px dashed #CBD5E1;
      border-radius: 12px;
      padding: 10px;
      margin-top: 10px;
      background: #F8FAFC;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <span class="pill">Guide</span>
      <h1 style="margin-top:8px;">{title}</h1>
    </div>

    <div class="card">
      <h2>Concept</h2>
      <div class="muted">{concept}</div>
    </div>

    <div class="card">
      <h2>Key Points</h2>
      <ul>{key_points_html}</ul>
    </div>

    <div class="row">
      <div class="card">
        <h2>Example Problem</h2>
        <div class="muted">{example_problem}</div>
        <div class="answer-box">
          <button class="toggle-btn" data-target="exampleAnswer">Show/Hide example answer</button>
          <div id="exampleAnswer" class="muted hidden" style="margin-top:8px;">{example_answer}</div>
        </div>
      </div>

      <div class="card">
        <h2>Check Your Understanding</h2>
        <div class="muted">{check_question}</div>
        <textarea id="userAnswer" rows="5" placeholder="Write your answer..."></textarea>
        <div style="display:flex; gap:8px; margin-top:8px;">
          <button id="btnCheck">Check with LLM</button>
          <button id="btnAsk">Ask a question</button>
        </div>
        <div class="status" id="checkStatus">Ready</div>
        <div class="answer-box">
          <div id="checkResult" class="muted">(LLM feedback will appear here)</div>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Next</h2>
      <div class="muted">{next_hint}</div>
      <div class="status">Use the Next button in the main UI to proceed.</div>
    </div>
  </div>

  <script>
  document.addEventListener('DOMContentLoaded', function () {{
    var sessionId = "__SESSION_ID__";

    function setStatus(text) {{
      var el = document.getElementById('checkStatus');
      if (el) el.textContent = text;
    }}

    function setResult(text) {{
      var el = document.getElementById('checkResult');
      if (el) el.textContent = text || '';
    }}

    function postChat(message) {{
      if (!sessionId || sessionId === "__SESSION_ID__") {{
        setStatus('Missing session id');
        return Promise.resolve(null);
      }}
      return fetch('/guide/chat', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ session_id: sessionId, message: message }})
      }}).then(function (res) {{
        return res.json();
      }});
    }}

    document.querySelectorAll('.toggle-btn').forEach(function (btn) {{
      btn.addEventListener('click', function () {{
        var id = this.getAttribute('data-target');
        if (!id) return;
        var el = document.getElementById(id);
        if (!el) return;
        el.classList.toggle('hidden');
      }});
    }});

    var btnCheck = document.getElementById('btnCheck');
    var btnAsk = document.getElementById('btnAsk');
    if (btnCheck) {{
      btnCheck.addEventListener('click', function () {{
        var answer = document.getElementById('userAnswer').value || '';
        if (!answer.trim()) {{
          setStatus('Please write an answer first.');
          return;
        }}
        setStatus('Checking...');
        var question = {check_question_js};
        var prompt = "Evaluate the learner answer to this question.\n" +
          "Question: " + question + "\n" +
          "Learner answer: " + answer + "\n" +
          "Provide concise feedback and the correct answer if needed.";
        postChat(prompt).then(function (data) {{
          if (data && data.answer) {{
            setResult(data.answer);
            setStatus('Done');
          }} else {{
            setStatus('LLM did not respond.');
          }}
        }}).catch(function (err) {{
          setStatus('Error: ' + String(err));
        }});
      }});
    }}
    if (btnAsk) {{
      btnAsk.addEventListener('click', function () {{
        var answer = document.getElementById('userAnswer').value || '';
        var prompt = answer ? ("Question about this topic: " + answer) : "Explain this topic with another example.";
        setStatus('Asking...');
        postChat(prompt).then(function (data) {{
          if (data && data.answer) {{
            setResult(data.answer);
            setStatus('Done');
          }} else {{
            setStatus('LLM did not respond.');
          }}
        }}).catch(function (err) {{
          setStatus('Error: ' + String(err));
        }});
      }});
    }}
  }});
  </script>
</body>
</html>"""

    async def process(
        self,
        *,
        knowledge: KnowledgePoint,
        retry_with_bug: str | None = None,
    ) -> dict[str, Any]:
        prompts = self.prompts()

        if retry_with_bug:
            user_prompt = (
                "The previously generated JSON has the following issues:\n"
                f"{retry_with_bug}\n\n"
                "Please fix the JSON and regenerate it using the schema.\n\n"
                "Knowledge point:\n"
                f"- Title: {knowledge.knowledge_title}\n"
                f"- Summary: {knowledge.knowledge_summary}\n"
                f"- Difficulties: {knowledge.user_difficulty}\n"
            )
        else:
            user_prompt = prompts.user_template.format(
                knowledge_title=knowledge.knowledge_title,
                knowledge_summary=knowledge.knowledge_summary,
                user_difficulty=knowledge.user_difficulty,
            )

        try:
            response_text = await self.call_llm(system_prompt=prompts.system, user_prompt=user_prompt)
            payload = self._extract_json(response_text)
            normalized = self._normalize_payload(payload, knowledge)
            html = self._render_html(normalized)
            return {"success": True, "html": html, "is_fallback": payload is None}
        except Exception as e:
            normalized = self._normalize_payload(None, knowledge)
            return {
                "success": True,
                "html": self._render_html(normalized),
                "is_fallback": True,
                "error": str(e),
            }
