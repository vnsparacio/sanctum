"""Pinned CLI adapter, reusing the validated runner's GPU/image/cache/SSH contracts.

No volume mutation API is exposed. Allocation errors remain uncertain until reconciled.
"""

import hashlib
import ipaddress
import json
import os
import subprocess
import time
from pathlib import Path

from common import BASE, Refused, atomic, canonical, private_dir, strict_json


def capacity_rejected(args, error):
    return (
        list(args[:2]) == ["pod", "create"]
        and type(error) is dict
        and error.get("code") == "graphql_error"
        and error.get("error")
        == "failed to create pod: graphql error: There are no longer any instances available with the requested specifications. Please refresh and try again."
    )


class Runpod:
    def __init__(self, settings, release_cfg=None):
        self.settings = settings
        self.gpu = release_cfg or settings["gpu"]
        self.inference_release = (
            release_cfg is settings.get("private_lead")
            and release_cfg is not None
            and release_cfg.get("logical_profile") == "PRIVATE_LEAD"
        )
        if (
            type(self.gpu["local_port"]) is not int
            or not 1024 <= self.gpu["local_port"] <= 65535
        ):
            raise Refused("private_port_invalid")
        self.cli = BASE / "runtime/runpodctl"
        self.pin = strict_json((BASE / "runtime/RUNPODCTL.json").read_text())

    def guard_root(self):
        root = Path(self.settings["state_directory"])
        return (
            root / "private-lead"
            if self.gpu.get("logical_profile") == "PRIVATE_LEAD"
            else root
        )

    def ensure_guard(self):
        # Independent Mac supervisor survives the command worker and gateway.
        # It can only sweep known leases/compute; it cannot allocate or infer.
        release = (
            "PRIVATE_LEAD"
            if self.gpu.get("logical_profile") == "PRIVATE_LEAD"
            else "PRIVATE_80B"
        )
        subprocess.Popen(
            [
                self.settings["python"],
                "-B",
                str(BASE / "watch.py"),
                "--release",
                release,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                p = self.guard_root() / "watch.ready"
                if p.is_symlink():
                    raise Refused("unsafe_watch_state")
                d = strict_json(p.read_text())
                os.kill(d["pid"], 0)
                command = subprocess.run(
                    ["/bin/ps", "-p", str(d["pid"]), "-o", "command="],
                    capture_output=True,
                    timeout=2,
                )
                if (
                    time.time() - d["heartbeat"] < 30
                    and str(BASE / "watch.py") in command.stdout.decode()
                ):
                    return
            except (OSError, KeyError, ValueError):
                pass
            time.sleep(0.2)
        raise Refused("mac_guard_not_ready")

    def call(self, *args, timeout=45):
        if tuple(args[:2]) in (("pod", "start"), ("pod", "resume")):
            raise Refused("private_80b_retired")
        if tuple(args[:2]) == ("pod", "create"):
            name = (
                args[args.index("--name") + 1]
                if "--name" in args and args.index("--name") + 1 < len(args)
                else ""
            )
            if not self.inference_release or not name.startswith(
                self.settings["private_lead"]["pod_prefix"]
            ):
                raise Refused("private_80b_retired")
        # Diagnostic-only bound. Cleanup remains callable after expiry; ordinary
        # lifecycle/provider timeouts are untouched when this attribute is absent.
        deadline = getattr(self, "experiment_deadline", None)

        def remaining(cap):
            if deadline is None:
                return cap
            left = deadline - time.time()
            if not getattr(self, "experiment_cleanup", False):
                left -= 120
            if left <= 0:
                if not getattr(self, "experiment_cleanup", False):
                    raise Refused("experiment_deadline")
                return min(cap, 20)
            return min(cap, 20, left)

        if (
            self.cli.is_symlink()
            or hashlib.sha256(self.cli.read_bytes()).hexdigest()
            != self.pin["binary_sha256"]
        ):
            raise Refused("runpod_cli_drift")
        r = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                os.environ.get("USER", "vinceai"),
                "-s",
                self.gpu.get("keychain_item", "VinceAI Runpod API"),
                "-w",
            ],
            capture_output=True,
            timeout=remaining(10),
        )
        key = r.stdout.decode().strip()
        if r.returncode or not key:
            raise Refused("runpod_auth_missing")
        try:
            r = subprocess.run(
                [str(self.cli), *args],
                env={**os.environ, "RUNPOD_API_KEY": key},
                capture_output=True,
                timeout=remaining(timeout),
            )
        except subprocess.TimeoutExpired:
            raise Refused("runpod_request_uncertain") from None
        if r.returncode:
            error = None
            try:
                error = strict_json(r.stderr)
                message = str(error.get("error", "")).replace(key, "[redacted]")[:700]
                # Store only the structured error, never request arguments/env.
                record = (
                    {
                        "operation": list(args[:2]),
                        "code": error.get("code"),
                        "status": error.get("status"),
                        "message": message,
                        "time": time.time(),
                    }
                    if deadline is None
                    else {
                        "code": "EXPERIMENT_PROVIDER_REQUEST_FAILED",
                        "time": time.time(),
                    }
                )
                atomic(
                    Path(self.settings["state_directory"]) / "last-runpod-error.json",
                    canonical(record).encode(),
                )
            except Exception:
                pass
            if capacity_rejected(args, error):
                raise Refused("gpu_capacity_unavailable")
            raise Refused("runpod_request_failed")
        if not r.stdout.strip():
            return None
        if len(r.stdout) > 4000000:
            raise Refused("runpod_response_limit")
        return strict_json(r.stdout)

    def pods(self):
        rows = self.call("pod", "list", "--all")
        if type(rows) is not list:
            raise Refused("runpod_list_shape")
        return rows

    def preflight(self):
        if self.inference_release:
            self.public_key()
        volumes = self.call("network-volume", "list")
        v = next((x for x in volumes if x.get("id") == self.gpu["volume_id"]), None)
        if (
            not v
            or v.get("dataCenterId") != self.gpu["datacenter"]
            or v.get("size", 0) < 150
        ):
            raise Refused("canonical_volume_mismatch")
        rows = self.call("gpu", "list")
        g = next((x for x in rows if x.get("gpuId") == self.gpu["gpu"]), None)
        price = g.get("securePricePerHr") if g else None
        if (
            type(price) not in [int, float]
            or not 0 < price <= self.gpu["max_hourly_usd"]
            or not g.get("secureCloud")
            or g.get("memoryInGb", 0) < 96
        ):
            raise Refused("gpu_price_or_identity")
        account = self.call("user")
        if (
            account.get("clientBalance", 0)
            < price * self.gpu["max_runtime_seconds"] / 3600
        ):
            raise Refused("gpu_budget_unavailable")
        available = any(
            x.get("dataCenterId") == self.gpu["datacenter"]
            and str(x.get("stockStatus", "")).lower()
            not in ["", "none", "unavailable", "no stock"]
            for x in g.get("dataCenterAvailability", [])
        )
        return {"available": available, "hourly_usd": price}

    def public_key(self):
        key = Path(self.gpu["ssh_private_key"])
        pub = Path(str(key) + ".pub")
        if (
            not key.is_absolute()
            or key.is_symlink()
            or pub.is_symlink()
            or not key.is_file()
            or not pub.is_file()
            or key.stat().st_mode & 0o077
        ):
            raise Refused("ssh_key_missing")
        try:
            fields = pub.read_text().split()
        except OSError:
            raise Refused("ssh_key_missing") from None
        if len(fields) < 2 or fields[0] != "ssh-ed25519":
            raise Refused("ssh_key_missing")
        return " ".join(fields[:2])

    def create(self, name):
        if not self.inference_release or not name.startswith(
            self.settings["private_lead"]["pod_prefix"]
        ):
            raise Refused("private_80b_retired")
        public = self.public_key()
        return self.call(
            "pod",
            "create",
            "--name",
            name,
            "--image",
            self.gpu["image"],
            "--gpu-id",
            self.gpu["gpu"],
            "--gpu-count",
            "1",
            "--cloud-type",
            "SECURE",
            "--data-center-ids",
            self.gpu["datacenter"],
            "--network-volume-id",
            self.gpu["volume_id"],
            "--volume-mount-path",
            "/workspace",
            "--container-disk-in-gb",
            "30",
            "--ports",
            "22/tcp",
            "--ssh",
            "--min-cuda-version",
            "12.8",
            "--env",
            json.dumps({"PUBLIC_KEY": public}),
            timeout=120,
        )

    def delete(self, pod_id):
        # A success response is not proof of deletion; the lifecycle always lists again.
        try:
            self.call("pod", "delete", pod_id, timeout=60)
        except Refused:
            pass

    def ssh_info(self, pod_id):
        d = self.call("ssh", "info", pod_id)
        host, port = d.get("ip"), d.get("port")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            raise Refused("ssh_address_invalid") from None
        if type(port) is not int or not 1 <= port <= 65535:
            raise Refused("ssh_port_invalid")
        return host, port

    def ssh_args(self, pod_id, host, port):
        return [
            "/usr/bin/ssh",
            "-i",
            str(Path(self.gpu["ssh_private_key"])),
            "-p",
            str(port),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "UserKnownHostsFile="
            + str(Path(self.settings["state_directory"]) / "known_hosts"),
            "-o",
            "HostKeyAlias=runpod-" + pod_id,
            "-o",
            "ConnectTimeout=8",
            "-o",
            "ServerAliveInterval=15",
            "-o",
            "ServerAliveCountMax=3",
        ]

    def ssh(self, pod_id, host, port, command, data=None, timeout=15, diagnostic=None):
        if not self.inference_release:
            raise Refused("private_80b_retired")
        r = subprocess.run(
            self.ssh_args(pod_id, host, port) + ["root@" + host, command],
            input=data,
            capture_output=True,
            timeout=timeout,
        )
        if r.returncode:
            if diagnostic:
                root = private_dir(
                    Path(self.settings["state_directory"]) / "private-lead"
                )
                atomic(
                    root / "last-setup-error.json",
                    canonical(
                        {
                            "stage": diagnostic,
                            "returncode": r.returncode,
                            "stdout_tail": r.stdout.decode(errors="replace")[-8192:],
                            "stderr_tail": r.stderr.decode(errors="replace")[-8192:],
                            "time": time.time(),
                        }
                    ).encode(),
                )
            raise Refused("ssh_failed")
        return r.stdout

    def bootstrap_server(self, pod_id, host, port):
        if not self.inference_release:
            raise Refused("private_80b_retired")
        name = (
            "bootstrap-private-lead-vllm.sh"
            if self.gpu.get("logical_profile") == "PRIVATE_LEAD"
            else "bootstrap-vllm.sh"
        )
        if self.gpu.get("logical_profile") == "PRIVATE_LEAD":
            self.ssh(
                pod_id,
                host,
                port,
                "bash -s",
                (BASE / "runtime/prepare-private-lead-runtime.sh").read_bytes(),
                timeout=1800,
                diagnostic="runtime_prepare",
            )
            self.ssh(
                pod_id,
                host,
                port,
                "bash -s",
                (BASE / "runtime/prepare-private-lead-model.sh").read_bytes(),
                timeout=2600,
                diagnostic="model_prepare",
            )
        self.ssh(
            pod_id,
            host,
            port,
            "bash -s",
            (BASE / "runtime" / name).read_bytes(),
            timeout=1800,
            diagnostic=(
                "server_launch"
                if self.gpu.get("logical_profile") == "PRIVATE_LEAD"
                else None
            ),
        )

    def server_alive(self, pod_id, host, port):
        root = self.gpu.get("runtime_root", "/workspace/vinceai")
        self.ssh(
            pod_id,
            host,
            port,
            f'test -f {root}/pids/vllm.pid && kill -0 "$(cat {root}/pids/vllm.pid)"',
            timeout=15,
        )

    def tunnel(self, pod_id, host, port):
        socket = self.socket_path(pod_id)
        args = self.ssh_args(pod_id, host, port)
        r = subprocess.run(
            args + ["-S", socket, "-O", "check", "root@" + host],
            capture_output=True,
            timeout=10,
        )
        if r.returncode == 0:
            return
        Path(socket).unlink(missing_ok=True)
        args += [
            "-M",
            "-S",
            socket,
            "-f",
            "-N",
            "-L",
            f"127.0.0.1:{self.gpu['local_port']}:127.0.0.1:8000",
            "-o",
            "ExitOnForwardFailure=yes",
            "root@" + host,
        ]
        r = subprocess.run(args, capture_output=True, timeout=20)
        if r.returncode:
            raise Refused("tunnel_failed")

    def close_tunnel(self, state):
        if not state.get("host"):
            return
        args = self.ssh_args(state["pod_id"], state["host"], state["port"])
        subprocess.run(
            args
            + [
                "-S",
                self.socket_path(state["pod_id"]),
                "-O",
                "exit",
                "root@" + state["host"],
            ],
            capture_output=True,
            timeout=10,
        )

    def socket_path(self, pod_id):
        # macOS Unix-domain sockets have a short path limit. Bind each socket to
        # one Pod, avoiding accidental reuse of a previous Pod's SSH master.
        root = private_dir(Path("/tmp") / ("vinceai-phase10-" + str(os.getuid())))
        tag = hashlib.sha256(
            (self.settings["state_directory"] + pod_id).encode()
        ).hexdigest()[:24]
        return str(root / (tag + ".sock"))
