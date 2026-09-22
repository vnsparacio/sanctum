import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
from command_runner import run, verify_runner
from common import Refused


class FakeChild:
    def __init__(self, *, running=False, stdout=b"", stderr=b"", returncode=0):
        self.pid = 4242
        self.returncode = returncode
        self.running = running
        self.stdin = None
        self.stdout = tempfile.TemporaryFile()
        self.stderr = tempfile.TemporaryFile()
        self.stdout.write(stdout)
        self.stderr.write(stderr)
        self.stdout.seek(0)
        self.stderr.seek(0)

    def poll(self):
        return None if self.running else self.returncode

    def wait(self, timeout=None):
        self.running = False
        return self.returncode


class FakeSelector:
    def __init__(self, *, fail=None):
        self.rows = []
        self.fail = fail

    def register(self, stream, _event, label):
        self.rows.append(SimpleNamespace(fileobj=stream, data=label))

    def select(self, _timeout):
        if self.fail:
            raise self.fail
        return [(row, None) for row in self.rows]

    def close(self):
        pass


class UnitRunner(unittest.TestCase):
    def run_case(
        self,
        child,
        *,
        selector=None,
        times=None,
        output_bytes=65536,
        inspect_unknown=False,
        calls=None,
    ):
        profile = {
            "docker_path": "/usr/bin/docker",
            "docker_host": "unix:///synthetic",
            "runner_image": "synthetic",
            "runner_image_id": "sha256:" + "a" * 64,
            "runner_user": "501:20",
            "timeout_seconds": 1,
            "operations": {"test": ["node", "--test"]},
        }
        policy = {
            "cpus": 1,
            "memory_bytes": 1024,
            "pids": 4,
            "open_files": 8,
            "file_bytes": 16,
            "tmp_bytes": 32,
            "timeout_seconds": 1,
            "output_bytes": output_bytes,
        }
        clock = iter(times or [0, 0, 0, 0, 0])

        def call(_docker, args, _profile, timeout=20, check=True):
            if calls is not None:
                calls.append(args)
            if args[0] == "inspect":
                if inspect_unknown:
                    raise Refused("runner_unavailable")
                return subprocess.CompletedProcess(args, 1, "", "")
            return subprocess.CompletedProcess(args, 0, "", "")

        with (
            patch("command_runner._real_directory", return_value=Path("/workspace")),
            patch("command_runner._profile", return_value=(profile, {})),
            patch(
                "command_runner._descriptor",
                return_value={"schema": "sanctum-work-runner/v1", "policy": policy},
            ),
            patch(
                "command_runner.verify_runner",
                return_value={
                    "image": "synthetic",
                    "image_id": profile["runner_image_id"],
                    "policy_digest": "b" * 64,
                },
            ),
            patch("command_runner._call", side_effect=call),
            patch("command_runner.subprocess.Popen", return_value=child),
            patch(
                "command_runner.selectors.DefaultSelector",
                return_value=selector or FakeSelector(),
            ),
            patch("command_runner.os.killpg"),
        ):
            return run({}, "test", "/workspace", "test", now=lambda: next(clock))

    def test_timeout_cancellation_background_child_output_and_unknown_are_terminal(
        self,
    ):
        timed = self.run_case(FakeChild(running=True), times=[0, 0, 0, 2, 2])
        self.assertEqual(
            (timed["code"], timed["executionState"]),
            ("COMMAND_TIMEOUT", "COMPLETION_UNKNOWN"),
        )
        self.assertTrue(timed["container_absent"])

        cancelled = self.run_case(
            FakeChild(running=True),
            selector=FakeSelector(fail=Refused("operation_cancelled")),
        )
        self.assertEqual(
            (cancelled["code"], cancelled["executionState"]),
            ("COMMAND_CANCELLED", "CANCELLED"),
        )
        self.assertTrue(cancelled["container_absent"])

        background = self.run_case(FakeChild(stdout=b"parent exited\n"))
        self.assertEqual(
            (background["code"], background["executionState"]),
            ("OK", "COMPLETED"),
        )
        self.assertTrue(background["container_absent"])

        huge = self.run_case(
            FakeChild(running=True, stdout=b"secret-output"), output_bytes=4
        )
        self.assertEqual(
            (huge["code"], huge["executionState"]),
            ("OUTPUT_LIMIT", "COMPLETION_UNKNOWN"),
        )
        self.assertEqual(huge["output_bytes"], 4)

        ambiguous = self.run_case(
            FakeChild(stdout=b"private value"), inspect_unknown=True
        )
        self.assertEqual(
            (ambiguous["code"], ambiguous["executionState"]),
            ("CLEANUP_UNKNOWN", "COMPLETION_UNKNOWN"),
        )
        self.assertFalse(ambiguous["container_absent"])

    def test_resource_arguments_are_host_selected(self):
        calls = []
        result = self.run_case(FakeChild(), calls=calls)
        self.assertTrue(result["container_absent"])
        create = calls[0]
        for expected in (
            "--cpus",
            "--memory",
            "--memory-swap",
            "--pids-limit",
            "--ulimit",
            "--read-only",
            "--cap-drop",
            "--security-opt",
            "--tmpfs",
        ):
            self.assertIn(expected, create)


