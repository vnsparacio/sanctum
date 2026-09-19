"""Pinned OCI command runner for untrusted repository code."""

import base64
import binascii
import hashlib
import hmac
import io
import os
import re
import selectors
import signal
import subprocess
import tarfile
import time
import uuid
from pathlib import Path

from common import BASE, Refused, canonical, strict_json
from workspace import _real_directory

MAX_OUTPUT = 65536
MAX_TIMEOUT = 300
SAFE_OPERATION = {"status", "diff", "test", "lint", "build"}


def _descriptor():
    value = strict_json((BASE / "runtime/work-runner.json").read_text())
    if value.get("schema") != "sanctum-work-runner/v1":
        raise Refused("runner_descriptor")
    return value


def _profile(settings, name):
    path = Path(settings["work_mode"]["profile_file"])
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise Refused("work_profile_permissions")
    value = strict_json(path.read_text())
    profile = value.get("profiles", {}).get(name)
    if type(profile) is not dict:
        raise Refused("work_profile_unknown")
    return profile, value


def _docker_env(profile):
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "HOME": "/nonexistent",
        "DOCKER_HOST": profile["docker_host"],
    }


def _call(docker, args, profile, timeout=20, check=True):
    try:
        r = subprocess.run(
            [docker, *args],
            env=_docker_env(profile),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        raise Refused("runner_unavailable") from None
    if check and r.returncode:
        raise Refused("runner_unavailable")
    return r


def verify_runner(settings, profile_name):
    descriptor = _descriptor()
    profile, _ = _profile(settings, profile_name)
    docker = profile["docker_path"]
    if not Path(docker).is_absolute() or Path(docker).is_symlink():
        raise Refused("runner_binary")
    image = profile["runner_image"]
    expected = profile["runner_image_id"]
    result = _call(docker, ["image", "inspect", "--format", "{{.Id}}", image], profile)
    if result.stdout.strip() != expected or not expected.startswith("sha256:"):
        raise Refused("runner_image_drift")
    return {
        "image": image,
        "image_id": expected,
        "policy_digest": hashlib.sha256(
            canonical(descriptor["policy"]).encode()
        ).hexdigest(),
    }


def _copy_acceptance_driver(docker, name, profile):
    # Exactly two trusted assets, with explicit container ownership/mode.
    # Installed host assets are 0600; Docker cp would otherwise retain that
    # mode while changing ownership to root, making them unreadable to the runner.
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for asset in ("protected-test-driver.cjs", "protected-test-preload.cjs"):
            path = BASE / "runtime" / asset
            if path.is_symlink():
                raise Refused("runner_driver")
            raw = path.read_bytes()
            info = tarfile.TarInfo(asset)
            info.size = len(raw)
            info.mode = 0o444
            info.uid = info.gid = 0
            archive.addfile(info, io.BytesIO(raw))
    result = subprocess.run(
        [docker, "cp", "-", name + ":/sanctum-acceptance"],
        env=_docker_env(profile),
        input=stream.getvalue(),
        capture_output=True,
        timeout=20,
    )
    if result.returncode:
        raise Refused("runner_driver")


def run(
    settings, profile_name, workspace, operation, now=time.monotonic, *, acceptance=None
):
    if operation not in SAFE_OPERATION:
        raise Refused("runner_operation")
    root = _real_directory(workspace)
    descriptor = _descriptor()
    profile, _ = _profile(settings, profile_name)
    argv = profile.get("operations", {}).get(operation)
    if "," in str(root):
        raise Refused("workspace_path")
    if (
        type(argv) is not list
        or not argv
        or any(type(x) is not str or not x or len(x) > 256 for x in argv)
    ):
        raise Refused("runner_operation")
    proof_key = None
    if acceptance is not None:
        from task_evidence import unrestricted_contract, validate_contract

        contract = unrestricted_contract()
        contract["protected"] = [e["path"] for e in acceptance["entries"]]
        contract["acceptance"] = acceptance
        validate_contract(contract)
        argv = [
            "node",
            "/sanctum-acceptance/protected-test-driver.cjs",
            canonical(acceptance["entries"]),
        ]
        proof_key = os.urandom(32)
    identity = verify_runner(settings, profile_name)
    policy = descriptor["policy"]
    docker = profile["docker_path"]
    timeout = min(
        int(profile.get("timeout_seconds", policy["timeout_seconds"])), MAX_TIMEOUT
    )
    name = "sanctum-work-" + uuid.uuid4().hex
    runner_user = profile.get("runner_user")
    if type(runner_user) is not str or not re.fullmatch(
        r"[1-9][0-9]{0,9}:[1-9][0-9]{0,9}", runner_user
    ):
        raise Refused("runner_identity")
    args = [
        "create",
        "--name",
        name,
        "--rm",
        "--platform",
        profile.get("platform", "linux/arm64"),
        "--user",
        runner_user,
        "--network",
        "none",
        "--cpus",
        str(policy["cpus"]),
        "--memory",
        str(policy["memory_bytes"]),
        "--memory-swap",
        str(policy["memory_bytes"]),
        "--pids-limit",
        str(policy["pids"]),
        "--ulimit",
        f"nofile={policy['open_files']}:{policy['open_files']}",
        "--ulimit",
        f"fsize={policy['file_bytes']}:{policy['file_bytes']}",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        f"/tmp:rw,noexec,nosuid,nodev,size={policy['tmp_bytes']}",
        "--mount",
        "type=volume,destination=/workspace,volume-nocopy",
        "--workdir",
        "/workspace",
        "--env",
        "HOME=/nonexistent",
        "--env",
        "LANG=C.UTF-8",
        "--env",
        "LC_ALL=C.UTF-8",
        "--env",
        "PATH=/usr/local/bin:/usr/bin:/bin",
        identity["image"],
        *argv,
    ]
    if acceptance is not None:
        args[1:1] = [
            "--interactive",
            "--mount",
            "type=volume,destination=/sanctum-acceptance,volume-nocopy",
        ]
    started = now()
    created = False
    try:
        _call(docker, args, profile, timeout=30)
        created = True
        # Docker Desktop cannot reliably bind nested APFS sparse-image mounts.
        # Copy a point-in-time workspace snapshot into the stopped container;
        # repository code receives no live host mount and all changes vanish.
        _call(
            docker, ["cp", str(root) + "/.", name + ":/workspace"], profile, timeout=120
        )
        if acceptance is not None:
            _copy_acceptance_driver(docker, name, profile)
        child = subprocess.Popen(
            [
                docker,
                "start",
                "--attach",
                *(["--interactive"] if acceptance is not None else []),
                name,
            ],
            env=_docker_env(profile),
            stdin=subprocess.PIPE if acceptance is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        if acceptance is not None:
            child.stdin.write(proof_key.hex().encode() + b"\n")
            child.stdin.close()
    except Exception:
        if created:
            _call(docker, ["rm", "-f", name], profile, timeout=20, check=False)
        raise Refused("runner_unavailable") from None
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ, "stdout")
    selector.register(child.stderr, selectors.EVENT_READ, "stderr")
    output = bytearray()
    proof_output = bytearray()
    code = "COMMAND_FAILED"
    unknown = False
    try:
        while child.poll() is None:
            if now() - started > timeout:
                code = "COMMAND_TIMEOUT"
                unknown = True
                break
            for key, _ in selector.select(0.1):
                chunk = os.read(key.fileobj.fileno(), 8192)
                output.extend(chunk)
                if key.data == "stderr":
                    proof_output.extend(chunk)
                if len(output) > MAX_OUTPUT:
                    code = "OUTPUT_LIMIT"
                    unknown = True
                    break
            if unknown:
                break
        if unknown:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _call(docker, ["rm", "-f", name], profile, timeout=20, check=False)
            try:
                child.wait(timeout=5)
            except Exception:
                pass
        else:
            child.wait(timeout=5)
            for label, stream in (("stdout", child.stdout), ("stderr", child.stderr)):
                chunk = stream.read(MAX_OUTPUT - len(output) + 1)
                output.extend(chunk)
                if label == "stderr":
                    proof_output.extend(chunk)
            if len(output) > MAX_OUTPUT:
                code = "OUTPUT_LIMIT"
                unknown = True
            else:
                code = "OK" if child.returncode == 0 else "COMMAND_FAILED"
    finally:
        selector.close()
        child.stdout.close()
        child.stderr.close()
    absent = (
        _call(docker, ["inspect", name], profile, timeout=10, check=False).returncode
        != 0
    )
    if not absent:
        raise Refused("runner_cleanup_uncertain")
    elapsed = now() - started
    raw = bytes(output[:MAX_OUTPUT])
    result = {
        "ok": code == "OK",
        "code": code,
        "executionState": "COMPLETION_UNKNOWN" if unknown else "COMPLETED",
        "output": raw.decode("utf-8", "replace"),
        "output_digest": hashlib.sha256(raw).hexdigest(),
        "output_bytes": len(raw),
        "elapsed_ms": round(elapsed * 1000, 3),
        "runner": identity,
        "limits": policy,
        "container_absent": absent,
    }

    if acceptance is not None:
        try:
            if proof_output.count(b"SANCTUM_PROTECTED_PROOF_V1 ") != 1:
                raise ValueError()
            frames = re.findall(
                rb"(?:^|\n)SANCTUM_PROTECTED_PROOF_V1 ([A-Za-z0-9+/]+={0,2}) ([0-9a-f]{64})(?=\n|$)",
                bytes(proof_output),
            )
            if len(frames) != 1:
                raise ValueError()
            payload = base64.b64decode(frames[0][0], validate=True)
            if not hmac.compare_digest(
                hmac.new(proof_key, payload, hashlib.sha256).hexdigest().encode(),
                frames[0][1],
            ):
                raise ValueError()
            proof = strict_json(payload.decode())
            if (
                type(proof) is not dict
                or set(proof)
                != {"schema", "executed", "passed", "observed", "failures", "skipped"}
                or proof["schema"] != "sanctum-protected-test-run/v1"
                or any(type(proof[k]) is not bool for k in ("executed", "passed"))
                or any(
                    type(proof[k]) is not int or proof[k] < 0
                    for k in ("observed", "failures", "skipped")
                )
            ):
                raise ValueError()
            result["protected_execution"] = proof
            result["ok"] = result["ok"] and proof["executed"] and proof["passed"]
        except (ValueError, Refused, UnicodeDecodeError, binascii.Error):
            result["ok"] = False
            result["protected_execution"] = {
                "schema": "sanctum-protected-test-run/v1",
                "executed": False,
                "passed": False,
                "observed": 0,
                "failures": 1,
                "skipped": 0,
            }
        if not result["ok"] and result["code"] == "OK":
            result["code"] = "PROTECTED_TEST_NOT_EXECUTED"
    return result
