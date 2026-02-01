# Portable Guided Learning (Guide) Blueprint

이 폴더는 DeepTutor의 **Guided Learning(Guide)** 기능을 다른 프로젝트로 “이식”할 수 있도록, 필요한 워크플로우/데이터 계약/구현 노하우를 **폴더 내부만 보고도** 재구현할 수 있게 정리한 문서 + 최소 레퍼런스 구현(Python)입니다.

> 목표: 다른 프로젝트에 `portable_guide/`를 그대로 복사한 뒤, 이 폴더의 내용만 읽고 **Guide 학습 기능**(학습 플랜 생성 → 인터랙티브 학습 페이지 → Q&A → 다음 지식 포인트 → 요약)을 구현할 수 있게 하기.

---

## 1) Guide 기능이 “뭐가 다른가”

일반 챗봇과 달리 Guide는 다음을 “세트”로 제공합니다:

1. **학습 플랜 생성(지식 포인트 분해/정렬)**  
   사용자의 노트/기록(질문+답변)을 분석해서 학습 가능한 단위(knowledge points)로 쪼개고, **기초→심화 순서로 정렬**합니다.
2. **지식 포인트별 학습 화면(Interactive HTML)**  
   현재 지식 포인트를 시각화/인터랙션 가능한 HTML로 만들어 오른쪽 패널(iframe 등)에 띄웁니다.
3. **지식 포인트 컨텍스트 기반 Q&A(Chat)**  
   현재 지식 포인트 + 해당 지식 포인트에서의 대화 이력만을 중심 컨텍스트로 답합니다.
4. **명시적 진행(Next 버튼 등)**  
   “사용자가 다음으로 넘어가겠다”는 명시적 신호로 지식 포인트를 전환합니다.
5. **완주 요약(Summary)**  
   전체 지식 포인트 + 대화 이력 기반으로 학습 리포트를 생성합니다.

이 폴더의 레퍼런스 구현은 위 5가지를 최소 단위로 묶어 제공합니다.

---

## 2) 핵심 워크플로우(Backend 관점)

### 상태 머신

- `initialized`: 세션 생성 완료(학습 플랜만 있음)
- `learning`: 특정 지식 포인트를 학습 중(HTML + Q&A 가능)
- `completed`: 모든 지식 포인트 학습 완료(요약 생성)

### API/호출 흐름 (권장)

1. `create_session(records)`  
   - 입력: 사용자가 선택한 기록(여러 노트/노트북에서 가져온 기록을 합쳐도 됨)
   - 출력: `knowledge_points[]`(학습 플랜), `session_id`
2. `start(session_id)`  
   - 1번째 지식 포인트의 HTML 생성, 상태를 `learning`으로 전환
3. 반복
   - `chat(session_id, message)` : 현재 지식 포인트 컨텍스트로 Q&A
   - `fix_html(session_id, bug_description)` : HTML 문제 설명을 주면 해당 지식 포인트 HTML 재생성(버그 수정)
   - `next(session_id)` : 다음 지식 포인트로 전환(마지막이면 요약 생성 후 `completed`)

이식 구현에서 **가장 중요한 포인트는 “세션 상태(진행도, 현재 지식 포인트, 대화 이력)가 영속 저장”**되는 것입니다. 서버가 재시작되어도 재개 가능해야 합니다.

---

## 3) 입력 데이터 계약(Records)

Guide는 “노트북/노트/기록”이라는 저장소가 무엇이든 상관없고, 아래처럼 **학습 기록 배열(records)**만 받으면 됩니다.

최소 필수 필드:

```json
{
  "id": "rec_123",
  "type": "solve | question | research | co_writer | ...",
  "title": "짧은 제목",
  "user_query": "사용자 입력/질문",
  "output": "시스템 답변/결과"
}
```

권장:
- `output`이 너무 길면(예: 2k~5k chars 이상) **truncate**하여 Locate 단계 입력 길이를 관리
- `type`은 필수는 아니지만 플랜 생성 품질이 좋아짐(어떤 종류의 기록인지 힌트)

---

## 4) 세션 데이터 계약(GuideSession)

레퍼런스 구현의 세션 JSON은 대략 아래 구조를 가집니다:

