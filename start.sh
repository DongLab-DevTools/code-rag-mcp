#!/bin/bash
# code-rag-mcp 로컬 서버 시작
# 사용법:
#   ./start.sh        백그라운드 실행
#   ./start.sh --log  포그라운드 실행 (로그 실시간 출력, Ctrl+C로 종료)

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# ─────────────────────────────────────────────
# 초기 셋업 (Python/venv/requirements/모델)
# ─────────────────────────────────────────────
"$DIR/init.sh" || exit 1

# .env 파일 로드
if [ -f "$DIR/.env" ]; then
    export $(grep -v '^#' "$DIR/.env" | xargs)
fi

LOG_MODE=false
if [ "$1" = "--log" ] || [ "$1" = "-l" ]; then
    LOG_MODE=true
fi

# 이미 실행 중인지 확인
if pgrep -f "server/api_server.py" > /dev/null 2>&1; then
    echo "이미 실행 중입니다. 종료 후 다시 시작하려면: ./stop.sh"
    exit 1
fi

# 환경변수 확인
HAS_SLACK=true
if [ -z "$SLACK_BOT_TOKEN" ] || [ -z "$SLACK_APP_TOKEN" ]; then
    echo "슬랙 토큰이 설정되지 않았습니다."
    echo "  .env 파일에 SLACK_BOT_TOKEN, SLACK_APP_TOKEN을 설정하세요."
    echo ""
    echo "API 서버만 시작합니다..."
    HAS_SLACK=false
fi

VENV_PYTHON="$DIR/venv/bin/python"
export PYTHONUNBUFFERED=1

# ─────────────────────────────────────────────
# 포그라운드 모드 (--log)
# ─────────────────────────────────────────────
if [ "$LOG_MODE" = true ]; then
    cleanup() {
        echo ""
        echo "종료 중..."
        kill $API_PID 2>/dev/null
        kill $SLACK_PID 2>/dev/null
        wait $API_PID 2>/dev/null
        wait $SLACK_PID 2>/dev/null
        echo "code-rag-mcp 종료 완료!"
        exit 0
    }
    trap cleanup SIGINT SIGTERM

    # API 서버 시작 (로그 → 터미널)
    "$VENV_PYTHON" "$DIR/server/api_server.py" 2>&1 | sed 's/^/[API] /' &
    API_PID=$!

    echo "API 서버 시작 중..."
    for i in $(seq 1 120); do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "[API] 서버 준비 완료 (PID: $API_PID)"
            break
        fi
        sleep 1
    done

    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "[API] 서버 시작 실패"
        kill $API_PID 2>/dev/null
        exit 1
    fi

    # 슬랙 봇 시작 (로그 → 터미널)
    if [ "$HAS_SLACK" = true ]; then
        CODE_RAG_API_URL="http://localhost:8000" "$VENV_PYTHON" "$DIR/server/slack_bot.py" 2>&1 | sed 's/^/[SLACK] /' &
        SLACK_PID=$!
        sleep 3
        if kill -0 "$SLACK_PID" 2>/dev/null; then
            echo "[SLACK] 봇 준비 완료 (PID: $SLACK_PID)"
        else
            echo "[SLACK] 봇 시작 실패"
        fi
    fi

    echo ""
    echo "code-rag-mcp 시작 완료! (Ctrl+C로 종료)"
    echo "──────────────────────────────────────"

    # 포그라운드 유지
    wait

# ─────────────────────────────────────────────
# 백그라운드 모드 (기본)
# ─────────────────────────────────────────────
else
    # API 서버 시작
    "$VENV_PYTHON" "$DIR/server/api_server.py" > /tmp/code-rag-api.log 2>&1 &
    API_PID=$!
    echo "$API_PID" > /tmp/code-rag-api.pid

    echo "API 서버 시작 중..."
    for i in $(seq 1 120); do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "API 서버 실행 중 (PID: $API_PID)"
            break
        fi
        sleep 1
    done

    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "API 서버 시작 실패. 로그: /tmp/code-rag-api.log"
        exit 1
    fi

    # 슬랙 봇 시작
    if [ "$HAS_SLACK" = true ]; then
        CODE_RAG_API_URL="http://localhost:8000" "$VENV_PYTHON" "$DIR/server/slack_bot.py" > /tmp/code-rag-slack.log 2>&1 &
        SLACK_PID=$!
        echo "$SLACK_PID" > /tmp/code-rag-slack.pid
        sleep 3

        if kill -0 "$SLACK_PID" 2>/dev/null; then
            echo "슬랙 봇 실행 중 (PID: $SLACK_PID)"
        else
            echo "슬랙 봇 시작 실패. 로그: /tmp/code-rag-slack.log"
        fi
    fi

    echo ""
    echo "code-rag-mcp 시작 완료!"
    echo "  API: http://localhost:8000"
    echo "  API 문서: http://localhost:8000/docs"
    echo "  로그 보기: tail -f /tmp/code-rag-api.log /tmp/code-rag-slack.log"
    echo "  종료: ./stop.sh"
fi
