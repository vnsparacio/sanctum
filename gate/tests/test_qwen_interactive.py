"""Offline contracts for the interactive, demand-started Qwen model route."""

import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "qwen_interactive_under_test", ROOT / "scripts/qwen_interactive.py"
)
qwen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qwen)


class Upstream(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.calls.append((self.path, json.loads(body)))
        data = json.dumps({"choices": [{"message": {"content": "READY"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class FakeHold:
    alias = "synthetic-private-model"
    ready = 0

    def __init__(self, port):
        self.port = port

    def ensure_ready(self):
        self.ready += 1


class InteractiveQwenContracts(unittest.TestCase):
    def test_fresh_settings_select_private_model_without_persisting_a_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".qwen/settings.json"
            qwen.configure_qwen(path, "synthetic-private-model")
            settings = json.loads(path.read_text())
            self.assertEqual(settings["security"]["auth"]["selectedType"], "openai")
            self.assertEqual(settings["model"]["name"], "synthetic-private-model")
            self.assertNotIn("env", settings)
            self.assertNotIn("apiKey", path.read_text())

    def test_hold_starts_once_and_stops_on_session_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            gate = prefix / "gate"
            gate.mkdir()
            (gate / "manage.py").write_text(
                "import json,signal,time\n"
                "stop=False\n"
                "def end(*_):\n global stop\n stop=True\n"
                "signal.signal(signal.SIGTERM,end)\n"
                "print(json.dumps({'event':'READY'}),flush=True)\n"
                "while not stop: time.sleep(0.01)\n"
            )
            hold = qwen.ModelHold(
                prefix, sys.executable, "synthetic-private-model", 12345
            )
            hold.ensure_ready()
            pid = hold.process.pid
            hold.ensure_ready()
            self.assertEqual(hold.process.pid, pid)
            self.assertGreater(hold.deadline, qwen.time.time())
            hold.close()
            self.assertEqual(hold.process.returncode, 0)

    def test_stuck_hold_is_killed_and_managed_stop_confirms_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            gate = prefix / "gate"
            gate.mkdir()
            (gate / "manage.py").write_text(
                "import json,signal,sys,time\n"
                "if 'hold' in sys.argv:\n"
                " signal.signal(signal.SIGTERM,signal.SIG_IGN)\n"
                " print(json.dumps({'event':'READY'}),flush=True)\n"
                " while True: time.sleep(0.01)\n"
                "else:\n"
                " print(json.dumps({'phase':'OFFLINE','leases':0,'active_requests':0}))\n"
            )
            hold = qwen.ModelHold(
                prefix, sys.executable, "synthetic-private-model", 12345
            )
            previous = qwen.CLEANUP_WAIT_SECONDS
            qwen.CLEANUP_WAIT_SECONDS = 0.2
            try:
                hold.ensure_ready()
                hold.close()
                self.assertNotEqual(hold.process.returncode, 0)
            finally:
                qwen.CLEANUP_WAIT_SECONDS = previous
                if hold.process and hold.process.poll() is None:
                    hold.process.kill()
                    hold.process.wait(timeout=3)

    def test_provider_setup_preserves_other_models_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".qwen/settings.json"
            path.parent.mkdir()
            path.write_text(
                json.dumps({"modelProviders": {"openai": [{"id": "other"}]}})
            )
            self.assertTrue(qwen.configure_qwen(path, "synthetic-private-model"))
            value = json.loads(path.read_text())
            self.assertEqual(value["modelProviders"]["openai"], [{"id": "other"}])
            self.assertEqual(value["providerProtocol"]["sanctum"], "openai")
            self.assertEqual(
                value["modelProviders"]["sanctum"][0]["id"], "synthetic-private-model"
            )
            self.assertFalse(qwen.configure_qwen(path, "synthetic-private-model"))
            self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_model_list_does_not_allocate_and_only_valid_chat_starts_hold(self):
        Upstream.calls = []
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        hold = FakeHold(upstream.server_port)
        bridge = qwen.ModelServer(("127.0.0.1", 0), hold, "synthetic-local-token")
        bridge_thread = threading.Thread(target=bridge.serve_forever, daemon=True)
        bridge_thread.start()
        base = f"http://127.0.0.1:{bridge.server_port}/v1"

        def call(path, *, body=None, token="synthetic-local-token"):
            headers = {"Authorization": "Bearer " + token}
            if body is not None:
                headers["Content-Type"] = "application/json"
            request = urllib.request.Request(
                base + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers=headers,
            )
            try:
                with urllib.request.urlopen(request, timeout=3) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)

        try:
            self.assertEqual(call("/models")[0], 200)
            self.assertEqual(hold.ready, 0)
            self.assertEqual(
                call("/chat/completions", body={"model": hold.alias}, token="wrong")[0],
                401,
            )
            self.assertEqual(call("/chat/completions", body={"model": "other"})[0], 400)
            self.assertEqual(call("/unknown", body={"model": hold.alias})[0], 404)
            self.assertEqual(hold.ready, 0)
            status, response = call(
                "/chat/completions",
                body={
                    "model": hold.alias,
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            self.assertEqual(status, 200)
            self.assertEqual(response["choices"][0]["message"]["content"], "READY")
            self.assertEqual(hold.ready, 1)
            self.assertEqual(len(Upstream.calls), 1)
            self.assertEqual(Upstream.calls[0][0], "/v1/chat/completions")
        finally:
            bridge.shutdown()
            bridge.server_close()
            upstream.shutdown()
            upstream.server_close()
            bridge_thread.join(timeout=3)
            upstream_thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
