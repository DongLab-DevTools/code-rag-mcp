# 안드로이드 집사 슬랙 봇 연동 가이드

> android-butler MCP가 로컬 Claude Code에서 동작하는 상태에서,
> 슬랙 봇을 연동하는 방법입니다.
>
> 로컬에서 테스트하고, 나중에 서버 주소만 바꾸면 됩니다.

---

## 전체 구조

```
[슬랙]  @android-butler 유저 로그인 로직이 어떻게 돼?
          │
          ▼
[슬랙 봇]  slack_bot.py (Socket Mode)
          │
          ├─→ 검색 요청: GET http://localhost:8000/search?q=...
          │         │
          │         ▼
          │   [API 서버]  api_server.py
          │         └─→ search.py → 벡터DB → 관련 코드 반환
          │
          ├─→ 검색 결과를 Claude Code CLI에 전달 → 답변 생성
          │
          └─→ 슬랙에 답변 전송
```

나중에 서버로 옮길 때는 `localhost:8000` → `company-server:8000` 만 변경.

---

## Step 1: 파일 추가 & 패키지 설치

기존 android-butler 디렉토리에 파일 2개를 추가합니다.

```
android-butler/
├── chunker.py          ← 기존
├── indexer.py          ← 기존
├── search.py           ← 기존
├── server.py           ← 기존 (MCP 서버)
├── api_server.py       ← 새로 추가
├── slack_bot.py        ← 새로 추가
└── chroma_db/          ← 기존
```

```bash
cd android-butler
pip install fastapi uvicorn slack-bolt slack-sdk requests
```

---

## Step 2: api_server.py — 검색 API 서버

```python
"""
api_server.py — 검색 API 서버

로컬 테스트: python api_server.py
서버 배포:   python api_server.py --host 0.0.0.0 --port 8000
"""

import argparse
from fastapi import FastAPI, Query
from pydantic import BaseModel
from search import search_code, format_results

app = FastAPI(title="Android Butler API")


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10


class SearchResponse(BaseModel):
    query: str
    total: int
    formatted: str  # Claude에게 넘기기 좋은 포맷


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search", response_model=SearchResponse)
def search_get(q: str = Query(...), top_k: int = Query(10, ge=1, le=20)):
    results = search_code(q, top_k=top_k)
    return SearchResponse(query=q, total=len(results), formatted=format_results(results))


@app.post("/search", response_model=SearchResponse)
def search_post(req: SearchRequest):
    results = search_code(req.query, top_k=min(req.top_k, 20))
    return SearchResponse(query=req.query, total=len(results), formatted=format_results(results))


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"🚀 API 서버: http://{args.host}:{args.port}")
    print(f"   API 문서: http://localhost:{args.port}/docs\n")
    uvicorn.run(app, host=args.host, port=args.port)
```

---

## Step 3: slack_bot.py — 슬랙 봇

```python
"""
slack_bot.py — 안드로이드 집사 슬랙 봇

사용법:
    export SLACK_BOT_TOKEN="xoxb-..."
    export SLACK_APP_TOKEN="xapp-..."
    export BUTLER_API_URL="http://localhost:8000"   ← 나중에 서버 주소로 변경
    python slack_bot.py
"""

import os
import subprocess
import logging
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
BUTLER_API_URL = os.environ.get("BUTLER_API_URL", "http://localhost:8000")
CLAUDE_CLI = os.environ.get("CLAUDE_CLI_PATH", "claude")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = App(token=SLACK_BOT_TOKEN)


# ─────────────────────────────────────────────
# 1) 서버에서 코드 검색
# ─────────────────────────────────────────────

def search_from_server(question: str, top_k: int = 10) -> dict:
    try:
        resp = requests.get(
            f"{BUTLER_API_URL}/search",
            params={"q": question, "top_k": top_k},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        return {"error": f"검색 서버({BUTLER_API_URL})에 연결할 수 없습니다."}
    except requests.Timeout:
        return {"error": "검색 서버 응답 시간 초과"}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# 2) Claude Code CLI로 답변 생성
# ─────────────────────────────────────────────

def generate_answer(question: str, search_results_formatted: str) -> str:
    prompt = f"""아래는 안드로이드 코드베이스에서 검색된 관련 코드입니다.
이 코드를 분석해서 질문에 정확하고 간결하게 답변하세요.
슬랙 메시지이므로 핵심만 전달하세요. 코드 블록은 ```로 감싸세요.
한국어로 답변하세요.

## 검색된 코드

{search_results_formatted}

## 질문

