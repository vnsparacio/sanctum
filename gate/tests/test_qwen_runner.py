"""Qwen headless host contracts; no provider calls or paid compute."""

import base64
import io
import json
import signal
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import qwen_runner
from common import Refused


class FakeLifecycle:
    def __init__(self):
        self.provider = self
        self.calls = []

    def preflight(self):
        return {"available": True, "hourly_usd": 2.0}

    def acquire(self, scope):
        self.calls.append(("acquire", scope))

    def resume(self):
        self.calls.append(("resume",))

    def heartbeat(self, scope):
        self.calls.append(("heartbeat", scope))

    def ensure_ready(self, scope, explicit=False):
        self.calls.append(("ready", scope, explicit))

    def release(self, scope):
        self.calls.append(("release", scope))

    def sweep(self):
        self.calls.append(("sweep",))


class FakeChild:
    def __init__(self):
        self.returncode = 0
        self.stdin = io.StringIO()
        self.stdout = io.StringIO()

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0


class QwenRunner(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.snapshot = self.root / "qwen-input"
        self.snapshot.mkdir()
        self.record = {"workspace_id": "a" * 32, "profile": "synthetic"}
        self.settings = {
            "private_lead": {
                "alias": "sanctum-private-lead-qwen35-122b",
                "local_port": 38123,
                "max_hourly_usd": 7,
            }
        }
        self.profile = {
            "engine": "qwen_code",
            "reviewer": True,
            "docker_path": "/usr/local/bin/docker",
            "docker_host": "unix:///var/run/docker.sock",
            "qwen_runner_image": "sanctum-qwen-code:test",
            "qwen_runner_image_id": "sha256:" + "a" * 64,
            "qwen_model_calls": 48,
            "qwen_tool_calls": 40,
            "qwen_wall_seconds": 1200,
            "qwen_outer_seconds": 2400,
            "qwen_retries": 0,
            "max_gpu_seconds": 2700,
            "max_cost_usd": 10,
        }

    def test_tar_has_container_owner_and_readable_copy_without_host_mount(self):
        raw = qwen_runner._tar_bytes(
            [("source", None, 0o755), ("source/app.js", b"code\n", 0o644)]
        )
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            rows = {item.name: item for item in archive}
            self.assertEqual(rows["source/app.js"].uid, qwen_runner.QWEN_USER)
            self.assertEqual(rows["source/app.js"].mode, 0o644)
            self.assertEqual(
                archive.extractfile(rows["source/app.js"]).read(), b"code\n"
            )
        with self.assertRaises(Refused):
            qwen_runner._tar_bytes([("../outside", b"bad", 0o644)])

    def test_broker_blocks_wrong_route_model_and_request_shape(self):
        def body(model):
            return base64.b64encode(json.dumps({"model": model}).encode()).decode()

        base = {
            "id": 1,
            "path": "/v1/chat/completions",
            "method": "POST",
            "body": body("wrong"),
        }
        for item, code in (
            (base, "qwen_model_identity"),
            ({**base, "path": "/v1/other"}, "qwen_broker_route"),
            ({**base, "body": "%%%"}, "qwen_broker_protocol"),
            ({**base, "host": "example.com"}, "qwen_broker_protocol"),
        ):
            with self.subTest(code=code), self.assertRaises(Refused) as caught:
                qwen_runner._model_reply(item, "allowed", 38123, 1)
            self.assertEqual(str(caught.exception), code)

    def test_profile_contract_refuses_without_export(self):
        for profile in (
            {**self.profile, "engine": "old"},
            {**self.profile, "reviewer": False},
            {**self.profile, "stages": [{"name": "second"}]},
        ):
            with self.assertRaises(Refused) as caught:
                qwen_runner.run(self.settings, self.record, profile, "task")
            self.assertEqual(str(caught.exception), "qwen_profile_contract")

    def test_one_run_imports_once_and_releases_lease_even_on_failure(self):
        fake = FakeLifecycle()
        values = {
            "ok": True,
            "receipt": {"authorityResult": "ALLOW", "paths": ["app.js"]},
        }
        for mode in ("success", "limit", "cancel"):
            with self.subTest(mode=mode):
                fake.calls.clear()
                child = FakeChild()
                run_dir = self.root / mode
                run_dir.mkdir()
                input_dir = run_dir / "qwen-input"
                input_dir.mkdir()
                with (
                    patch.object(qwen_runner, "verify_runner"),
                    patch.object(
                        qwen_runner, "_image", return_value="sanctum-qwen-code:test"
                    ),
                    patch.object(
                        qwen_runner.qwen_snapshot,
                        "export",
                        return_value={"input": str(input_dir)},
                    ),
                    patch.object(qwen_runner, "_snapshot_files", return_value=[]),
                    patch.object(qwen_runner, "_copy_tar"),
                    patch.object(qwen_runner, "_call"),
                    patch.object(qwen_runner.subprocess, "Popen", return_value=child),
                    patch.object(qwen_runner, "_remove_container", return_value=True),
                    patch.object(
                        qwen_runner.qwen_snapshot, "import_output", return_value=values
                    ) as importer,
                    patch.object(
                        qwen_runner,
                        "_broker_loop",
                        side_effect=(
                            Refused("qwen_model_call_limit")
                            if mode == "limit"
                            else (
                                (
                                    lambda *_: signal.getsignal(signal.SIGTERM)(
                                        signal.SIGTERM, None
                                    )
                                )
                                if mode == "cancel"
                                else None
                            )
                        ),
                        return_value={"modelCalls": 37, "inferenceSeconds": 120},
                    ),
                ):
                    result = qwen_runner.run(
                        self.settings,
                        self.record,
                        self.profile,
                        "Fix MoodLog",
                        lifecycle=fake,
                    )
                self.assertEqual(result["ok"], mode == "success")
                self.assertEqual(
                    result["code"],
                    {
                        "success": "OK",
                        "limit": "qwen_model_call_limit",
                        "cancel": "qwen_owner_cancelled",
                    }[mode],
                )
                self.assertEqual(result["containerAbsent"], True)
                self.assertIn(("release", self.record["workspace_id"]), fake.calls)
                self.assertIn(("sweep",), fake.calls)
                self.assertEqual(importer.call_count, 1 if mode == "success" else 0)
                self.assertTrue((input_dir.parent / "qwen-run-result.json").exists())


if __name__ == "__main__":
    unittest.main()
