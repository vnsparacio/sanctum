#!/usr/bin/env bash
set -euo pipefail
umask 077
CACHE=/workspace/sanctum/huggingface/private-lead-qwen35-122b-nvfp4-candidate-v1
PYTHON=/workspace/sanctum/releases/private-lead-qwen35-122b-nvfp4-candidate-v1/venvs/vllm-0.20.1/bin/python
MODEL=nvidia/Qwen3.5-122B-A10B-NVFP4
REVISION=98915d837c4e7c87ac8296d02e89de19b3207e6d
MARKER="$CACHE/.sanctum-exact-revision"
mkdir -p "$CACHE"
chmod 700 "$CACHE"
if [ -f "$MARKER" ] && [ "$(cat "$MARKER")" = "$MODEL@$REVISION" ]; then
  if HF_HOME="$CACHE" HF_HUB_OFFLINE=1 HF_HUB_DISABLE_XET=1 "$PYTHON" - "$MODEL" "$REVISION" "$CACHE" <<'PY'
from huggingface_hub import snapshot_download
from pathlib import Path
from safetensors import safe_open
import sys
p=Path(snapshot_download(repo_id=sys.argv[1],revision=sys.argv[2],local_files_only=True,max_workers=1))
cache=Path(sys.argv[3]).resolve()
shards=sorted(p.glob('*.safetensors'))
if not shards:
    raise SystemExit(42)
bad=[]
for shard in shards:
    try:
        with safe_open(shard,framework='pt') as f:
            next(iter(f.keys()),None)
    except Exception:
        bad.append(shard)
for shard in bad:
    target=shard.resolve(strict=True)
    if cache not in target.parents:
        raise SystemExit(43)
    if shard.is_symlink():
        shard.unlink()
    target.unlink(missing_ok=True)
if bad:
    raise SystemExit(44)
PY
  then
    exit 0
  fi
  rm -f "$MARKER"
fi
HF_HOME="$CACHE" HF_HUB_DISABLE_XET=1 "$PYTHON" - "$MODEL" "$REVISION" <<'PY'
from huggingface_hub import snapshot_download
from pathlib import Path
from safetensors import safe_open
import sys
p=Path(snapshot_download(repo_id=sys.argv[1],revision=sys.argv[2],max_workers=1))
if p.name != sys.argv[2]:
    raise SystemExit(41)
shards=sorted(p.glob('*.safetensors'))
if not shards:
    raise SystemExit(42)
for shard in shards:
    with safe_open(shard,framework='pt') as f:
        next(iter(f.keys()),None)
PY
printf '%s@%s\n' "$MODEL" "$REVISION" > "$MARKER"