```json
{
  "session_id": "a1b2c3d4",
  "notebook_id": "cross_notebook",
  "notebook_name": "Cross-Notebook (3 notebooks, 12 records)",
  "created_at": 1730000000.0,

  "status": "initialized | learning | completed",
  "knowledge_points": [
    { "knowledge_title": "...", "knowledge_summary": "...", "user_difficulty": "..." }
  ],
  "current_index": 0,

  "chat_history": [
    { "role": "system|user|assistant", "content": "...", "knowledge_index": 0, "timestamp": 1730000001.0 }
  ],

  "current_html": "<!DOCTYPE html> ...",
  "summary_markdown": "# Learning Summary ..."
}
```

핵심은:
- `knowledge_index`로 메시지를 지식 포인트에 “귀속”시켜서, ChatAgent에 **현재 포인트의 대화만** 컨텍스트로 공급 가능
- `current_html`을 세션에 저장해 “현재 화면”을 즉시 복원 가능

---

## 5) Agents 설계(LLM 프롬프트/출력 계약)

Guide는 4개 에이전트를 사용합니다.

### (A) LocateAgent (학습 플랜 생성)
- 입력: `records[]`, `notebook_name`
- 출력: `knowledge_points[]` (기초→심화 순서)
- 구현 포인트
  - 출력은 “완벽한 JSON”이 깨질 수 있으니 파싱을 견고하게(리트라이/후처리)
  - 가능하면 LLM의 `response_format`(JSON 강제)을 지원하는 프로바이더/모델을 사용

### (B) InteractiveAgent (HTML 생성/수정)
- 입력: `knowledge_point`
- 출력: **완전한 HTML 문서 문자열**
- 구현 포인트
  - LLM이 ```html code fences```로 감싸는 경우가 흔하므로 HTML 추출 로직이 필요
  - HTML이 깨지면 fallback 템플릿으로라도 “보여줄 것”을 확보(UX 안정성)

### (C) ChatAgent (현재 지식 포인트 Q&A)
- 입력: `knowledge_point` + `chat_history(current_index)` + `user_question`
- 출력: Markdown 답변
- 구현 포인트
  - 현재 포인트의 대화만 넣고(또는 최근 N개만) 컨텍스트를 작게 유지
  - “정답 제공 + 사고 유도” 톤 유지(학습형 답변)

### (D) SummaryAgent (완주 요약)
- 입력: `knowledge_points[]` + 전체 `chat_history`
- 출력: Markdown 리포트
- 구현 포인트
  - 반드시 “구체적”이어야 함(지식 포인트 제목, 실제 질문 인용 등)

프롬프트 샘플은 `portable_guide/prompts/en/*.yaml`에 포함되어 있습니다.

---

## 6) API 계약(권장)

아래는 “이식하기 쉬운” 최소 REST 계약입니다. (FastAPI 예시는 `portable_guide/examples/fastapi_app.py` 참고)

- `POST /guide/create_session`
  - body: `{ "records": [ ... ], "notebook_id": "optional" }`
  - resp: `{ "success": true, "session_id": "...", "knowledge_points": [...], "total_points": 4 }`

- `POST /guide/start`
  - body: `{ "session_id": "..." }`
  - resp: `{ "success": true, "current_index": 0, "current_knowledge": {...}, "html": "<!DOCTYPE...>", "progress": 0 }`

- `POST /guide/next`
  - body: `{ "session_id": "..." }`
  - resp(learning): `{ "success": true, "current_index": 1, "html": "...", "progress": 25 }`
  - resp(completed): `{ "success": true, "status": "completed", "summary": "..." }`

- `POST /guide/chat`
  - body: `{ "session_id": "...", "message": "..." }`
  - resp: `{ "success": true, "answer": "..." }`

- `POST /guide/fix_html`
  - body: `{ "session_id": "...", "bug_description": "..." }`
  - resp: `{ "success": true, "html": "..." }`

- `GET /guide/session/{session_id}`
- `GET /guide/session/{session_id}/html`

---

## 7) Frontend 구현 노하우(최소)

가장 흔한 UI는:
- 좌측: 채팅 + 진행 버튼(Start/Next)
- 우측: HTML iframe(지식 포인트 학습 화면)

### iframe 렌더링 권장
- `srcdoc`로 HTML 주입
- sandbox는 최소 권한 권장:
  - 기본: `sandbox="allow-scripts"` (가능하면 `allow-same-origin`은 피하기)
  - 필요 시만 권한 추가
- 외부 리소스 로딩을 막고 싶다면:
  - CSP 메타를 HTML에 주입하거나
  - HTML을 서버에서 rewrite/sanitize하는 파이프라인을 추가

