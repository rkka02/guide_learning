from __future__ import annotations

from pathlib import Path
import json
import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel


# Allow running this file directly without installing the package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from manager import GuideManager  # noqa: E402
from env import load_env  # noqa: E402
from llm.fake import FakeLLMClient  # noqa: E402
from llm.openai_compatible import OpenAICompatibleClient  # noqa: E402


class CreateSessionRequest(BaseModel):
    notebook_id: str | None = None
    notebook_name: str | None = None
    records: list[dict]


class SessionRequest(BaseModel):
    session_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class FixHtmlRequest(BaseModel):
    session_id: str
    bug_description: str


def build_manager() -> GuideManager:
    # Best-effort .env loading for GUIDE_* and LLM_* vars.
    # Priority: GUIDE_ENV_PATH > repo root .env > upward search.
    env_path = os.getenv("GUIDE_ENV_PATH")
    if env_path:
        load_env(Path(env_path))
    else:
        repo_env = ROOT / ".env"
        if repo_env.exists():
            load_env(repo_env)
        else:
            load_env()

    prompts_dir = Path(__file__).resolve().parents[1] / "prompts"
    output_dir = Path(os.getenv("GUIDE_OUTPUT_DIR", "./guide_sessions"))

    language = os.getenv("GUIDE_LANGUAGE", "en")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    temperature = float(os.getenv("GUIDE_TEMPERATURE", "0.5"))
    max_tokens = int(os.getenv("GUIDE_MAX_TOKENS", "8000"))

    # Default to FakeLLM so the example runs out-of-the-box without API keys.
    if os.getenv("GUIDE_FAKE_LLM", "1") == "1":
        llm = FakeLLMClient()
    else:
        llm = OpenAICompatibleClient.from_env()

    return GuideManager(
        llm=llm,
        prompts_dir=prompts_dir,
        output_dir=output_dir,
        language=language,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


app = FastAPI(title="Portable Guide API")
manager = build_manager()


TRANSFORMER_DUMMY_RECORDS: list[dict] = [
    {
        "id": "t1",
        "type": "question",
        "title": "Transformer overview",
        "user_query": "What is the Transformer architecture, and why did it replace RNNs in many NLP tasks?",
        "output": (
            "Transformers replace recurrence with self-attention. Key ideas: (1) attention lets each token "
            "directly attend to all others, enabling parallelism; (2) stacked layers of attention + MLP, with "
            "residual connections and layer norm; (3) positional information is injected via positional "
            "encodings/embeddings. The result trains faster and captures long-range dependencies better."
        ),
    },
    {
        "id": "t2",
        "type": "solve",
        "title": "Scaled dot-product attention",
        "user_query": "Explain scaled dot-product attention (Q, K, V). Why do we divide by sqrt(d_k)?",
        "output": (
            "Attention(Q,K,V)=softmax(QK^T / sqrt(d_k)) V. The scaling prevents dot products from growing too "
            "large when d_k is big, which would push softmax into saturated regions and harm gradients."
        ),
    },
    {
        "id": "t3",
        "type": "question",
        "title": "Multi-head attention",
        "user_query": "What is multi-head attention? Why not just one big attention head?",
        "output": (
            "Multi-head attention runs attention multiple times with different learned projections. Each head "
            "can focus on different relations (syntax, coreference, local vs global patterns). Heads are "
            "concatenated then projected back. It improves expressiveness without huge cost."
        ),
    },
    {
        "id": "t4",
        "type": "research",
        "title": "Positional encoding",
        "user_query": "If transformers have no recurrence, how do they know token order? Compare sinusoidal vs learned.",
        "output": (
            "Order is injected by adding positional encodings to token embeddings. Sinusoidal encodings are "
            "fixed functions enabling extrapolation to longer lengths; learned positional embeddings can fit "
            "training lengths well but may generalize less. Many variants exist (RoPE, ALiBi, etc.)."
        ),
    },
    {
        "id": "t5",
        "type": "solve",
        "title": "Encoder-decoder vs decoder-only",
        "user_query": "Explain encoder-decoder Transformers vs decoder-only (GPT-style). Where is masking used?",
        "output": (
            "Encoder-decoder: encoder self-attention over input, decoder uses masked self-attention (causal) "
            "plus cross-attention to encoder outputs. Decoder-only: only masked self-attention; trained as a "
            "causal language model to predict next tokens."
        ),
    },
]


@app.get("/")
async def root():
    # Convenient default for local development.
    return RedirectResponse(url="/ui")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "guide_learning"}


