"""Owner-operated PRIVATE_LEAD qualification. Synthetic prompts; private receipts only."""

import argparse
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "src"))
from common import Refused, atomic, canonical, load_settings, verify_release
from lifecycle import PrivateLeadLifecycle


def synthetic_words(target):
    # A leading-space ASCII word is one token for the pinned Qwen tokenizer.
    return " x" * target


def stream(url, payload, timeout=900):
    request = urllib.request.Request(
        url,
        data=canonical(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    first = None
    text = []
    usage = {}
    tool_call_received = False
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            for raw in reply:
                if not raw.startswith(b"data: "):
                    continue
                data = raw[6:].strip()
                if data == b"[DONE]":
                    break
                item = json.loads(data)
                choices = item.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    chunk = (
                        delta.get("content")
                        or delta.get("reasoning")
                        or delta.get("reasoning_content")
                        or ""
                    )
                    if delta.get("tool_calls"):
                        tool_call_received = True
                        if first is None:
                            first = time.monotonic()
                    if chunk and first is None:
                        first = time.monotonic()
                    text.append(chunk)
                if item.get("usage"):
                    usage = item["usage"]
    except Exception:
        raise Refused("benchmark_transport") from None
    end = time.monotonic()
    if first is None:
        raise Refused("benchmark_no_first_token")
    return {
        "ttft_seconds": first - started,
        "total_seconds": end - started,
        "decode_seconds": max(end - first, 0.001),
        "text": "".join(text),
        "usage": usage,
        "tool_call_received": tool_call_received,
    }


def remote_snapshot(lifecycle, state):
    cmd = "nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu --format=csv,noheader; awk '/MemAvailable/{print $2}' /proc/meminfo; df -B1 /workspace | tail -1"
    try:
        return lifecycle.provider.ssh(
            state["pod_id"], state["host"], state["port"], cmd, timeout=20
        ).decode(errors="replace")[:4096]
    except Exception:
        return "unavailable"


def runtime_facts(lifecycle, state):
    log = "/workspace/sanctum/releases/private-lead-qwen35-122b-nvfp4-candidate-v1/logs/vllm.log"
    cmd = (
        "grep -E \"Using '.*' NvFp4|Using AttentionBackend|Loading weights took|Model loading took|GPU KV cache size|Maximum concurrency|torch.compile took|warmup run took|Application startup complete\" "
        + log
        + " | tail -n 40"
    )
    try:
        return lifecycle.provider.ssh(
            state["pod_id"], state["host"], state["port"], cmd, timeout=20
        ).decode(errors="replace")[:8192]
    except Exception:
        return "unavailable"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", action="store_true")
    p.add_argument("--long-context", action="store_true")
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    verify_release()
    if not a.run:
        raise Refused("benchmark_requires_explicit_run")
    s = load_settings()
    cfg = s["private_lead"]
    if not cfg.get("enabled"):
        raise Refused("private_lead_disabled")
    # Qualification is an explicit owner operation, not gateway autostart.
    original = cfg["auto_start"]
    cfg["auto_start"] = True
    lc = PrivateLeadLifecycle(s)
    scope = "b" * 32
    began = time.time()
    pulse_stop = threading.Event()
    pulse = None
    balance_before = None
    active_seconds = 0.0
    report = {
        "schema": "sanctum-private-lead-stage-b/v1",
        "release_id": cfg["release_id"],
        "model": cfg["model"],
        "revision": cfg["revision"],
        "image": cfg["image"],
        "quantization": cfg["quantization"],
        "launch": {
            "max_model_len": cfg["max_model_len"],
            "moe_backend": cfg["moe_backend"],
            "attention_backend": cfg["attention_backend"],
            "kv_cache_dtype": cfg["kv_cache_dtype"],
            "reasoning_parser": cfg["reasoning_parser"],
            "tool_parser": cfg["tool_parser"],
        },
        "started_at": began,
        "measurements": [],
        "failures": [],
    }
    try:
        account = lc.provider.call("user")
        balance_before = account.get("clientBalance")
        lc.acquire(scope)

        def heartbeat():
            while not pulse_stop.wait(10):
                try:
                    lc.heartbeat(scope)
                except Exception:
                    return

        pulse = threading.Thread(target=heartbeat, daemon=True)
        pulse.start()
        lc.ensure_ready(scope)
        state = lc.state()
        report["ready_at"] = time.time()
        report["readiness_elapsed_seconds"] = report["ready_at"] - began
        report["ready_state"] = lc.status()
        report["resources_ready"] = remote_snapshot(lc, state)
        report["runtime_facts"] = runtime_facts(lc, state)
        cases = [
            ("small", 256, 128),
            ("8k", 8192, 128),
            ("32k", 32000, 128),
            ("sustained_decode", 1024, 512),
        ]
        if a.long_context:
            cases.append(("64k_optional", 65536, 64))
        for name, tokens, out in cases:
            for repetition in range(3):
                instruction = (
                    " Output exactly 512 occurrences of the word TOKEN separated by single spaces."
                    if name == "sustained_decode"
                    else " Reply with a concise synthetic acknowledgement."
                )
                payload = {
                    "model": cfg["alias"],
                    "messages": [
                        {
                            "role": "user",
                            "content": synthetic_words(tokens) + instruction,
                        }
                    ],
                    "temperature": 0,
                    "max_tokens": out,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                }
                item = stream(
                    "http://127.0.0.1:"
                    + str(cfg["local_port"])
                    + "/v1/chat/completions",
                    payload,
                )
                active_seconds += item["total_seconds"]
                u = item.pop("usage")
                completion = int(u.get("completion_tokens", 0))
                prompt = int(u.get("prompt_tokens", 0))
                item.update(
                    {
                        "case": name,
                        "repetition": repetition,
                        "prompt_tokens": prompt,
                        "completion_tokens": completion,
                        "decode_tokens_per_second": completion / item["decode_seconds"],
                        "prompt_tokens_per_second": prompt
                        / max(item["ttft_seconds"], 0.001),
                    }
                )
                item.pop("text", None)
                report["measurements"].append(item)
        # Tool-formatted and repeated-turn checks deliberately carry no private content.
        tool = {
            "type": "function",
            "function": {
                "name": "synthetic_lookup",
                "description": "synthetic test only",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }
        tool_result = stream(
            "http://127.0.0.1:" + str(cfg["local_port"]) + "/v1/chat/completions",
            {
                "model": cfg["alias"],
                "messages": [
                    {
                        "role": "user",
                        "content": "Call synthetic_lookup with query benchmark.",
                    }
                ],
                "tools": [tool],
                "tool_choice": "required",
                "max_tokens": 128,
                "stream": True,
                "stream_options": {"include_usage": True},
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        active_seconds += tool_result["total_seconds"]
        report["tool_formatted_response"] = {
            "received": tool_result["tool_call_received"],
            "ttft_seconds": tool_result["ttft_seconds"],
        }
        report["repeated_turns"] = []
        for turn in range(10):
            x = stream(
                "http://127.0.0.1:" + str(cfg["local_port"]) + "/v1/chat/completions",
                {
                    "model": cfg["alias"],
                    "messages": [
                        {
                            "role": "user",
                            "content": "Synthetic repeated turn "
                            + str(turn)
                            + "; reply READY.",
                        }
                    ],
                    "temperature": 0,
                    "max_tokens": 16,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
                timeout=120,
            )
            active_seconds += x["total_seconds"]
            report["repeated_turns"].append(
                {
                    "turn": turn,
                    "ttft_seconds": x["ttft_seconds"],
                    "total_seconds": x["total_seconds"],
                }
            )
        report["resources_final"] = remote_snapshot(lc, lc.state())
        sustained = [
            x["decode_tokens_per_second"]
            for x in report["measurements"]
            if x["case"] == "sustained_decode"
        ]
        report["sustained_decode_tokens_per_second_min"] = min(sustained)
        report["hard_gate_passed"] = min(sustained) >= 10
        report["target_met"] = min(sustained) >= 20
    except (Exception, KeyboardInterrupt) as e:
        report["failures"].append(str(e) if type(e) is Refused else "benchmark_failed")
        report["hard_gate_passed"] = False
    finally:
        pulse_stop.set()
        if pulse:
            pulse.join(timeout=1)
        try:
            lc.release(scope, close=True)
            lc.release(scope)
            lc.sweep(immediate=True)
            report["cleanup_state"] = lc.status()
        except Exception as e:
            report["failures"].append(
                "cleanup_" + (str(e) if type(e) is Refused else "failed")
            )
        try:
            balance_after = lc.provider.call("user").get("clientBalance")
            if type(balance_before) in [int, float] and type(balance_after) in [
                int,
                float,
            ]:
                report["provider_balance_delta_usd"] = max(
                    0, balance_before - balance_after
                )
        except Exception:
            pass
        cfg["auto_start"] = original
        report["ended_at"] = time.time()
        report["elapsed_seconds"] = report["ended_at"] - began
        report["measured_inference_active_seconds"] = active_seconds
        rate = (report.get("ready_state") or report.get("cleanup_state") or {}).get(
            "hourly_usd", 0
        )
        report["estimated_actual_usd"] = rate * report["elapsed_seconds"] / 3600
        out = a.output or Path(s["state_directory"]) / "private-lead" / "receipts" / (
            "qualification-" + str(time.time_ns()) + ".json"
        )
        out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic(out, canonical(report).encode())
        print(
            canonical(
                {
                    "receipt": str(out),
                    "hard_gate_passed": report["hard_gate_passed"],
                    "cleanup_phase": report.get("cleanup_state", {}).get("phase"),
                }
            )
        )
    return 0 if report["hard_gate_passed"] and not report["failures"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Refused as e:
        raise SystemExit("REFUSED: " + str(e))
