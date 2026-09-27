#!/usr/bin/env bash
set -euo pipefail
umask 077
BASE=/workspace/sanctum/releases/private-lead-qwen35-122b-nvfp4-candidate-v1
VLLM="$BASE/venvs/vllm-0.20.1/bin/vllm"
CACHE=/workspace/sanctum/huggingface/private-lead-qwen35-122b-nvfp4-candidate-v1
MODEL=nvidia/Qwen3.5-122B-A10B-NVFP4
REVISION=98915d837c4e7c87ac8296d02e89de19b3207e6d
ALIAS=sanctum-private-lead-qwen35-122b
mkdir -p "$BASE/logs" "$BASE/pids" "$CACHE" /tmp/spl
chmod 700 "$BASE" "$BASE/logs" "$BASE/pids" "$CACHE"
# Match the two reviewed configure.py bindings, with one sufficiently large GPU.
# Fail closed on command errors, malformed inventory and multi-GPU allocations.
GPU_INFO="$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)" || exit 31
printf '%s\n' "$GPU_INFO" | awk -F ',[[:space:]]*' '
  NF == 2 && $2 ~ /^[0-9]+ MiB$/ {
    if ($1 == "NVIDIA RTX PRO 6000 Blackwell Server Edition" && $2 + 0 >= 90000) valid = 1
    if ($1 == "NVIDIA B200" && $2 + 0 >= 170000) valid = 1
  }
  END { exit !(NR == 1 && valid) }
' || exit 31
if [ -f "$BASE/pids/vllm.pid" ]; then
  PID="$(cat "$BASE/pids/vllm.pid")"
  if kill -0 "$PID" 2>/dev/null && ps -p "$PID" -o args= | grep -Fq -- "$REVISION"; then exit 0; fi
  rm -f "$BASE/pids/vllm.pid"
fi
export HF_HOME="$CACHE" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TMPDIR=/tmp/spl
# The pinned NVFP4 path uses CUTLASS, not DeepGEMM. On B200, vLLM 0.20.1's
# optional FP8 warmup probes an unavailable DeepGEMM API before checking layers.
# Disable that backend explicitly, including when inherited environment enables it.
export VLLM_USE_DEEP_GEMM=0
"$VLLM" serve "$MODEL" --revision "$REVISION" --host 127.0.0.1 --port 8000 \
  --served-model-name "$ALIAS" --tensor-parallel-size 1 --language-model-only \
  --quantization modelopt_fp4 --moe-backend cutlass --attention-backend TRITON_ATTN \
  --kv-cache-dtype fp8 --gpu-memory-utilization 0.92 \
  --max-model-len 32768 --max-num-seqs 1 --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder --reasoning-parser qwen3 --no-enable-log-requests \
  --disable-log-stats --enable-prefix-caching \
  > "$BASE/logs/vllm.log" 2>&1 < /dev/null &
PID=$!
printf '%s\n' "$PID" > "$BASE/pids/vllm.pid"
sleep 3
kill -0 "$PID" || exit 34
