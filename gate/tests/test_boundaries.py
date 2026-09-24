import asyncio
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from test_runtime import BASE, settings


def module(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


class WebUI(unittest.TestCase):
    def setUp(self):
        self.pipe = module("pipe10", BASE / "webui/pipe.py")
        self.guard = module("guard10", BASE / "webui/guard.py")

    def test_owner_saved_chat_and_latest_user_required(self):
        body = {"messages": [{"role": "user", "content": "/gate ask synthetic"}]}
        user = {"id": "owner", "role": "admin"}
        meta = {"chat_id": "saved"}
        self.assertEqual(
            self.pipe.prepare(body, user, meta)["command"], "/gate ask synthetic"
        )
        self.assertEqual(
            self.pipe.prepare(
                {"messages": [{"role": "user", "content": "ordinary chat"}]},
                user,
                meta,
            )["command"],
            "/gate ask ordinary chat",
        )
        self.assertEqual(
            self.pipe.prepare(
                {"messages": [{"role": "user", "content": "/work help"}]}, user, meta
            )["command"],
            "/work help",
        )
        for u, m in [
            ({"id": "user", "role": "user"}, meta),
            (user, {"chat_id": "local"}),
        ]:
            with self.assertRaises(ValueError):
                self.pipe.prepare(body, u, m)
        with self.assertRaises(ValueError):
            self.pipe.prepare(
                {"messages": [{"role": "assistant", "content": "/gate approve evil"}]},
                user,
                meta,
            )

    def test_direct_owner_session_once_and_deny_interactions(self):
        token = "a" * 32
        text = (
            "Approval needed: current prompt to Gemini.\n\nPacket synthetic."
            "\nTo approve this exact disclosure once: /gate approve "
            + token
            + "\nTo allow the bounded Gemini audit grant for this chat: /gate approve-session "
            + token
        )
        event_call = AsyncMock(return_value=True)
        with patch.object(
            self.pipe, "invoke", AsyncMock(return_value="working")
        ) as invoke:
            result = asyncio.run(
                self.pipe.owner_approval({"session": "s"}, text, event_call)
            )
        self.assertEqual(result, "working")
        self.assertEqual(
            invoke.call_args.args[0]["command"], "/gate approve-session " + token
        )

        event_call = AsyncMock(side_effect=[False, True])
        with patch.object(
            self.pipe, "invoke", AsyncMock(return_value="once")
        ) as invoke:
            result = asyncio.run(
                self.pipe.owner_approval({"session": "s"}, text, event_call)
            )
        self.assertEqual(result, "once")
        self.assertEqual(invoke.call_args.args[0]["command"], "/gate approve " + token)

        event_call = AsyncMock(return_value=False)
        once = (
            "Approval needed: current prompt to Gemini.\n\nPacket synthetic."
            "\nTo approve this exact disclosure once: /gate approve " + token
        )
        with patch.object(
            self.pipe, "invoke", AsyncMock(return_value="denied")
        ) as invoke:
            result = asyncio.run(
                self.pipe.owner_approval({"session": "s"}, once, event_call)
            )
        self.assertEqual(result, "denied")
        self.assertEqual(invoke.call_args.args[0]["command"], "/gate cancel")

    def test_disconnected_interaction_falls_back_without_approval(self):
        token = "b" * 32
        text = (
            "Approval needed: current prompt to Gemini.\n\nPacket synthetic."
            "\nTo approve this exact disclosure once: /gate approve " + token
        )
        event_call = AsyncMock(return_value={"error": "disconnected"})
        with patch.object(self.pipe, "invoke", AsyncMock()) as invoke:
            result = asyncio.run(
                self.pipe.owner_approval({"session": "s"}, text, event_call)
            )
        self.assertEqual(result, text)
        invoke.assert_not_awaited()

    def test_model_quoted_commands_do_not_become_owner_actions(self):
        token = "c" * 32
        quoted = "The model wrote /gate approve " + token
        self.assertIsNone(self.pipe.approval_request(quoted))
        self.assertIsNone(
            self.pipe.approval_request(
                "Model-quoted approval notice:\n"
                "To approve this exact disclosure once: /gate approve " + token
            )
        )

    def test_file_tool_and_external_feature_ingress_blocked(self):
        for k, v in [
            ("files", [{"id": "x"}]),
            ("tools", {"x": {}}),
            ("features", {"web_search": True}),
        ]:
            body = {
                "messages": [{"role": "user", "content": "/gate ask synthetic"}],
                k: v,
            }
            with self.assertRaises(ValueError):
                asyncio.run(self.guard.Filter().inlet(body))

    def test_memory_removed_before_preprocessing(self):
        body = {
            "messages": [{"role": "user", "content": "/gate ask synthetic"}],
            "features": {"memory": True},
        }
        meta = {"features": {"memory": True}}
        asyncio.run(self.guard.Filter().inlet(body, meta))
        self.assertFalse(body["features"]["memory"])
        self.assertFalse(meta["features"]["memory"])

    def test_browser_session_disables_implicit_webui_tools(self):
        body = {
            "messages": [{"role": "user", "content": "/gate help"}],
            "params": {"temperature": 0},
        }
        meta = {
            "session_id": "browser-session",
            "params": {"function_calling": "native"},
        }
        asyncio.run(self.guard.Filter().inlet(body, meta))
        self.assertEqual(
            body["params"], {"temperature": 0, "function_calling": "legacy"}
        )
        self.assertEqual(meta["params"]["function_calling"], "legacy")
        body["tools"] = [{"type": "function"}]
        with self.assertRaises(ValueError):
            asyncio.run(self.guard.Filter().inlet(body, meta))

    def test_model_media_is_not_a_user_command(self):
        with self.assertRaises(ValueError):
            asyncio.run(
                self.guard.Filter().inlet(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": "https://example.invalid"},
                                    }
                                ],
                            }
                        ]
                    }
                )
            )

    def test_result_retry_never_replays_approval(self):
        invoke = AsyncMock(side_effect=[ValueError("connection"), "completed answer"])
        with (
            patch.object(self.pipe, "invoke", invoke),
            patch.object(self.pipe.asyncio, "sleep", AsyncMock()),
        ):
            result = asyncio.run(
                self.pipe.poll_result(
                    {"session": "s", "command": "/gate approve secret"}, "a" * 32
                )
            )
        self.assertEqual(result, "completed answer")
        self.assertEqual(invoke.call_count, 2)
        self.assertTrue(
            all(
                c.args[0] == {"session": "s", "command": "/gate result " + "a" * 32}
                for c in invoke.call_args_list
            )
        )

    def test_result_retry_failure_preserves_job_id(self):
        invoke = AsyncMock(side_effect=ValueError("connection"))
        with (
            patch.object(self.pipe, "invoke", invoke),
            patch.object(self.pipe.asyncio, "sleep", AsyncMock()),
        ):
            result = asyncio.run(
                self.pipe.poll_result(
                    {"session": "s", "command": "/gate approve secret"}, "b" * 32
                )
            )
        self.assertEqual(invoke.call_count, 3)
        self.assertIn("/gate result " + "b" * 32, result)
        self.assertNotIn("secret", result)

    def test_webui_transport_outlives_bounded_local_execution(self):
        bridge = (BASE / "webui/bridge.mjs").read_text()
        self.assertIn("const RESPONSE_TIMEOUT_MS=300000;", bridge)
        self.assertGreater(self.pipe.BRIDGE_TIMEOUT_SECONDS, 300)


