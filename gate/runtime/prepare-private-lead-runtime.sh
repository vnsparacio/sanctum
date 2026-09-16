#!/usr/bin/env bash
set -euo pipefail
umask 077
BASE=/workspace/sanctum/releases/private-lead-qwen35-122b-nvfp4-candidate-v1
VENV="$BASE/venvs/vllm-0.20.1"
mkdir -p "$BASE/venvs" "$BASE/tmp"
chmod 700 "$BASE" "$BASE/venvs"
if ! "$VENV/bin/python" -c 'import vllm; assert vllm.__version__ == "0.20.1"' 2>/dev/null; then
  python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install --upgrade pip
  "$VENV/bin/python" -m pip install --no-cache-dir 'vllm==0.20.1'
fi
"$VENV/bin/python" -c 'import vllm; assert vllm.__version__ == "0.20.1"'
"$VENV/bin/vllm" --version
