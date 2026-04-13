# 안드로이드 집사 (Android Butler) 셋업 가이드

## 사전 준비

- macOS + Homebrew (없으면 Python 3.10+를 직접 설치)
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (슬랙 봇 답변 생성에 필요)

## 1. 설치

```bash
git clone <repo-url> code-rag-mcp
cd code-rag-mcp
./init.sh    # Python/venv/패키지/임베딩 모델까지 자동 셋업
```

`init.sh`는 멱등이므로 재실행해도 안전합니다. requirements.txt 변경 시에만 재설치되고, 모델 다운로드도 최초 1회만 수행됩니다.

## 2. 프로젝트 인덱싱

Claude Code에서 `/project-add`를 실행하면 대화형으로 인덱싱됩니다. 또는 CLI로:

```bash
source venv/bin/activate
python analysis/indexer.py --name 프로젝트이름 /path/to/android-project
```

인덱싱된 프로젝트 확인:
```bash
python analysis/indexer.py --list
```

## 3. MCP 서버 등록 (Claude Code에서 사용 시)

Claude Code에서 아래 명령어로 MCP 서버를 등록합니다:

```bash
claude mcp add android-butler -- $(pwd)/venv/bin/python $(pwd)/server/mcp_server.py
```

## 4. 슬랙 봇 연동 (선택)

### 4-1. Slack 앱 만들기

1. https://api.slack.com/apps → Create New App → From scratch
2. OAuth & Permissions → Bot Token Scopes: `app_mentions:read`, `chat:write`
3. Socket Mode → Enable → 토큰 생성 (xapp-...)
4. Event Subscriptions → Enable → `app_mention` 추가
5. Install App → Install to Workspace → 토큰 복사 (xoxb-...)

### 4-2. 환경변수 설정

`.env` 파일을 프로젝트 루트에 생성:

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
BUTLER_API_URL=http://localhost:8000
```

### 4-3. 실행

```bash
# 백그라운드 실행
./start.sh

# 로그 실시간 출력 모드
./start.sh --log

# 종료
./stop.sh
```

### 4-4. 슬랙에서 테스트

1. 채널에 봇 초대: `/invite @android-butler`
2. 멘션: `@android-butler 로그인 로직이 어떻게 돼?`

## 구조

```
android-butler/
├── analysis/            # 코드 분석
│   ├── chunker.py       # AST 기반 코드 청킹
│   ├── indexer.py       # 임베딩 생성 + 벡터DB 저장
│   └── search.py        # 벡터DB 검색
├── server/              # 서버
│   ├── mcp_server.py    # MCP 서버 (Claude Code 연동)
│   ├── api_server.py    # REST API 서버
│   └── slack_bot.py     # 슬랙 봇
├── chroma_db/           # 벡터DB (자동 생성)
├── .env                 # 슬랙 토큰 (직접 생성)
├── start.sh             # 서버 시작
├── stop.sh              # 서버 종료
└── requirements.txt     # Python 패키지
```
