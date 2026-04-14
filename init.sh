#!/bin/bash
# code-rag-mcp 초기 셋업
# - Python 3.10+ 확인 및 자동 설치 (Homebrew)
# - venv 생성
# - requirements.txt 설치 (해시 비교로 멱등)
# - Jina 임베딩 모델 가중치 다운로드 프리워밍
#
# 사용법:
#   ./init.sh

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# 런타임 데이터 디렉토리 (venv, chroma_db 등)
# 플러그인 모드에서는 $CLAUDE_PLUGIN_DATA (업데이트에도 유지되는 영구 저장소)
# standalone 모드에서는 $DIR (기존 동작)
DATA_DIR="${CLAUDE_PLUGIN_DATA:-$DIR}"
mkdir -p "$DATA_DIR"

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
# venv 생성
# ─────────────────────────────────────────────
if [ ! -d "$DATA_DIR/venv" ]; then
    echo "가상환경을 생성합니다..."
    "$PYTHON_CMD" -m venv "$DATA_DIR/venv"
    if [ $? -ne 0 ]; then
        echo "가상환경 생성 실패"
        exit 1
    fi
fi

# ─────────────────────────────────────────────
# requirements 설치 (해시 변경 시에만)
# ─────────────────────────────────────────────
if [ -f "$DIR/requirements.txt" ]; then
    REQ_HASH=$(md5 -q "$DIR/requirements.txt" 2>/dev/null || md5sum "$DIR/requirements.txt" | cut -d' ' -f1)
    INSTALLED_HASH=""
    if [ -f "$DATA_DIR/venv/.req_hash" ]; then
        INSTALLED_HASH=$(cat "$DATA_DIR/venv/.req_hash")
    fi

    if [ "$REQ_HASH" != "$INSTALLED_HASH" ]; then
        echo "패키지를 설치합니다..."
        "$DATA_DIR/venv/bin/pip" install -r "$DIR/requirements.txt"
        if [ $? -ne 0 ]; then
            echo "패키지 설치 실패"
            exit 1
        fi
        echo "$REQ_HASH" > "$DATA_DIR/venv/.req_hash"
        echo "패키지 설치 완료!"
    fi
fi

# ─────────────────────────────────────────────
# Jina 임베딩 모델 가중치 다운로드 프리워밍
# - 최초 1회: HuggingFace에서 ~3GB 다운로드 → ~/.cache/huggingface/
# - 이후: 캐시 hit으로 즉시 종료 (모델을 메모리에 보관하진 않음)
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# chroma_db 마이그레이션 (캐시 → 영구 저장소)
# 이전 버전에서 캐시 디렉토리에 저장된 chroma_db를
# ~/.code-rag-mcp/chroma_db로 이관한다.
# ─────────────────────────────────────────────
PERSISTENT_DATA="$HOME/.code-rag-mcp"
mkdir -p "$PERSISTENT_DATA"

if [ -d "$DIR/chroma_db" ] && [ ! -d "$PERSISTENT_DATA/chroma_db" ]; then
    echo "기존 인덱스 데이터를 영구 저장소로 이관합니다..."
    mv "$DIR/chroma_db" "$PERSISTENT_DATA/chroma_db"
    echo "  → $PERSISTENT_DATA/chroma_db 로 이관 완료"
fi

MODEL_MARKER="$DATA_DIR/venv/.model_warmed"
if [ ! -f "$MODEL_MARKER" ]; then
    echo "임베딩 모델 가중치를 다운로드합니다 (최초 1회, 수 분 소요)..."
    "$DATA_DIR/venv/bin/python" - <<'PY'
import sys
try:
    from sentence_transformers import SentenceTransformer
    SentenceTransformer("jinaai/jina-code-embeddings-1.5b")
    print("  → 모델 가중치 캐시 완료")
except Exception as e:
    print(f"  ⚠ 모델 다운로드 실패: {e}", file=sys.stderr)
    sys.exit(1)
PY
    if [ $? -ne 0 ]; then
        echo "모델 다운로드 실패. 네트워크를 확인하고 ./init.sh를 다시 실행하세요."
        exit 1
    fi
    touch "$MODEL_MARKER"
fi

echo ""
echo "✓ 초기 셋업 완료!"
echo "  서버 시작: ./start.sh"
