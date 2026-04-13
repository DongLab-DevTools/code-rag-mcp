#!/bin/bash
# code-rag-mcp 로컬 서버 종료

stopped=false

if [ -f /tmp/code-rag-slack.pid ]; then
    PID=$(cat /tmp/code-rag-slack.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "슬랙 봇 종료 (PID: $PID)"
        stopped=true
    fi
    rm -f /tmp/code-rag-slack.pid
fi

if [ -f /tmp/code-rag-api.pid ]; then
    PID=$(cat /tmp/code-rag-api.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "API 서버 종료 (PID: $PID)"
        stopped=true
    fi
    rm -f /tmp/code-rag-api.pid
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
    echo "code-rag-mcp 종료 완료!"
else
    echo "실행 중인 서버가 없습니다."
fi
