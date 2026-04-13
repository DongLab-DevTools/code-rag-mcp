#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${CLAUDE_PLUGIN_DATA:-$DIR}"
cd "$DIR" && source "$DATA_DIR/venv/bin/activate" && python analysis/indexer.py "$@"