class OciRunner(unittest.TestCase):
    def write_profile(self, timeout):
        value = json.loads(self.profile.read_text())
        value["profiles"]["test"]["timeout_seconds"] = timeout
        self.profile.write_text(json.dumps(value))
        self.profile.chmod(0o600)

    def setUp(self):
        self.docker = shutil.which("docker")
        if not self.docker:
            self.skipTest("Docker CLI unavailable")
        try:
            subprocess.run(
                [self.docker, "version"], check=True, capture_output=True, timeout=10
            )
        except Exception:
            self.skipTest("Docker daemon unavailable")
        inspect = subprocess.run(
            [
                self.docker,
                "image",
                "inspect",
                "--format",
                "{{.Id}}",
                "sanctum-work-runner:project3g",
            ],
            capture_output=True,
            text=True,
        )
        if inspect.returncode:
            self.skipTest("reviewed Work Mode runner unavailable")
        context = json.loads(
            subprocess.run(
                [self.docker, "context", "inspect"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "index.test.js").write_text(
            "import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import net from 'node:net';test('sandbox',async()=>{assert.equal(process.env.TEST_SECRET,undefined);assert.equal(fs.existsSync('/run/docker.sock'),false);assert.equal(fs.existsSync('/Users'),false);await new Promise((resolve,reject)=>{const s=net.connect({host:'1.1.1.1',port:443});const blocked=()=>{s.destroy();resolve()};s.on('error',blocked);s.setTimeout(500,blocked);s.on('connect',()=>reject(Error('ambient network')))});});\n"
        )
        profile = {
            "schema": "sanctum-work-mode-profiles/v1",
            "profiles": {
                "test": {
                    "docker_path": str(Path(self.docker).resolve()),
                    "docker_host": context[0]["Endpoints"]["docker"]["Host"],
                    "runner_image": "sanctum-work-runner:project3g",
                    "runner_image_id": inspect.stdout.strip(),
                    "runner_user": f"{os.getuid()}:{os.getgid()}",
                    "platform": "linux/arm64",
                    "timeout_seconds": 30,
                    "operations": {"test": ["node", "--test"]},
                }
            },
        }
        self.profile = self.root / "profile.json"
        self.profile.write_text(json.dumps(profile))
        self.profile.chmod(0o600)
        self.settings = {"work_mode": {"profile_file": str(self.profile)}}

    def tearDown(self):
        if hasattr(self, "tmp"):
            self.tmp.cleanup()

    def test_real_container_has_limits_no_socket_home_secret_or_network_mount(self):
        os.environ["TEST_SECRET"] = "must-not-leak"
        try:
            result = run(self.settings, "test", str(self.workspace), "test")
        finally:
            os.environ.pop("TEST_SECRET", None)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["container_absent"])
        self.assertEqual(result["limits"]["network"], "none")
        self.assertEqual(result["runner"], verify_runner(self.settings, "test"))

    def test_output_timeout_and_file_limits_fail_closed_and_cleanup(self):
        self.write_profile(10)
        (self.workspace / "index.test.js").write_text(
            "import test from 'node:test';test('output',()=>process.stdout.write('x'.repeat(70000)));\n"
        )
        output = run(self.settings, "test", str(self.workspace), "test")
        self.assertEqual(output["code"], "OUTPUT_LIMIT")
        self.assertTrue(output["container_absent"])
        self.write_profile(1)
        (self.workspace / "index.test.js").write_text(
            "import test from 'node:test';test('timeout',async()=>await new Promise(r=>setTimeout(r,5000)));\n"
        )
        timed = run(self.settings, "test", str(self.workspace), "test")
        self.assertEqual(timed["code"], "COMMAND_TIMEOUT")
        self.assertTrue(timed["container_absent"])
        self.write_profile(10)
        (self.workspace / "index.test.js").write_text(
            "import test from 'node:test';import fs from 'node:fs';test('file',()=>fs.writeFileSync('large.bin',Buffer.alloc(70*1024*1024)));\n"
        )
        disk = run(self.settings, "test", str(self.workspace), "test")
        self.assertFalse(disk["ok"])
        self.assertTrue(disk["container_absent"])
        self.assertFalse((self.workspace / "large.bin").exists())
        (self.workspace / "index.test.js").write_text(
            "import test from 'node:test';import{spawn}from'node:child_process';"
            "test('background',()=>{const p=spawn(process.execPath,['-e',"
            "'setInterval(()=>{},1000)'],{detached:true,stdio:'ignore'});p.unref()});\n"
        )
        background = run(self.settings, "test", str(self.workspace), "test")
        self.assertTrue(background["ok"], background)
        self.assertTrue(background["container_absent"])


if __name__ == "__main__":
    unittest.main()
