import importlib.util
import json
import os
import signal
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "lifecycle_tools", ROOT / "scripts/lifecycle.py"
)
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.prefix = Path(self.tmp.name).resolve() / "install"
        (self.prefix / "logs").mkdir(parents=True)
        (self.prefix / "state").mkdir()

    def test_prefix_defaults_to_owner_environment(self):
        with patch.dict(os.environ, {"SANCTUM_PREFIX": str(self.prefix)}):
            self.assertEqual(lifecycle.default_prefix(), self.prefix)

    def test_broker_health_requires_a_successful_health_response(self):
        cache = self.prefix / "cache"
        cache.mkdir()
        path = lifecycle.broker_socket(self.prefix, "files")
        server = socket.socket(socket.AF_UNIX)
        self.addCleanup(server.close)
        server.bind(str(path))
        server.listen(1)

        def respond():
            connection, _ = server.accept()
            with connection:
                request = connection.recv(1024)
                self.assertIn(b"GET /health", request)
                body = b'{"ok":true}'
                connection.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n" + body
                )

        thread = threading.Thread(target=respond)
        thread.start()
        self.assertTrue(lifecycle.broker_ready(self.prefix, "files"))
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())

    def test_stale_broker_socket_is_moved_to_private_recovery(self):
        cache = self.prefix / "cache"
        cache.mkdir()
        path = lifecycle.broker_socket(self.prefix, "files")
        server = socket.socket(socket.AF_UNIX)
        server.bind(str(path))
        server.close()
        path.chmod(0o600)
        old = lifecycle.time.time() - 10
        os.utime(path, (old, old))
        with (
            patch.object(
                lifecycle.component_tools,
                "selected_brokers",
                return_value=["files"],
            ),
            patch.object(lifecycle.time, "sleep"),
        ):
            recovery = lifecycle.recover_stale_broker_sockets(self.prefix)
        self.assertFalse(path.exists())
        self.assertTrue((recovery / path.name).exists())
        self.assertEqual(recovery.stat().st_mode & 0o777, 0o700)

    def test_live_broker_socket_is_never_adopted_or_moved(self):
        cache = self.prefix / "cache"
        cache.mkdir()
        path = lifecycle.broker_socket(self.prefix, "files")
        server = socket.socket(socket.AF_UNIX)
        self.addCleanup(server.close)
        server.bind(str(path))
        server.listen(1)
        path.chmod(0o600)
        with patch.object(
            lifecycle.component_tools,
            "selected_brokers",
            return_value=["files"],
        ):
            with self.assertRaisesRegex(ValueError, "live listener"):
                lifecycle.recover_stale_broker_sockets(self.prefix)
        self.assertTrue(path.exists())

    def test_non_socket_broker_path_requires_manual_inspection(self):
        cache = self.prefix / "cache"
        cache.mkdir()
        path = lifecycle.broker_socket(self.prefix, "files")
        path.write_text("synthetic\n")
        with patch.object(
            lifecycle.component_tools,
            "selected_brokers",
            return_value=["files"],
        ):
            with self.assertRaisesRegex(ValueError, "not a socket"):
                lifecycle.recover_stale_broker_sockets(self.prefix)

    def test_broker_group_uses_interrupt_for_socket_cleanup(self):
        child = Mock()
        child.poll.side_effect = [None, 0, 0]
        lifecycle.component_tools.stop_children([child])
        child.send_signal.assert_called_once_with(signal.SIGINT)
        child.terminate.assert_not_called()

    def test_authorization_checks_use_metadata_without_returning_secrets(self):
        account = self.prefix / "config/gmail-read/account"
        account.parent.mkdir(parents=True)
        account.write_text("owner@example.test\n")
        google = Mock(
            returncode=0,
            stdout=json.dumps(
                {
                    "accounts": [
                        {
                            "email": "owner@example.test",
                            "services": ["gmail"],
                        }
                    ]
                }
            ),
        )
        web = Mock(
            returncode=0,
            stdout=json.dumps([{"name": "PARALLEL_API_KEY", "kind": "secret"}]),
        )
        with (
            patch.object(lifecycle.shutil, "which", return_value="/reviewed/gog"),
            patch.object(lifecycle.subprocess, "run", return_value=google),
        ):
            self.assertTrue(lifecycle.google_authorized(self.prefix, "gmail"))
        with (
            patch.object(lifecycle, "web_enabled", return_value=True),
            patch.object(lifecycle, "openclaw_command", return_value=(["node"], {})),
            patch.object(lifecycle.subprocess, "run", return_value=web),
        ):
            self.assertTrue(lifecycle.web_authorized(self.prefix))

    def test_openrouter_check_requires_exactly_one_isolated_profile(self):
        database = self.prefix / "state/openclaw/state/openclaw.sqlite"
        database.parent.mkdir(parents=True)
        with lifecycle.sqlite3.connect(database) as connection:
            connection.execute(
                "create table config_machine_state (state_key text, value_json text)"
            )
            connection.execute(
                "insert into config_machine_state values (?, ?)",
                (
                    "authProfiles.store",
                    json.dumps(
                        {
                            "profiles": {
                                "openrouter:manual": {
                                    "provider": "openrouter",
                                    "type": "api_key",
                                    "key": "synthetic-test-value",
                                }
                            }
                        }
                    ),
                ),
            )
        with patch.object(
            lifecycle.op,
            "environment",
            return_value={"VINCEAI_OPENCLAW_DATABASE": str(database)},
        ):
            self.assertTrue(lifecycle.openrouter_authorized(self.prefix))

    def test_setup_reuses_reviewed_primitives_and_prepares_model(self):
        with (
            patch.object(lifecycle, "ensure_dependencies") as dependencies,
            patch.object(lifecycle.op, "verify") as verify,
            patch.object(lifecycle.op, "setup") as core_setup,
            patch.object(lifecycle.op, "verify_install", return_value={}),
            patch.object(lifecycle.bootstrap_tools, "bootstrap") as bootstrap,
            patch.object(lifecycle.bootstrap_tools, "ensure_model") as model,
        ):
            lifecycle.setup(self.prefix, cache_only=True)
        dependencies.assert_called_once_with()
        verify.assert_called_once_with()
        core_setup.assert_called_once_with(self.prefix)
        self.assertEqual(
            bootstrap.call_args_list,
            [call("mlx", self.prefix), call("webui", self.prefix)],
        )
        model.assert_called_once_with(self.prefix, cache_only=True)

    def test_complete_runtime_is_idempotent_and_cache_probe_is_offline(self):
        runtime = self.prefix / "runtime/mlx/bin"
        runtime.mkdir(parents=True)
        (runtime / "mlx_lm.server").write_text("synthetic\n")
        (runtime / "python").symlink_to(Path(sys.executable).resolve())
        with (
            patch.object(lifecycle.bootstrap_tools.op, "verify"),
            patch.object(lifecycle.bootstrap_tools.op, "verify_install"),
            patch.object(
                lifecycle.bootstrap_tools.platform, "system", return_value="Darwin"
            ),
            patch.object(
                lifecycle.bootstrap_tools.platform, "machine", return_value="arm64"
            ),
            patch.object(lifecycle.bootstrap_tools.subprocess, "run") as run,
        ):
            lifecycle.bootstrap_tools.bootstrap("mlx", self.prefix)
            lifecycle.bootstrap_tools.ensure_model(self.prefix, cache_only=True)
        command = run.call_args.args[0]
        self.assertIn("mlx_lm.utils import _download", command[-1])
        self.assertEqual(run.call_args.kwargs["env"]["HF_HUB_OFFLINE"], "1")
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0][:3], ["uv", "pip", "check"])

    def test_start_daemonizes_one_supervisor_and_waits_for_ready(self):
        process = Mock(pid=4321)
        process.poll.return_value = None
        state = {"pid": 4321, "phase": "ready"}
        with (
            patch.object(lifecycle.op, "verify"),
            patch.object(
                lifecycle.op,
                "verify_install",
                return_value={"mlx_port": 28080, "gateway_port": 28789},
            ),
            patch.object(lifecycle.bootstrap_tools, "runtime_ready", return_value=True),
            patch.object(lifecycle, "read_state", side_effect=[None, state]),
            patch.object(lifecycle.op, "process_record", return_value=None),
            patch.object(lifecycle.op, "owns_process", return_value=False),
            patch.object(lifecycle, "tcp_ready", return_value=False),
            patch.object(
                lifecycle, "recover_stale_broker_sockets", return_value=None
            ) as recover,
            patch.object(lifecycle, "http_ready", return_value=True),
            patch.object(
                lifecycle,
                "readiness_report",
                return_value={
                    "readiness": "ready",
                    "next_actions": [],
                    "owner_checks": [],
                },
            ),
            patch.object(lifecycle.subprocess, "Popen", return_value=process) as popen,
        ):
            lifecycle.start(self.prefix)
        recover.assert_called_once_with(self.prefix)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        command = popen.call_args.args[0]
        self.assertIn("_supervise", command)
        self.assertEqual(command[-1], str(self.prefix))

    def test_start_refuses_to_adopt_a_separate_gateway(self):
        with (
            patch.object(lifecycle.op, "verify"),
            patch.object(
                lifecycle.op,
                "verify_install",
                return_value={"mlx_port": 28080, "gateway_port": 28789},
            ),
            patch.object(lifecycle.bootstrap_tools, "runtime_ready", return_value=True),
            patch.object(lifecycle, "read_state", return_value=None),
            patch.object(lifecycle.op, "process_record", return_value={"pid": 7}),
            patch.object(lifecycle.op, "owns_process", return_value=True),
        ):
            with self.assertRaisesRegex(ValueError, "separately managed gateway"):
                lifecycle.start(self.prefix)

    def test_supervisor_starts_in_dependency_order_and_stops_children(self):
        events = []
        handlers = {}

        class Child:
            next_pid = 5000

            def __init__(self, command):
                self.command = command
                self.pid = Child.next_pid
                Child.next_pid += 1
                self.code = None

            def poll(self):
                return self.code

            def terminate(self):
                events.append("stop:" + self.command[0])
                self.code = -15

            def wait(self, timeout=None):
                return self.code

            def kill(self):
                self.code = -9

        def spawn(command, **_kwargs):
            events.append("start:" + command[0])
            return Child(command)

        def signal_handler(signum, handler):
            handlers[signum] = handler

        def finish_loop(_seconds):
            handlers[lifecycle.signal.SIGTERM](lifecycle.signal.SIGTERM, None)

        commands = [(["mlx"], {}), (["brokers"], {}), (["webui"], {})]
        with (
            patch.object(lifecycle.op, "verify"),
            patch.object(
                lifecycle,
                "expected_identity",
                return_value={"schema": lifecycle.STACK_SCHEMA},
            ),
            patch.object(
                lifecycle.op,
                "verify_install",
                return_value={"mlx_port": 28080, "gateway_port": 28789},
            ),
            patch.object(
                lifecycle.component_tools,
                "component_command",
                side_effect=commands,
            ),
            patch.object(
                lifecycle.component_tools, "selected_brokers", return_value=["files"]
            ),
            patch.object(lifecycle.subprocess, "Popen", side_effect=spawn),
            patch.object(lifecycle, "http_ready", return_value=True),
            patch.object(lifecycle, "broker_ready", return_value=True),
            patch.object(
                lifecycle.op, "up", side_effect=lambda _prefix: events.append("gateway")
            ),
            patch.object(lifecycle.op, "down"),
            patch.object(lifecycle.signal, "signal", side_effect=signal_handler),
            patch.object(lifecycle.time, "sleep", side_effect=finish_loop),
        ):
            lifecycle.supervise(self.prefix)
        self.assertEqual(
            events[:4], ["start:mlx", "gateway", "start:brokers", "start:webui"]
        )
        self.assertEqual(events[-3:], ["stop:webui", "stop:brokers", "stop:mlx"])
        self.assertEqual(lifecycle.read_state(self.prefix)["phase"], "stopped")

    def test_stop_signals_only_the_recorded_supervisor_after_gateway_shutdown(self):
        record = {"pid": 4321, "identity": ["lifecycle.py", "_supervise"]}
        events = []
        with (
            patch.object(lifecycle.op, "verify_install", return_value={}),
            patch.object(lifecycle, "read_state", return_value=record),
            patch.object(lifecycle, "process_matches", return_value=True),
            patch.object(
                lifecycle.op,
                "down",
                side_effect=lambda _prefix: events.append("gateway"),
            ),
            patch.object(
                lifecycle,
                "terminate_record",
                side_effect=lambda *_args, **_kwargs: events.append("supervisor"),
            ),
        ):
            lifecycle.stop(self.prefix)
        self.assertEqual(events, ["gateway", "supervisor"])

    def test_stop_recovers_recorded_children_in_safe_order(self):
        record = {
            "phase": "ready",
            "children": {
                name: {"pid": number, "identity": [name]}
                for number, name in enumerate(("mlx", "brokers", "webui"), 10)
            },
        }
        stopped = []
        with (
            patch.object(lifecycle.op, "verify_install", return_value={}),
            patch.object(lifecycle, "read_state", return_value=record),
            patch.object(lifecycle, "process_matches", return_value=False),
            patch.object(lifecycle.op, "down"),
            patch.object(
                lifecycle,
                "terminate_record",
                side_effect=lambda child: stopped.append(child["identity"][0]),
            ),
            patch.object(lifecycle, "write_state"),
        ):
            lifecycle.stop(self.prefix)
        self.assertEqual(stopped, ["webui", "brokers", "mlx"])

    def test_status_reports_each_configured_component(self):
        record = {"phase": "ready", "pid": 4321, "identity": ["supervisor"]}
        with (
            patch.object(
                lifecycle.op,
                "verify_install",
                return_value={"mlx_port": 28080, "gateway_port": 28789},
            ),
            patch.object(lifecycle, "read_state", return_value=record),
            patch.object(lifecycle, "process_matches", return_value=True),
            patch.object(lifecycle, "identity_current", return_value=True),
            patch.object(
                lifecycle.component_tools,
                "selected_brokers",
                return_value=["messages", "files"],
            ),
            patch.object(lifecycle, "tcp_ready", return_value=True),
            patch.object(lifecycle.op, "gateway_socket_ready", return_value=True),
            patch.object(lifecycle, "broker_ready", return_value=True),
            patch.object(lifecycle, "http_ready", return_value=True),
            patch("builtins.print") as output,
        ):
            lifecycle.status(self.prefix)
        report = json.loads(output.call_args.args[0])
        self.assertEqual(report["supervisor"], "current")
        self.assertEqual(report["brokers"], {"messages": True, "files": True})
        self.assertTrue(report["webui"])

    def test_readiness_reports_owner_actions_without_exposing_credentials(self):
        services = {
            "supervisor": "current",
            "phase": "ready",
            "mlx": True,
            "gateway": True,
            "brokers": {"messages": True, "gmail": True, "files": True},
            "webui": True,
            "url": "http://127.0.0.1:28000",
        }
        enabled = {"messages": True, "gmail": True, "calendar": False}
        with (
            patch.object(lifecycle, "service_status", return_value=services),
            patch.object(lifecycle, "webui_owner_enrollment", return_value="pass"),
            patch.object(lifecycle.op, "webui_function_sync", return_value="pass"),
            patch.object(
                lifecycle.component_tools,
                "integration_enabled",
                side_effect=lambda _prefix, name: enabled[name],
            ),
            patch.object(
                lifecycle, "google_authorized", side_effect=lambda _prefix, name: False
            ),
            patch.object(lifecycle, "web_enabled", return_value=True),
            patch.object(lifecycle, "web_authorized", return_value=True),
            patch.object(lifecycle, "openrouter_authorized", return_value=False),
        ):
            report = lifecycle.readiness_report(self.prefix)
        self.assertEqual(report["readiness"], "owner-action-required")
        self.assertEqual(report["integrations"]["gmail"]["authorization"], "missing")
        self.assertEqual(
            report["integrations"]["messages"]["authorization"],
            "owner-permission-check-required",
        )
        self.assertNotIn("owner@example", json.dumps(report))

    def test_webui_owner_enrollment_requires_exactly_one_admin(self):
        database = self.prefix / "state/webui/webui.db"
        database.parent.mkdir(parents=True, exist_ok=True)
        with lifecycle.sqlite3.connect(database) as connection:
            connection.execute("create table user (role text)")
            connection.execute("insert into user values ('admin')")
        self.assertEqual(lifecycle.webui_owner_enrollment(self.prefix), "pass")


if __name__ == "__main__":
    unittest.main()
