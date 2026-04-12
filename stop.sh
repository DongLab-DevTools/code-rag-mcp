#!/bin/bash
# 안드로이드 집사 로컬 서버 종료

stopped=false

if [ -f /tmp/butler-slack.pid ]; then
    PID=$(cat /tmp/butler-slack.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "슬랙 봇 종료 (PID: $PID)"
        stopped=true
    fi
    rm -f /tmp/butler-slack.pid
fi

if [ -f /tmp/butler-api.pid ]; then
    PID=$(cat /tmp/butler-api.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "API 서버 종료 (PID: $PID)"
        stopped=true
    fi
    rm -f /tmp/butler-api.pid
fi

# PID 파일 없이 실행 중인 프로세스 정리
if pgrep -f "server/api_server.py" > /dev/null 2>&1; then
    pkill -f "server/api_server.py"
    echo "API 서버 종료 (프로세스 탐색)"
    stopped=true
fi

if pgrep -f "server/slack_bot.py" > /dev/null 2>&1; then
    pkill -f "server/slack_bot.py"
    echo "슬랙 봇 종료 (프로세스 탐색)"
    stopped=true
fi

if [ "$stopped" = true ]; then
    echo ""
    echo "안드로이드 집사 종료 완료!"
else
    echo "실행 중인 서버가 없습니다."
fi