{question}"""

    try:
        result = subprocess.run(
            [CLAUDE_CLI, "--print", "--max-turns", "1", "--message", prompt],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            return f"Claude Code 에러:\n```{result.stderr[:500]}```"
        return result.stdout.strip() or "답변을 생성하지 못했습니다."

    except subprocess.TimeoutExpired:
        return "⏰ 답변 생성에 시간이 너무 오래 걸렸습니다."
    except FileNotFoundError:
        return "❌ `claude` CLI를 찾을 수 없습니다. CLAUDE_CLI_PATH를 확인하세요."
    except Exception as e:
        return f"예외 발생: {str(e)[:200]}"


# ─────────────────────────────────────────────
# 3) 슬랙 이벤트 핸들러
# ─────────────────────────────────────────────

@app.event("app_mention")
def handle_mention(event, say):
    text = event.get("text", "")
    question = text.split(">", 1)[-1].strip() if ">" in text else text.strip()
    thread_ts = event.get("thread_ts") or event.get("ts")

    if not question:
        say(text="질문을 함께 입력해주세요!\n예: `@android-butler 유저 로그인 로직이 어떻게 돼?`", thread_ts=thread_ts)
        return

    logger.info(f"질문: {question}")

    # Step 1: 검색 중 표시
    say(text="🔍 코드베이스에서 관련 코드를 찾고 있습니다...", thread_ts=thread_ts)

    # Step 2: 서버에서 검색
    search_data = search_from_server(question)

    if "error" in search_data:
        say(text=f"❌ 검색 실패: {search_data['error']}", thread_ts=thread_ts)
        return

    if search_data["total"] == 0:
        say(text="관련 코드를 찾지 못했습니다. 질문을 다르게 해보세요.", thread_ts=thread_ts)
        return

    # Step 3: Claude Code CLI로 답변 생성
    answer = generate_answer(question, search_data["formatted"])

    if len(answer) > 3900:
        answer = answer[:3900] + "\n\n_(답변이 길어서 잘렸습니다)_"

    # Step 4: 슬랙에 답변
    say(text=answer, thread_ts=thread_ts)
    logger.info(f"답변 전송 완료 ({len(answer)}자)")


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 안드로이드 집사 슬랙 봇 시작!")
    print(f"   검색 서버: {BUTLER_API_URL}")
    print(f"   Claude CLI: {CLAUDE_CLI}")
    print(f"   종료: Ctrl+C\n")
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
```

---

## Step 4: Slack 앱 만들기

### 4-1. 앱 생성

1. https://api.slack.com/apps → **Create New App** → **From scratch**
2. App Name: `android-butler` → 워크스페이스 선택 → **Create App**

### 4-2. 권한 추가

왼쪽 **OAuth & Permissions** → **Bot Token Scopes**:

| 추가할 Scope | 용도 |
|-------|------|
| `app_mentions:read` | 멘션 감지 |
| `chat:write` | 메시지 전송 |

### 4-3. Socket Mode 활성화

1. 왼쪽 **Socket Mode** → **Enable Socket Mode** ON
2. Token Name: `android-butler-socket` → **Generate**
3. 생성된 `xapp-...` 토큰 복사 → 이게 **SLACK_APP_TOKEN**

### 4-4. 이벤트 구독

1. 왼쪽 **Event Subscriptions** → **Enable Events** ON
2. **Subscribe to bot events** → `app_mention` 추가 → **Save Changes**

### 4-5. 앱 설치

왼쪽 **Install App** → **Install to Workspace** → 허용

**OAuth & Permissions** 페이지에서 `xoxb-...` 토큰 복사 → 이게 **SLACK_BOT_TOKEN**

---

## Step 5: 실행

터미널 3개를 엽니다.

### 터미널 1: API 서버

```bash
cd android-butler
python api_server.py
```

```
🚀 API 서버: http://0.0.0.0:8000
   API 문서: http://localhost:8000/docs
```

### 터미널 2: 슬랙 봇

```bash
cd android-butler
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_APP_TOKEN="xapp-your-token"
export BUTLER_API_URL="http://localhost:8000"
python slack_bot.py
```

```
🤖 안드로이드 집사 슬랙 봇 시작!
   검색 서버: http://localhost:8000
   Claude CLI: claude
   종료: Ctrl+C
```

### 터미널 3: 테스트 (선택)

```bash
# API 서버 동작 확인
curl http://localhost:8000/health

# 검색 테스트
curl "http://localhost:8000/search?q=유저+로그인&top_k=3"
```

### 슬랙에서 테스트

1. 채널에 봇 초대: `/invite @android-butler`
2. 멘션: `@android-butler 유저 로그인 로직이 어떻게 돼?`

---

## 나중에 서버로 옮길 때

바꿀 것은 **환경변수 하나**뿐입니다:

```bash
# 로컬 테스트
export BUTLER_API_URL="http://localhost:8000"

# 사내 서버로 전환
export BUTLER_API_URL="http://company-server:8000"
```

서버에는 `chunker.py`, `indexer.py`, `search.py`, `api_server.py`, `chroma_db/`만 배포하면 됩니다.

---

## 트러블슈팅

| 문제 | 해결 |
|------|------|
| 봇이 응답 없음 | `/invite @android-butler`로 채널에 초대했는지 확인 |
| "검색 서버에 연결할 수 없습니다" | 터미널 1에서 api_server.py가 실행 중인지 확인 |
| "claude: command not found" | `which claude`로 경로 확인 후 `export CLAUDE_CLI_PATH="/경로/claude"` |
| 응답이 느림 (30초+) | 정상입니다. Claude Code CLI 호출에 10-30초 소요 |
| 슬랙 메시지 잘림 | 정상입니다. 4000자 제한으로 자동 잘림 처리됨 |
