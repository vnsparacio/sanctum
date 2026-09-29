"""One bounded Qwen Code headless run inside the Mac-owned Work Mode task."""

import base64
import io
import json
import os
import re
import select
import signal
import subprocess
import tarfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import qwen_snapshot
import task_evidence
from command_runner import _call, _docker_env, _remove_container, verify_runner
from common import BASE, Refused, atomic, canonical
from lifecycle import PrivateLeadLifecycle

SCHEMA = "sanctum-qwen-run/v1"
QWEN_USER = 65532
MAX_GOAL = 32768
MAX_MODEL_CALLS = 48
MAX_INFERENCE_SECONDS = 900
MAX_RUN_SECONDS = 2400
CLEANUP_SECONDS = 120
MAX_REQUEST = 2 * 1024 * 1024
MAX_RESPONSE = 16 * 1024 * 1024


def _private_write(path, raw):
    atomic(path, raw if isinstance(raw, bytes) else raw.encode())


def _image(profile):
    image = profile.get("qwen_runner_image")
    expected = profile.get("qwen_runner_image_id")
    if (
        type(image) is not str
        or not re.fullmatch(r"sanctum-qwen-code:[A-Za-z0-9_.-]{1,32}", image)
        or type(expected) is not str
        or not re.fullmatch(r"sha256:[a-f0-9]{64}", expected)
    ):
        raise Refused("qwen_runner_identity")
    result = _call(
        profile["docker_path"],
        ["image", "inspect", "--format", "{{.Id}}", image],
        profile,
    )
    if result.stdout.strip() != expected:
        raise Refused("qwen_runner_image_drift")
    return image


def _tar_bytes(files):
    """Copy fixed private files with container ownership; no host mount or chown."""
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, raw, mode in files:
            if not name or name.startswith("/") or ".." in name.split("/"):
                raise Refused("qwen_copy_path")
            info = tarfile.TarInfo(name)
            info.uid = info.gid = QWEN_USER
            info.mode = mode
            if raw is None:
                info.type = tarfile.DIRTYPE
                info.size = 0
                archive.addfile(info)
            else:
                info.size = len(raw)
                archive.addfile(info, io.BytesIO(raw))
    return output.getvalue()


def _copy_tar(docker, name, destination, profile, files):
    try:
        result = subprocess.run(
            [docker, "cp", "-", name + ":" + destination],
            input=_tar_bytes(files),
            env=_docker_env(profile),
            capture_output=True,
            timeout=120,
        )
    except Exception:
        raise Refused("qwen_container_copy") from None
    if result.returncode:
        raise Refused("qwen_container_copy")


def _snapshot_files(root):
    rows = task_evidence.inventory(root)
    if any(row["kind"] not in ("file", "directory") for row in rows.values()):
        raise Refused("qwen_snapshot_type")
    files = []
    for path, row in sorted(
        rows.items(), key=lambda item: (item[0].count("/"), item[0])
    ):
        if row["kind"] == "directory":
            files.append((path, None, 0o755))
            continue
        raw = qwen_snapshot._file(root, path, row)
        files.append((path, raw, 0o755 if row["mode"] & 0o111 else 0o644))
    return files


def _settings(model):
    return {
        "context": {
            "autoCompactThreshold": 0.6,
            "clearContextOnIdle": {
                "toolResultsNumToKeep": 1,
                "toolResultsTotalCharsThreshold": 12000,
            },
        },
        "model": {"skipLoopDetection": True},
        "modelProviders": {
            "openai": [
                {
                    "id": model,
                    "envKey": "OPENAI_API_KEY",
                    "baseUrl": "http://127.0.0.1:38080/v1",
                    "generationConfig": {
                        "contextWindowSize": 32768,
                        "maxRetries": 0,
                        "samplingParams": {"max_tokens": 4096},
                    },
                }
            ]
        },
        "telemetry": {"enabled": False},
    }


