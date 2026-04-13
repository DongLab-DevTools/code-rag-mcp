#!/bin/bash
# 안드로이드 집사 로컬 서버 시작
# 사용법:
#   ./start.sh        백그라운드 실행
#   ./start.sh --log  포그라운드 실행 (로그 실시간 출력, Ctrl+C로 종료)

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# ─────────────────────────────────────────────
# Python 설치 확인 및 자동 설치
# ─────────────────────────────────────────────
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" > /dev/null 2>&1; then
        ver=$("$cmd" -c "import sys; print(sys.version_info.minor)")
        if [ "$ver" -ge 10 ] 2>/dev/null; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "⚠ Python 3.10 이상이 설치되어 있지 않습니다."
    if command -v brew > /dev/null 2>&1; then
        echo "Homebrew를 사용하여 Python 3.12를 설치합니다..."
        echo "  (시간이 다소 걸릴 수 있습니다)"
        brew install python@3.12
        if [ $? -ne 0 ]; then
            echo "Python 설치 실패"
            exit 1
        fi
        PYTHON_CMD="python3.12"
        echo "✓ Python 설치 완료!"
    else
        echo "Homebrew가 설치되어 있지 않습니다."
        echo "  먼저 Homebrew를 설치하세요: https://brew.sh"
        echo "  또는 직접 Python 3.10+를 설치하세요: https://www.python.org/downloads/"
        exit 1
    fi
fi

echo "Python: $($PYTHON_CMD --version)"

# ─────────────────────────────────────────────
# venv 생성 및 패키지 설치
# ─────────────────────────────────────────────
if [ ! -d "$DIR/venv" ]; then
    echo "가상환경을 생성합니다..."
    "$PYTHON_CMD" -m venv "$DIR/venv"
fi

if [ -f "$DIR/requirements.txt" ]; then
    # requirements.txt가 변경되었으면 재설치
    REQ_HASH=$(md5 -q "$DIR/requirements.txt" 2>/dev/null || md5sum "$DIR/requirements.txt" | cut -d' ' -f1)
    INSTALLED_HASH=""
    if [ -f "$DIR/venv/.req_hash" ]; then
        INSTALLED_HASH=$(cat "$DIR/venv/.req_hash")
    fi

    if [ "$REQ_HASH" != "$INSTALLED_HASH" ]; then
        echo "패키지를 설치합니다..."
        "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"
        if [ $? -ne 0 ]; then
            echo "패키지 설치 실패"
            exit 1
        fi
        echo "$REQ_HASH" > "$DIR/venv/.req_hash"
        echo "패키지 설치 완료!"
    fi
fi

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
        echo "안드로이드 집사 종료 완료!"
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
        BUTLER_API_URL="http://localhost:8000" "$VENV_PYTHON" "$DIR/server/slack_bot.py" 2>&1 | sed 's/^/[SLACK] /' &
        SLACK_PID=$!
        sleep 3
        if kill -0 "$SLACK_PID" 2>/dev/null; then
            echo "[SLACK] 봇 준비 완료 (PID: $SLACK_PID)"
        else
            echo "[SLACK] 봇 시작 실패"
        fi
    fi

    echo ""
    echo "안드로이드 집사 시작 완료! (Ctrl+C로 종료)"
    echo "──────────────────────────────────────"

    # 포그라운드 유지
    wait

# ─────────────────────────────────────────────
# 백그라운드 모드 (기본)
# ─────────────────────────────────────────────
else
    # API 서버 시작
    "$VENV_PYTHON" "$DIR/server/api_server.py" > /tmp/butler-api.log 2>&1 &
    API_PID=$!
    echo "$API_PID" > /tmp/butler-api.pid

    echo "API 서버 시작 중..."
    for i in $(seq 1 120); do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "API 서버 실행 중 (PID: $API_PID)"
            break
        fi
        sleep 1
    done

    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "API 서버 시작 실패. 로그: /tmp/butler-api.log"
        exit 1
    fi

    # 슬랙 봇 시작
    if [ "$HAS_SLACK" = true ]; then
        BUTLER_API_URL="http://localhost:8000" "$VENV_PYTHON" "$DIR/server/slack_bot.py" > /tmp/butler-slack.log 2>&1 &
        SLACK_PID=$!
        echo "$SLACK_PID" > /tmp/butler-slack.pid
        sleep 3

        if kill -0 "$SLACK_PID" 2>/dev/null; then
            echo "슬랙 봇 실행 중 (PID: $SLACK_PID)"
        else
            echo "슬랙 봇 시작 실패. 로그: /tmp/butler-slack.log"
        fi
    fi

    echo ""
    echo "안드로이드 집사 시작 완료!"
    echo "  API: http://localhost:8000"
    echo "  API 문서: http://localhost:8000/docs"
    echo "  로그 보기: tail -f /tmp/butler-api.log /tmp/butler-slack.log"
    echo "  종료: ./stop.sh"
fi
