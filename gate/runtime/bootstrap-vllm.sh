#!/usr/bin/env bash
set -euo pipefail
umask 077
# Phase10 repair of the validated v1.4 bootstrap. Never relocate a populated venv.
BASE=/workspace/vinceai
VENV="$BASE/venvs/vllm-0.13.0"
mkdir -p "$BASE/venvs" "$BASE/logs" "$BASE/pids" "$BASE/huggingface" "$BASE/tmp"
chmod 700 "$BASE" "$BASE/pids" "$BASE/logs"
nvidia-smi --query-gpu=name --format=csv,noheader | grep -q 'RTX PRO 6000' || exit 31
if ! "$VENV/bin/python" -c 'import vllm; assert vllm.__version__ == "0.13.0"' 2>/dev/null; then
  python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install --upgrade pip
  "$VENV/bin/python" -m pip install --no-cache-dir 'vllm==0.13.0'
fi
# Regenerate entry points if a legacy .tmp shebang survived; preserve weight cache.
if [ "$(head -n 1 "$VENV/bin/vllm" 2>/dev/null || true)" != "#!$VENV/bin/python" ] || ! "$VENV/bin/vllm" --version >/dev/null 2>&1; then
  "$VENV/bin/python" -m pip install --force-reinstall --no-deps 'vllm==0.13.0'
fi
[ "$(head -n 1 "$VENV/bin/vllm")" = "#!$VENV/bin/python" ] || exit 35
"$VENV/bin/python" -c 'import vllm; assert vllm.__version__ == "0.13.0"'
"$VENV/bin/vllm" --version >/dev/null
printf 'vllm=0.13.0\n' > "$VENV/.vinceai-ready"
if [ -f "$BASE/pids/vllm.pid" ]; then
  PID="$(cat "$BASE/pids/vllm.pid")"
  if kill -0 "$PID" 2>/dev/null; then
    if ps -p "$PID" -o args= | grep -q 'vllm.*serve.*RedHatAI/Qwen3-Next-80B'; then
      if ps -p "$PID" -o args= | grep -q '\.tmp/'; then
        # Replace only our legacy server after its launcher has been repaired.
        kill "$PID"
        for attempt in $(seq 1 30); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
        kill -0 "$PID" 2>/dev/null && exit 36
      else
        exit 0
      fi
    fi
    # A persistent PID file can refer to a different process in a new container.
    # Discard only our stale record; never kill the unrelated process.
    rm -f "$BASE/pids/vllm.pid"
  fi
fi
export HF_HOME="$BASE/huggingface" TMPDIR="$BASE/tmp"
nohup "$VENV/bin/vllm" serve RedHatAI/Qwen3-Next-80B-A3B-Instruct-quantized.w4a16 \
  --host 127.0.0.1 --port 8000 --served-model-name vinceai-qwen80b \
  --max-model-len 32768 --gpu-memory-utilization 0.90 --disable-log-requests \
  > "$BASE/logs/vllm.log" 2>&1 < /dev/null &
PID=$!
printf '%s\n' "$PID" > "$BASE/pids/vllm.pid"
sleep 3
kill -0 "$PID" || exit 34
# No Pod control-plane credentials or unverified self-delete watchdog.