@app.get("/ui")
async def ui():
    using_fake = os.getenv("GUIDE_FAKE_LLM", "1") == "1"
    default_records_json = json.dumps(TRANSFORMER_DUMMY_RECORDS, ensure_ascii=False, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Portable Guide UI</title>
  <style>
    :root {{
      --bg: #0B1220;
      --panel: #0F172A;
      --card: #111C33;
      --border: rgba(148, 163, 184, 0.18);
      --text: #E2E8F0;
      --muted: #94A3B8;
      --accent: #3B82F6;
      --accent2: #22C55E;
      --warn: #F59E0B;
      --danger: #EF4444;
      --shadow: 0 8px 30px rgba(0,0,0,0.35);
      --radius: 14px;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: var(--sans);
      background: radial-gradient(1200px 600px at 20% 0%, rgba(59,130,246,0.25), transparent 60%),
                  radial-gradient(900px 500px at 80% 20%, rgba(34,197,94,0.18), transparent 60%),
                  var(--bg);
      color: var(--text);
    }}

    header {{
      padding: 18px 20px;
      border-bottom: 1px solid var(--border);
      background: rgba(15,23,42,0.65);
      backdrop-filter: blur(8px);
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    header .row {{
      display: flex;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
    }}
    h1 {{
      font-size: 16px;
      margin: 0;
      letter-spacing: 0.2px;
    }}
    .pill {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      font-size: 12px;
      color: var(--muted);
    }}
    .dot {{
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: {('#22C55E' if using_fake else '#3B82F6')};
      box-shadow: 0 0 0 4px rgba(34,197,94,0.12);
    }}
    .links a {{
      color: var(--muted);
      text-decoration: none;
      font-size: 12px;
      margin-left: 12px;
    }}
    .links a:hover {{ color: var(--text); }}

    .grid {{
      display: grid;
      grid-template-columns: 420px 1fr;
      gap: 14px;
      padding: 14px;
      height: calc(100vh - 62px);
    }}

    .panel {{
      background: rgba(15,23,42,0.75);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}

    .panel-header {{
      padding: 12px 12px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .panel-header h2 {{
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin: 0;
      color: var(--muted);
    }}
    .panel-body {{
      padding: 12px;
      overflow: auto;
      min-height: 0;
    }}

    .card {{
      background: rgba(17,28,51,0.65);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 12px;
      margin-bottom: 12px;
    }}

    label {{
      display: block;
      font-size: 11px;
      color: var(--muted);
      margin-bottom: 6px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    textarea, input {{
      width: 100%;
      border: 1px solid var(--border);
      background: rgba(2,6,23,0.35);
      color: var(--text);
      border-radius: 12px;
      padding: 10px 10px;
      outline: none;
      font-family: var(--mono);
      font-size: 12px;
    }}
    textarea {{ min-height: 180px; resize: vertical; }}
    input {{ font-family: var(--sans); }}

    button {{
      border: 1px solid var(--border);
      background: rgba(59,130,246,0.14);
      color: var(--text);
      border-radius: 12px;
      padding: 9px 10px;
      cursor: pointer;
      font-size: 13px;
    }}
    button:hover {{ border-color: rgba(59,130,246,0.45); }}
    button.primary {{ background: rgba(59,130,246,0.28); }}
    button.success {{ background: rgba(34,197,94,0.22); }}
    button.warn {{ background: rgba(245,158,11,0.22); }}
    button.danger {{ background: rgba(239,68,68,0.18); }}
    button:disabled {{
      opacity: 0.5;
      cursor: not-allowed;
    }}

    .btn-row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 10px;
    }}

    .kv {{
      display: grid;
      grid-template-columns: 100px 1fr;
      gap: 8px 10px;
      align-items: center;
      font-size: 12px;
    }}
    .kv .k {{ color: var(--muted); }}
    .mono {{ font-family: var(--mono); }}
    .small {{ font-size: 12px; color: var(--muted); }}

    .chat-log {{
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 10px;
      background: rgba(2,6,23,0.25);
      min-height: 160px;
      max-height: 260px;
      overflow: auto;
      font-size: 13px;
      line-height: 1.45;
      white-space: pre-wrap;
    }}
    .chat-line {{ margin: 0 0 10px 0; }}
    .role {{
      display: inline-block;
      font-size: 11px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--muted);
      margin-right: 8px;
    }}

    .right {{
      display: grid;
      grid-template-rows: 1fr auto;
      gap: 14px;
      min-height: 0;
    }}
    iframe {{
      width: 100%;
      height: 100%;
      border: 0;
      background: #fff;
    }}
    pre {{
      margin: 0;
      font-family: var(--mono);
      font-size: 11px;
      color: var(--muted);
      white-space: pre-wrap;
    }}

    @media (max-width: 980px) {{
      .grid {{ grid-template-columns: 1fr; height: auto; }}
      .right {{ grid-template-rows: 420px auto; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="row">
      <div class="pill">
        <span class="dot"></span>
        <h1>Portable Guide UI</h1>
        <span class="small">LLM: <span class="mono">{'FakeLLM' if using_fake else 'OpenAI-compatible'}</span></span>
      </div>
      <div class="links">
        <a href="/docs" target="_blank">/docs</a>
        <a href="/health" target="_blank">/health</a>
      </div>
    </div>
  </header>

  <div class="grid">
    <!-- LEFT: Controls -->
    <div class="panel">
      <div class="panel-header">
        <h2>Session</h2>
        <span id="status" class="small">idle</span>
      </div>
      <div class="panel-body">
        <div class="card">
          <div class="kv">
            <div class="k">Session</div><div class="mono" id="sessionId">-</div>
            <div class="k">Index</div><div class="mono" id="currentIndex">-</div>
            <div class="k">Progress</div><div class="mono" id="progress">-</div>
          </div>
        </div>

        <div class="card">
          <label>Dummy Records (Transformer architecture)</label>
          <textarea id="records">{default_records_json}</textarea>
          <div class="btn-row">
            <button class="primary" id="btnCreate">Create Session</button>
            <button class="success" id="btnStart" disabled>Start</button>
            <button class="success" id="btnNext" disabled>Next</button>
            <button class="warn" id="btnReload">Reload Session</button>
          </div>
          <div class="small" style="margin-top:8px;">
            Tip: keep <span class="mono">GUIDE_FAKE_LLM=1</span> for offline verification.
          </div>
        </div>

        <div class="card">
          <label>Knowledge Points</label>
          <div id="kpList" class="small">(none)</div>
        </div>

        <div class="card">
          <label>Chat</label>
          <div id="chatLog" class="chat-log"></div>
          <div style="display:flex; gap:8px; margin-top:8px;">
            <input id="chatInput" placeholder="Ask about the current knowledge point..." />
            <button id="btnChat" class="primary" style="width:120px;">Send</button>
          </div>
        </div>

        <div class="card">
          <label>Fix HTML (optional)</label>
          <input id="bugInput" placeholder="Describe the issue (e.g., button not clickable, overflow...)" />
          <div class="btn-row" style="grid-template-columns: 1fr;">
            <button class="warn" id="btnFix" disabled>Fix HTML</button>
          </div>
        </div>

        <div class="card">
          <label>Last Response (debug)</label>
          <pre id="debug">(none)</pre>
        </div>
      </div>
    </div>

    <!-- RIGHT: HTML + Summary -->
    <div class="right">
      <div class="panel">
        <div class="panel-header">
          <h2>Interactive HTML</h2>
          <span class="small">rendered in iframe</span>
        </div>
        <div style="flex:1; min-height:0;">
          <iframe id="viewer" sandbox="allow-scripts" title="guide-html"></iframe>
        </div>
      </div>

      <div class="panel" style="max-height: 280px;">
        <div class="panel-header">
          <h2>Summary</h2>
          <span class="small">appears when completed</span>
        </div>
        <div class="panel-body">
          <pre id="summary">(not completed)</pre>
        </div>
      </div>
    </div>
  </div>

  <script>
  (function() {{
    var sessionId = null;

    function setStatus(text) {{
      var el = document.getElementById('status');
      if (el) el.textContent = text;
    }}

    function setDebug(obj) {{
      var el = document.getElementById('debug');
      if (!el) return;
      try {{
        el.textContent = JSON.stringify(obj, null, 2);
      }} catch (e) {{
        el.textContent = String(obj);
      }}
    }}

    function appendChat(role, content) {{
      var log = document.getElementById('chatLog');
      if (!log) return;
      var p = document.createElement('div');
      p.className = 'chat-line';
      p.innerHTML = '<span class="role">' + role + '</span>' + (content || '');
      log.appendChild(p);
      log.scrollTop = log.scrollHeight;
    }}

    function updateButtons(state) {{
      var btnStart = document.getElementById('btnStart');
      var btnNext = document.getElementById('btnNext');
      var btnFix = document.getElementById('btnFix');
      if (btnStart) btnStart.disabled = !state.canStart;
      if (btnNext) btnNext.disabled = !state.canNext;
      if (btnFix) btnFix.disabled = !state.canFix;
    }}

    function updateSessionHeader(data) {{
      var sid = document.getElementById('sessionId');
      var idx = document.getElementById('currentIndex');
      var prog = document.getElementById('progress');
      if (sid) sid.textContent = data.session_id || '-';
      if (idx) idx.textContent = (data.current_index === undefined ? '-' : String(data.current_index));
      if (prog) prog.textContent = (data.progress === undefined ? '-' : (String(data.progress) + '%'));
    }}

    function updateKnowledgePoints(kps) {{
      var el = document.getElementById('kpList');
      if (!el) return;
      if (!kps || !kps.length) {{
        el.textContent = '(none)';
        return;
      }}
      var lines = [];
      for (var i = 0; i < kps.length; i++) {{
        var title = kps[i].knowledge_title || ('KP ' + (i+1));
        lines.push((i+1) + '. ' + title);
      }}
      el.textContent = lines.join('\\n');
    }}

    async function postJson(path, body) {{
      var res = await fetch(path, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(body || {{}})
      }});
      var data = await res.json();
      return data;
    }}

    async function getJson(path) {{
      var res = await fetch(path);
      var data = await res.json();
      return data;
    }}

    async function createSession() {{
      try {{
        setStatus('creating session...');
        var recordsText = document.getElementById('records').value;
        var records = JSON.parse(recordsText);
        var data = await postJson('/guide/create_session', {{
          notebook_id: 'cross_notebook',
          notebook_name: 'Transformer Architecture (dummy)',
          records: records
        }});
        setDebug(data);
        if (!data.success) {{
          setStatus('error');
          appendChat('system', 'Create failed: ' + (data.error || 'unknown'));
          return;
        }}
        sessionId = data.session_id;
        updateKnowledgePoints(data.knowledge_points || []);
        updateSessionHeader({{ session_id: sessionId, current_index: -1, progress: 0 }});
        updateButtons({{ canStart: true, canNext: false, canFix: false }});
        document.getElementById('summary').textContent = '(not completed)';
        document.getElementById('viewer').srcdoc = '';
        document.getElementById('chatLog').innerHTML = '';
        appendChat('system', 'Session created. Click Start.');
        setStatus('initialized');
      }} catch (e) {{
        setStatus('error');
        appendChat('system', 'Create error: ' + String(e));
      }}
    }}

    async function startLearning() {{
      if (!sessionId) return;
      try {{
        setStatus('starting...');
        var data = await postJson('/guide/start', {{ session_id: sessionId }});
        setDebug(data);
        if (!data.success) {{
          setStatus('error');
          appendChat('system', 'Start failed: ' + (data.error || 'unknown'));
          return;
        }}
        document.getElementById('viewer').srcdoc = data.html || '';
        updateSessionHeader({{ session_id: sessionId, current_index: data.current_index, progress: data.progress }});
        updateButtons({{ canStart: false, canNext: true, canFix: true }});
        appendChat('system', data.message || 'Started.');
        setStatus('learning');
      }} catch (e) {{
        setStatus('error');
        appendChat('system', 'Start error: ' + String(e));
      }}
    }}

    async function nextKnowledge() {{
      if (!sessionId) return;
      try {{
        setStatus('next...');
        var data = await postJson('/guide/next', {{ session_id: sessionId }});
        setDebug(data);
        if (!data.success) {{
          setStatus('error');
          appendChat('system', 'Next failed: ' + (data.error || 'unknown'));
          return;
        }}

        if (data.status === 'completed') {{
          document.getElementById('summary').textContent = data.summary || '(empty)';
          updateSessionHeader({{ session_id: sessionId, current_index: '-', progress: 100 }});
          updateButtons({{ canStart: false, canNext: false, canFix: false }});
          appendChat('system', data.message || 'Completed.');
          setStatus('completed');
          return;
        }}

        document.getElementById('viewer').srcdoc = data.html || '';
        updateSessionHeader({{ session_id: sessionId, current_index: data.current_index, progress: data.progress }});
        updateButtons({{ canStart: false, canNext: true, canFix: true }});
        appendChat('system', data.message || 'Next.');
        setStatus('learning');
      }} catch (e) {{
        setStatus('error');
        appendChat('system', 'Next error: ' + String(e));
      }}
    }}

    async function sendChat() {{
      if (!sessionId) return;
      var input = document.getElementById('chatInput');
      var message = (input && input.value) ? input.value.trim() : '';
      if (!message) return;
      try {{
        appendChat('user', message);
        if (input) input.value = '';
        setStatus('thinking...');
        var data = await postJson('/guide/chat', {{ session_id: sessionId, message: message }});
        setDebug(data);
        appendChat('assistant', data.answer || '(empty)');
        setStatus('learning');
      }} catch (e) {{
        setStatus('error');
        appendChat('system', 'Chat error: ' + String(e));
      }}
    }}

    async function fixHtml() {{
      if (!sessionId) return;
      var input = document.getElementById('bugInput');
      var bug = (input && input.value) ? input.value.trim() : '';
      if (!bug) return;
      try {{
        setStatus('fixing...');
        var data = await postJson('/guide/fix_html', {{ session_id: sessionId, bug_description: bug }});
        setDebug(data);
        if (data.success && data.html) {{
          document.getElementById('viewer').srcdoc = data.html;
          appendChat('system', 'HTML updated.');
        }} else {{
          appendChat('system', 'Fix failed: ' + (data.error || 'unknown'));
        }}
        setStatus('learning');
      }} catch (e) {{
        setStatus('error');
        appendChat('system', 'Fix error: ' + String(e));
      }}
    }}

    async function reloadSession() {{
      if (!sessionId) {{
        appendChat('system', 'No sessionId to reload.');
        return;
      }}
      try {{
        setStatus('reloading...');
        var data = await getJson('/guide/session/' + sessionId);
        setDebug(data);
        updateKnowledgePoints(data.knowledge_points || []);
        updateSessionHeader({{
          session_id: data.session_id,
          current_index: data.current_index,
          progress: data.status === 'completed' ? 100 : (data.current_index >= 0 ? Math.floor((data.current_index / (data.knowledge_points.length || 1)) * 100) : 0)
        }});
        if (data.status === 'completed') {{
          document.getElementById('summary').textContent = data.summary_markdown || '(empty)';
          updateButtons({{ canStart: false, canNext: false, canFix: false }});
          setStatus('completed');
        }} else if (data.status === 'learning') {{
          document.getElementById('viewer').srcdoc = data.current_html || '';
          updateButtons({{ canStart: false, canNext: true, canFix: true }});
          setStatus('learning');
        }} else {{
          updateButtons({{ canStart: true, canNext: false, canFix: false }});
          setStatus('initialized');
        }}
      }} catch (e) {{
        setStatus('error');
        appendChat('system', 'Reload error: ' + String(e));
      }}
    }}

    document.addEventListener('DOMContentLoaded', function () {{
      var btnCreate = document.getElementById('btnCreate');
      var btnStart = document.getElementById('btnStart');
      var btnNext = document.getElementById('btnNext');
      var btnChat = document.getElementById('btnChat');
      var btnFix = document.getElementById('btnFix');
      var btnReload = document.getElementById('btnReload');
      var chatInput = document.getElementById('chatInput');

      if (btnCreate) btnCreate.addEventListener('click', createSession);
      if (btnStart) btnStart.addEventListener('click', startLearning);
      if (btnNext) btnNext.addEventListener('click', nextKnowledge);
      if (btnChat) btnChat.addEventListener('click', sendChat);
      if (btnFix) btnFix.addEventListener('click', fixHtml);
      if (btnReload) btnReload.addEventListener('click', reloadSession);

      if (chatInput) {{
        chatInput.addEventListener('keydown', function (e) {{
          if (e.key === 'Enter') sendChat();
        }});
      }}

      setStatus('idle');
      updateButtons({{ canStart: false, canNext: false, canFix: false }});
      appendChat('system', 'Ready. Dummy Transformer records are pre-filled. Click Create Session.');
    }});
  }})();
  </script>
</body>
</html>"""
    return HTMLResponse(html)


@app.post("/guide/create_session")
async def create_session(req: CreateSessionRequest):
    notebook_id = req.notebook_id or "cross_notebook"
    notebook_name = req.notebook_name or f"Cross-notebook ({len(req.records)} records)"
    return await manager.create_session(notebook_id=notebook_id, notebook_name=notebook_name, records=req.records)


@app.post("/guide/start")
async def start(req: SessionRequest):
    return await manager.start(session_id=req.session_id)


@app.post("/guide/next")
async def next_(req: SessionRequest):
    return await manager.next(session_id=req.session_id)


@app.post("/guide/chat")
async def chat(req: ChatRequest):
    return await manager.chat(session_id=req.session_id, message=req.message)


@app.post("/guide/fix_html")
async def fix_html(req: FixHtmlRequest):
    return await manager.fix_html(session_id=req.session_id, bug_description=req.bug_description)


@app.get("/guide/session/{session_id}")
async def get_session(session_id: str):
    session = manager.get_session(session_id=session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/guide/session/{session_id}/html")
async def get_html(session_id: str):
    html = manager.get_current_html(session_id=session_id)
    if html is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"html": html}