def _model_reply(item, model, port, remaining):
    if set(item) != {"id", "method", "path", "body"} or type(item["id"]) is not int:
        raise Refused("qwen_broker_protocol")
    route, method = item["path"], item["method"]
    if (route, method) not in (("/v1/models", "GET"), ("/v1/chat/completions", "POST")):
        raise Refused("qwen_broker_route")
    try:
        body = base64.b64decode(item["body"], validate=True)
    except Exception:
        raise Refused("qwen_broker_protocol") from None
    if len(body) > MAX_REQUEST or (method == "GET" and body):
        raise Refused("qwen_broker_limit")
    if method == "POST":
        try:
            value = json.loads(body)
        except Exception:
            raise Refused("qwen_broker_protocol") from None
        if type(value) is not dict or value.get("model") != model:
            raise Refused("qwen_model_identity")
    request = urllib.request.Request(
        "http://127.0.0.1:" + str(port) + route,
        data=body if method == "POST" else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        try:
            response = urllib.request.build_opener(
                urllib.request.ProxyHandler({})
            ).open(request, timeout=remaining)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.status
            content_type = response.headers.get("Content-Type", "application/json")
            raw = response.read(MAX_RESPONSE + 1)
    except Exception:
        raise Refused("qwen_model_transport") from None
    if len(raw) > MAX_RESPONSE:
        raise Refused("qwen_broker_limit")
    return {
        "id": item["id"],
        "status": status,
        "content_type": (
            "text/event-stream"
            if content_type.startswith("text/event-stream")
            else "application/json"
        ),
        "body": base64.b64encode(raw).decode(),
    }


def _broker_loop(child, trace, model, port, deadline, progress):
    calls = 0
    inference = 0.0
    done = None
    while time.monotonic() < deadline - CLEANUP_SECONDS:
        ready, _, _ = select.select([child.stdout], [], [], 2)
        if not ready:
            if child.poll() is not None:
                break
            continue
        line = child.stdout.readline(MAX_REQUEST * 2 + 1)
        if not line:
            break
        if len(line) > MAX_REQUEST * 2:
            raise Refused("qwen_broker_limit")
        try:
            item = json.loads(line)
        except Exception:
            raise Refused("qwen_broker_protocol") from None
        if item.get("done") is True:
            done = item
            break
        calls += 1
        if calls > MAX_MODEL_CALLS:
            raise Refused("qwen_model_call_limit")
        progress["modelCalls"] = calls
        remaining = min(
            240,
            MAX_INFERENCE_SECONDS - inference,
            deadline - CLEANUP_SECONDS - time.monotonic(),
        )
        if remaining <= 0:
            raise Refused("qwen_inference_limit")
        started = time.monotonic()
        try:
            reply = _model_reply(item, model, port, remaining)
        finally:
            inference += time.monotonic() - started
            progress["inferenceSeconds"] = inference
        trace.write(canonical({"request": item, "reply": reply}) + "\n")
        trace.flush()
        child.stdin.write(canonical(reply) + "\n")
        child.stdin.flush()
    if done is None:
        raise Refused(
            "qwen_outer_wall"
            if time.monotonic() >= deadline - CLEANUP_SECONDS
            else "qwen_broker_exit"
        )
    return {
        "modelCalls": calls,
        "inferenceSeconds": inference,
        "headlessExitCode": done.get("code"),
        "headlessSignal": done.get("signal"),
    }


def run(settings, record, profile, goal, lifecycle=None):
    reviewed_limits = {
        "qwen_model_calls": MAX_MODEL_CALLS,
        "qwen_tool_calls": 40,
        "qwen_wall_seconds": 1200,
        "qwen_outer_seconds": MAX_RUN_SECONDS,
        "qwen_retries": 0,
        "max_gpu_seconds": 2700,
        "max_cost_usd": 10,
    }
    if (
        profile.get("engine") != "qwen_code"
        or profile.get("reviewer") is False
        or profile.get("stages")
        or type(goal) is not str
        or not goal.strip()
        or len(goal.encode()) > MAX_GOAL
        or any(profile.get(key) != value for key, value in reviewed_limits.items())
    ):
        raise Refused("qwen_profile_contract")
    # The task's existing fixed command image remains a separate identity.
    verify_runner(settings, record["profile"])
    image = _image(profile)
    snapshot = qwen_snapshot.export(settings, record)
    directory = Path(snapshot["input"]).parent
    docker = profile["docker_path"]
    model = settings["private_lead"]["alias"]
    port = settings["private_lead"]["local_port"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", model):
        raise Refused("qwen_model_identity")
    lc = lifecycle or PrivateLeadLifecycle(settings)
    preflight = lc.provider.preflight()
    hourly = preflight.get("hourly_usd")
    cap = min(float(profile.get("max_cost_usd", 1.5)), 50.0)
    if (
        preflight.get("available") is not True
        or type(hourly) not in (int, float)
        or not 0 < hourly <= settings["private_lead"]["max_hourly_usd"]
        or not 0 < cap <= 50
    ):
        raise Refused("qwen_price_or_capacity")
    started = time.monotonic()
    deadline = started + min(MAX_RUN_SECONDS, cap * 3600 / hourly)
    if deadline - started < CLEANUP_SECONDS + 60:
        raise Refused("qwen_cost_budget")
    name = "sanctum-qwen-work-" + uuid.uuid4().hex
    created = False
    child = None
    child_stderr = None
    leased = False
    stop = threading.Event()
    heartbeat = None
    outcome = {
        "schema": SCHEMA,
        "taskId": record["workspace_id"],
        "code": "QWEN_NOT_STARTED",
    }
    progress = {"modelCalls": 0, "inferenceSeconds": 0.0}
    _private_write(directory / "qwen-goal.txt", goal)
    previous_term = signal.getsignal(signal.SIGTERM)

    def cancelled(_signum, _frame):
        raise Refused("qwen_owner_cancelled")

    signal.signal(signal.SIGTERM, cancelled)
    try:
        _call(
            docker,
            [
                "create",
                "--name",
                name,
                "--interactive",
                "--rm",
                "--platform",
                profile.get("platform", "linux/arm64"),
                "--user",
                f"{QWEN_USER}:{QWEN_USER}",
                "--network",
                "none",
                "--cpus",
                "2",
                "--memory",
                "4294967296",
                "--memory-swap",
                "4294967296",
                "--pids-limit",
                "64",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--ulimit",
                "fsize=16777216:16777216",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=268435456",
                "--tmpfs",
                f"/home/qwen:rw,nosuid,nodev,size=268435456,uid={QWEN_USER},gid={QWEN_USER}",
                "--mount",
                "type=volume,destination=/workspace",
                "--mount",
                "type=volume,destination=/poc",
                "--mount",
                "type=volume,destination=/evidence",
                "--env",
                "QWEN_MODEL=" + model,
                image,
                "sleep",
                "infinity",
            ],
            profile,
            timeout=30,
        )
        created = True
        _copy_tar(
            docker,
            name,
            "/workspace",
            profile,
            _snapshot_files(Path(snapshot["input"])),
        )
        _copy_tar(
            docker,
            name,
            "/poc",
            profile,
            [
                (
                    "broker.mjs",
                    (BASE / "runtime/qwen-headless-broker.mjs").read_bytes(),
                    0o444,
                ),
                (
                    "qwen-request-policy.mjs",
                    (BASE / "runtime/qwen-request-policy.mjs").read_bytes(),
                    0o444,
                ),
                ("prompt.txt", goal.encode(), 0o444),
                ("settings.json", (canonical(_settings(model)) + "\n").encode(), 0o444),
            ],
        )
        _call(docker, ["start", name], profile, timeout=30)
        lc.acquire(record["workspace_id"])
        leased = True
        lc.resume()

        def pulse():
            while not stop.wait(10):
                try:
                    lc.heartbeat(record["workspace_id"])
                except Exception:
                    return

        heartbeat = threading.Thread(target=pulse, daemon=True)
        heartbeat.start()
        lc.ensure_ready(record["workspace_id"], explicit=True)
        if time.monotonic() >= deadline - CLEANUP_SECONDS:
            raise Refused("qwen_outer_wall")
        child_stderr = (directory / "qwen-docker-stderr.txt").open("xb")
        os.fchmod(child_stderr.fileno(), 0o600)
        child = subprocess.Popen(
            [
                docker,
                "exec",
                "--interactive",
                "--user",
                f"{QWEN_USER}:{QWEN_USER}",
                name,
                "node",
                "/poc/broker.mjs",
            ],
            env=_docker_env(profile),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=child_stderr,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        with (directory / "qwen-broker-events.jsonl").open("x") as trace:
            os.fchmod(trace.fileno(), 0o600)
            metrics = _broker_loop(child, trace, model, port, deadline, progress)
        progress.update({k: metrics[k] for k in ("modelCalls", "inferenceSeconds")})
        child.wait(timeout=10)
        if child.returncode:
            raise Refused("qwen_broker_exit")
        if metrics.get("headlessExitCode", 0) != 0 or metrics.get("headlessSignal") is not None:
            raise Refused("qwen_headless_failed")
        outcome.update({"code": "QWEN_HEADLESS_COMPLETE"})
    except Refused as error:
        outcome["code"] = str(error)
    except Exception:
        outcome["code"] = "qwen_environment_failure"
    finally:
        outcome.update(progress)
        stop.set()
        if heartbeat:
            heartbeat.join(timeout=1)
        if child and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        if child_stderr:
            child_stderr.close()
        if created:
            for source, target in (
                ("/workspace/.", "qwen-output"),
                ("/evidence/.", "qwen-trace"),
            ):
                dest = directory / target
                dest.mkdir(mode=0o700, exist_ok=True)
                try:
                    _call(
                        docker,
                        ["cp", name + ":" + source, str(dest)],
                        profile,
                        timeout=45,
                    )
                except Refused:
                    outcome["copyFailure"] = target
            try:
                _call(docker, ["rm", "-fv", name], profile, timeout=10, check=False)
            except Refused:
                pass
            absent = _remove_container(docker, name, profile)
            outcome["containerAbsent"] = absent
            if absent is not True:
                outcome["code"] = "qwen_container_cleanup_uncertain"
        if leased:
            try:
                lc.release(record["workspace_id"])
                lc.sweep()
            except Exception:
                outcome["code"] = "qwen_gpu_release_uncertain"
        signal.signal(signal.SIGTERM, previous_term)
    if outcome.get("code") == "QWEN_HEADLESS_COMPLETE" and not outcome.get(
        "copyFailure"
    ):
        try:
            imported = qwen_snapshot.import_output(settings, record)
            if imported.get("ok") is not True:
                outcome["code"] = imported.get("code", "qwen_import_denied")
            else:
                outcome["code"] = "OK"
                outcome["importReceipt"] = imported["receipt"]
        except Refused as error:
            outcome["code"] = str(error)
    outcome["elapsedSeconds"] = time.monotonic() - started
    outcome["estimatedCostUsd"] = outcome["elapsedSeconds"] * hourly / 3600
    _private_write(directory / "qwen-run-result.json", canonical(outcome) + "\n")
    return {"ok": outcome["code"] == "OK", **outcome}