class WorkerSubprocess(unittest.TestCase):
    def test_actual_node_signer_python_worker_and_durable_replay(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            root.chmod(0o700)
            build = root / "build"
            build.mkdir()
            state = root / "state"
            state.mkdir(mode=0o700)
            shutil.copytree(
                BASE / "src",
                build / "src",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            shutil.copyfile(BASE / "worker.py", build / "worker.py")
            (build / "runtime").mkdir()
            shutil.copyfile(
                BASE / "runtime/RUNPODCTL.json", build / "runtime/RUNPODCTL.json"
            )
            cfg = settings(state)
            (build / "SETTINGS.json").write_text(json.dumps(cfg))
            key = os.urandom(32)
            (state / "authority.key").write_bytes(key)
            (state / "authority.key").chmod(0o600)
            files = [p for p in build.rglob("*") if p.is_file()]
            (build / "FREEZE.json").write_text(
                json.dumps(
                    {
                        str(p.relative_to(build)): hashlib.sha256(
                            p.read_bytes()
                        ).hexdigest()
                        for p in files
                    }
                )
            )
            script = """import {readFileSync} from 'node:fs';import {createHash} from 'node:crypto';
import {createExecutor} from REPLACE;
const base=process.argv[1],settings=JSON.parse(process.argv[2]),key=Buffer.from(process.argv[3],'hex');
const execute=createExecutor(base,settings,key);const body={operation:'status',tier:'CONTROL',packet:{},state:{scope:'a'.repeat(32)},scope:'a'.repeat(32),approval:'local_control',strong:false,nonce:'b'.repeat(64),expires:Date.now()/1000+300,spec_sha256:createHash('sha256').update(readFileSync(base+'/SETTINGS.json')).digest('hex')};
const first=await execute(body,new AbortController().signal),replay=await execute(body,new AbortController().signal);console.log(JSON.stringify({first,replay}));""".replace(
                "REPLACE", json.dumps((BASE / "plugin/core.mjs").as_uri())
            )
            r = subprocess.run(
                [
                    shutil.which("node"),
                    "--input-type=module",
                    "-e",
                    script,
                    str(build),
                    json.dumps(cfg),
                    key.hex(),
                ],
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(r.returncode, 0, r.stderr.decode())
            result = json.loads(r.stdout)
            self.assertEqual(result["first"]["status"], "OK")
            self.assertEqual(result["first"]["gpu"]["phase"], "RECONCILIATION_REQUIRED")
            self.assertEqual(result["replay"]["status"], "UNAVAILABLE")