### 수학식(LaTeX/KaTeX)
- HTML에 `$...$`, `$$...$$` 형태로 넣고, 호스트 앱에서 KaTeX 렌더를 주입하는 방식이 안전/안정적입니다.
- (레거시 방식) HTML이 자체적으로 CDN KaTeX를 로드하게 만들면 오프라인/보안 제약에서 문제가 생길 수 있습니다.

---

## 8) 운영/품질 노하우(실전)

1. **Locate는 비용이 크다**  
   - records truncation, 요약 전처리, 캐시를 적극 사용
2. **HTML 생성 실패 대비(fallback)**  
   - LLM 출력이 깨져도 화면이 비지 않게 템플릿 제공
3. **세션 저장은 원자적으로(atomic)**
   - 파일 저장 시 임시 파일 → rename으로 깨짐 방지
4. **모델/프로바이더 추상화**
   - LLM 클라이언트는 인터페이스로 분리(폴더 내 `llm/` 참고)

---

## 9) 빠른 시작(이식 시)

1. 다른 프로젝트에 `portable_guide/` 폴더를 복사
2. 의존성 설치(예: Python)
   - `pyyaml` (프롬프트 로딩)
   - `httpx` (OpenAI-compatible HTTP 클라이언트 예시)
   - `fastapi`, `uvicorn` (API 예시 실행 시)
   - `python-dotenv` (`.env` 로딩)
   - 참고: `portable_guide/requirements.txt`
3. 환경 변수/설정 준비
   - `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`
   - 필요 시 `LLM_MAX_TOKENS_FIELD` 설정 (`max_tokens` 또는 `max_completion_tokens`)
4. `portable_guide/examples/fastapi_app.py`로 동작 확인

### `.env` 사용

- 예시 파일: `portable_guide/.env.example`
- `.env`는 보통 프로젝트 루트에 둡니다(권장). 예시 코드에서 자동으로 탐색/로드합니다.
  - 특정 경로를 쓰려면 `GUIDE_ENV_PATH`에 `.env` 경로를 지정할 수 있습니다.

### 로컬 데모(네트워크/키 없이)

`FakeLLMClient`를 사용해 워크플로우가 “코드적으로” 동작하는지 확인:

```bash
python portable_guide/examples/demo_cli.py
```

### FastAPI 예시 실행

```bash
pip install fastapi uvicorn pyyaml httpx
GUIDE_FAKE_LLM=1 uvicorn portable_guide.examples.fastapi_app:app --reload
```

브라우저에서 `http://127.0.0.1:8000/ui` 로 UI를 열어 기능을 검증할 수 있습니다.

실제 LLM을 붙이려면 `GUIDE_FAKE_LLM=0`(또는 unset)으로 두고, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`을 설정하세요.

---

## 10) 폴더 구성

필수 로직:
- `portable_guide/manager.py` : 전체 오케스트레이션(세션/진행/호출)
- `portable_guide/storage.py` : 세션 영속 저장(JSON 파일)
- `portable_guide/agents/*` : Locate/Interactive/Chat/Summary
- `portable_guide/prompts/en/*.yaml` : 프롬프트 샘플
- `portable_guide/llm/*` : LLM 클라이언트 인터페이스 + OpenAI-compatible 예시

예시 앱:
- `portable_guide/examples/fastapi_app.py`
- `portable_guide/examples/demo_cli.py`

---

## 11) 다음 단계(당신 프로젝트에 맞게 바꿀 것)

- records를 어디서/어떻게 뽑을지(노트, LMS, 로그, DB 등)
- “Next” 신호를 버튼 외에 어떤 이벤트로 볼지(퀴즈 통과, 숙제 제출 등)
- HTML을 그대로 신뢰할지(iframe sandbox/CSP/정적 컴포넌트 렌더로 제한할지)
- 지식 포인트 수/난이도 자동 조절 규칙

---

## 12) 코드 레퍼런스

레퍼런스 구현은 이 폴더 내 Python 코드로 제공합니다:

- Core: `portable_guide/models.py`, `portable_guide/manager.py`, `portable_guide/storage.py`
- Agents: `portable_guide/agents/locate.py`, `portable_guide/agents/interactive.py`, `portable_guide/agents/chat.py`, `portable_guide/agents/summary.py`
- LLM: `portable_guide/llm/base.py`, `portable_guide/llm/openai_compatible.py`
