import importlib.util
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "operator_tools", ROOT / "scripts/release_operator.py"
)
op = importlib.util.module_from_spec(spec)
spec.loader.exec_module(op)
component_spec = importlib.util.spec_from_file_location(
    "component_tools", ROOT / "scripts/component.py"
)
component = importlib.util.module_from_spec(component_spec)
component_spec.loader.exec_module(component)
work_mode_spec = importlib.util.spec_from_file_location(
    "work_mode_tools", ROOT / "scripts/upgrade_work_mode.py"
)
work_mode = importlib.util.module_from_spec(work_mode_spec)
work_mode_spec.loader.exec_module(work_mode)


class Setup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.prefix = Path(self.tmp.name).resolve() / "install"

    def test_idempotent_private_isolated_configuration(self):
        op.setup(self.prefix)
        before = (self.prefix / "config/openclaw.json").read_bytes()
        op.setup(self.prefix)
        self.assertEqual(before, (self.prefix / "config/openclaw.json").read_bytes())
        op.verify_install(self.prefix)
        cfg = json.loads(before)
        self.assertEqual(cfg["tools"]["profile"], "minimal")
        self.assertIn("exec", cfg["tools"]["deny"])
        self.assertEqual(cfg["gateway"]["bind"], "loopback")
        main = cfg["agents"]["entries"]["main"]
        self.assertEqual(main["thinkingDefault"], "off")
        self.assertFalse(main["params"]["chat_template_kwargs"]["enable_thinking"])
        self.assertEqual(
            cfg["models"]["providers"]["mlx-local"]["models"][0]["contextWindow"],
            24576,
        )
        self.assertFalse(
            json.loads((self.prefix / "gate/SETTINGS.json").read_text())["gpu"][
                "auto_start"
            ]
        )
        self.assertEqual(
            (self.prefix / "state/gate/authority.key").stat().st_mode & 0o777, 0o600
        )
        self.assertEqual((self.prefix / "config/contacts.json").read_text(), "{}\n")
        self.assertEqual(
            op.environment(self.prefix)["VINCEAI_MCP_INPUT_DIR"],
            str(self.prefix / "mcp-input"),
        )
        import plistlib

        self.assertEqual(
            plistlib.loads((self.prefix / "config/gpu-janitor.plist").read_bytes())[
                "EnvironmentVariables"
            ]["USER"],
            os.environ.get("USER", "vinceai"),
        )

    def test_drift_refuses_without_overwrite(self):
        op.setup(self.prefix)
        p = self.prefix / "config/openclaw.json"
        p.write_text("{}")
        with self.assertRaises(ValueError):
            op.setup(self.prefix)
        self.assertEqual(p.read_text(), "{}")

    def test_work_mode_amendment_updates_only_reviewed_local_model_context(self):
        op.setup(self.prefix)
        config_path = self.prefix / "config/openclaw.json"
        config = json.loads(config_path.read_text())
        local = config["models"]["providers"]["mlx-local"]["models"][0]
        local["contextWindow"] = 16384
        firecrawl = str(
            self.prefix / "runtime/web/node_modules/@openclaw/firecrawl-plugin"
        )
        config["tools"]["web"] = {
            "search": {"enabled": True, "provider": "parallel"},
            "fetch": {"enabled": True, "provider": "firecrawl"},
        }
        config["plugins"]["load"]["paths"].append(firecrawl)
        config["plugins"]["allow"].append("firecrawl")
        config["plugins"]["entries"]["firecrawl"] = {"enabled": True}
        config_path.write_text(json.dumps(config))
        updated = json.loads(work_mode.openclaw_config(self.prefix))
        self.assertEqual(
            updated["models"]["providers"]["mlx-local"]["models"][0]["contextWindow"],
            24576,
        )
        self.assertEqual(
            updated["agents"]["defaults"]["model"],
            config["agents"]["defaults"]["model"],
        )
        self.assertNotIn("provider", updated["tools"]["web"]["fetch"])
        self.assertNotIn(firecrawl, updated["plugins"]["load"]["paths"])
        self.assertNotIn("firecrawl", updated["plugins"]["allow"])
        self.assertNotIn("firecrawl", updated["plugins"]["entries"])

    def test_doctor_detects_stale_imported_webui_functions(self):
        op.setup(self.prefix)
        self.assertEqual(op.webui_function_sync(self.prefix), "not-enrolled")
        database = self.prefix / "state/webui/webui.db"
        database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database) as connection:
            connection.execute(
                "create table function (id text primary key, content text, is_active boolean)"
            )
            connection.executemany(
                "insert into function values (?, ?, ?)",
                [
                    (
                        "sanctum_gate_guard",
                        (self.prefix / "gate/webui/guard.py").read_text(),
                        True,
                    ),
                    ("sanctum_gate_pipe", "stale pipe", True),
                ],
            )
        self.assertEqual(op.webui_function_sync(self.prefix), "stale:sanctum_gate_pipe")
        with sqlite3.connect(database) as connection:
            connection.execute(
                "update function set content = ? where id = ?",
                (
                    (self.prefix / "gate/webui/pipe.py").read_text(),
                    "sanctum_gate_pipe",
                ),
            )
        self.assertEqual(op.webui_function_sync(self.prefix), "pass")

    def test_nonempty_prefix_is_preserved(self):
        self.prefix.mkdir(mode=0o700)
        p = self.prefix / "keep"
        p.write_text("owned")
        with self.assertRaises(ValueError):
            op.setup(self.prefix)
        self.assertEqual(p.read_text(), "owned")

    def test_symlink_and_broad_permissions_rejected(self):
        target = self.prefix.parent / "target"
        target.mkdir(mode=0o700)
        self.prefix.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            op.private(self.prefix)
        self.prefix.unlink()
        self.prefix.mkdir(mode=0o755)
        with self.assertRaises(ValueError):
            op.private(self.prefix)

    def test_offline_timer_state_does_not_prevent_local_shutdown(self):
        op.setup(self.prefix)
        p = self.prefix / "state/gate/gpu.json"
        p.write_text(json.dumps({"phase": "OFFLINE", "pod_id": None, "pod_name": None}))
        op.down(self.prefix)
        p.write_text(
            json.dumps(
                {"phase": "OFFLINE", "pod_id": None, "allocation_uncertain": True}
            )
        )
        with self.assertRaises(ValueError):
            op.down(self.prefix)

    def test_no_gate_template_left_in_rendered_paths(self):
        op.setup(self.prefix)
        for n in [
            "SETTINGS.json",
            "webui/pipe.py",
            "webui/bridge.mjs",
            "plugin/observability.mjs",
        ]:
            text = (self.prefix / "gate" / n).read_text()
            self.assertNotIn("@GATE@", text)
            self.assertNotIn("@PYTHON@", text)
            self.assertNotIn("@SANCTUM_PACKAGE@", text)

    def test_rendered_content_telemetry_resolves_pinned_ajv(self):
        op.setup(self.prefix)
        script = """import {pathToFileURL} from 'node:url';
const root=process.argv[1];
for(const name of ['contract.mjs','quality.mjs','benchmark.mjs']){
  await import(pathToFileURL(root+'/gate/content-telemetry/'+name));
}
"""
        subprocess.run(
            ["node", "--input-type=module", "-e", script, str(self.prefix)],
            cwd=self.prefix.parent,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_content_telemetry_runtime_amendment_is_reversible(self):
        op.setup(self.prefix)
        module_spec = importlib.util.spec_from_file_location(
            "content_telemetry_upgrade",
            ROOT / "scripts/upgrade_content_telemetry_runtime.py",
        )
        upgrade = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(upgrade)
        before = (self.prefix / "receipt.json").read_bytes()
        record = upgrade.apply(self.prefix)
        self.assertTrue((record / "complete").is_file())
        op.verify_install(self.prefix)
        upgrade.rollback(self.prefix, record)
        self.assertEqual((self.prefix / "receipt.json").read_bytes(), before)
        op.verify_install(self.prefix)

    def test_gateway_process_identity_is_exact_and_stale_records_fail(self):
        expected = {
            "schema": op.GATEWAY_PROCESS_SCHEMA,
            "install_receipt_sha256": "a" * 64,
        }
        original = op.expected_gateway_identity
        try:
            op.expected_gateway_identity = lambda prefix, r=None: expected
            self.assertTrue(
                op.gateway_identity_matches(
                    self.prefix, {**expected, "pid": 1, "identity": ["entry"]}
                )
            )
            self.assertFalse(
                op.gateway_identity_matches(
                    self.prefix,
                    {
                        **expected,
                        "install_receipt_sha256": "b" * 64,
                        "pid": 1,
                        "identity": ["entry"],
                    },
                )
            )
            self.assertFalse(
                op.gateway_identity_matches(
                    self.prefix, {"pid": 1, "identity": ["entry"]}
                )
            )
        finally:
            op.expected_gateway_identity = original

    def test_gateway_preloads_observability_only_when_enabled_and_available(self):
        op.setup(self.prefix)
        expected = {
            "node_path": "/reviewed/node",
            "entrypoint_path": "/reviewed/openclaw",
        }
        receipt = {"gateway_port": 28789}
        disabled = op.gateway_command(self.prefix, receipt, expected, {})
        self.assertEqual(disabled[1], "/reviewed/openclaw")
        enabled = op.gateway_command(
            self.prefix, receipt, expected, {"SANCTUM_O11Y_ENABLED": "1"}
        )
        self.assertEqual(enabled[1], "--import")
        self.assertEqual(
            enabled[2],
            str(self.prefix / "gate/plugin/observability-bootstrap.mjs"),
        )
        self.assertEqual(enabled[3], "/reviewed/openclaw")

    def test_component_does_not_adopt_an_executable_from_path(self):
        op.setup(self.prefix)
        bin_dir = self.prefix / "fake-bin"
        bin_dir.mkdir()
        fake = bin_dir / "mlx_lm.server"
        fake.write_text("#!/bin/sh\necho SHOULD_NOT_RUN\n")
        fake.chmod(0o700)
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/component.py"),
                "mlx",
                "--prefix",
                str(self.prefix),
            ],
            env={**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"]},
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bootstrap.py mlx", result.stderr)
        self.assertNotIn("SHOULD_NOT_RUN", result.stdout)

    def test_broker_group_selects_enabled_integrations_and_local_brokers(self):
        config = self.prefix / "config"
        config.mkdir(parents=True)
        (config / "messages.enabled").write_text("enabled\n")
        (config / "gmail.enabled").write_text("disabled\n")
        (config / "calendar.enabled").write_text("enabled\n")
        self.assertEqual(
            component.selected_brokers(self.prefix),
            ["messages", "calendar", "markdown", "files"],
        )

    def test_broker_group_stops_peers_when_one_exits(self):
        config = self.prefix / "config"
        config.mkdir(parents=True)
        children = []

        class Child:
            def __init__(self):
                self.pid = 1000 + len(children)
                self.code = None
                self.terminated = False
                self.killed = False

            def poll(self):
                return self.code

            def terminate(self):
                self.terminated = True
                self.code = -15

            def wait(self, timeout=None):
                return self.code

            def kill(self):
                self.killed = True
                self.code = -9

        def spawn(*_args, **_kwargs):
            child = Child()
            children.append(child)
            return child

        def advance(_seconds):
            children[0].code = 7

        with (
            patch.object(component.subprocess, "Popen", side_effect=spawn) as popen,
            patch.object(component.time, "sleep", side_effect=advance),
            patch.object(component.signal, "signal", return_value=signal.SIG_DFL),
        ):
            result = component.run_brokers(self.prefix, "/reviewed/python", {})
        self.assertEqual(result, 7)
        self.assertEqual(popen.call_count, 2)
        self.assertFalse(children[0].terminated)
        self.assertTrue(children[1].terminated)

    def test_bootstrap_preserves_existing_runtime(self):
        op.setup(self.prefix)
        runtime = self.prefix / "runtime/webui"
        runtime.mkdir(parents=True)
        marker = runtime / "owned"
        marker.write_text("preserve")
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/bootstrap.py"),
                "webui",
                "--prefix",
                str(self.prefix),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Nothing overwritten", result.stderr)
        self.assertEqual(marker.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()


class Amendments(unittest.TestCase):
    setUp = Setup.setUp

    def test_bounded_amendment_and_rollback(self):
        spec = importlib.util.spec_from_file_location(
            "configure_tools", ROOT / "scripts/configure.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        op.setup(self.prefix)
        before = (self.prefix / "config/openclaw.json").read_bytes()
        mod.configure(
            self.prefix,
            {"integrations": ["messages", "files"], "contacts": {"Alex Example": 123}},
        )
        op.verify_install(self.prefix)
        cfg = json.loads((self.prefix / "config/openclaw.json").read_text())
        self.assertIn("steward_move", cfg["tools"]["alsoAllow"])
        self.assertIn("exec", cfg["tools"]["deny"])
        self.assertEqual(
            (self.prefix / "config/messages.enabled").read_text(), "enabled\n"
        )
        log = next((self.prefix / "state/amendments").iterdir())
        mod.rollback(self.prefix, log)
        op.verify_install(self.prefix)
        self.assertEqual(before, (self.prefix / "config/openclaw.json").read_bytes())

    def test_unknown_authority_field_is_rejected_without_mutation(self):
        spec = importlib.util.spec_from_file_location(
            "configure_tools", ROOT / "scripts/configure.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        op.setup(self.prefix)
        before = (self.prefix / "receipt.json").read_bytes()
        with self.assertRaises(ValueError):
            mod.configure(self.prefix, {"tools": ["exec"]})
        with self.assertRaises(ValueError):
            mod.configure(self.prefix, {"integrations": ["shell"]})
        self.assertEqual(before, (self.prefix / "receipt.json").read_bytes())

    def test_observability_secret_is_private_reversible_and_disabled_cleanly(self):
        spec = importlib.util.spec_from_file_location(
            "configure_o11y", ROOT / "scripts/configure.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        op.setup(self.prefix)
        before = (self.prefix / "config/environment.json").read_bytes()
        fake = "sk-fake-super-secret"
        mod.configure(
            self.prefix,
            {
                "observability": {
                    "enabled": True,
                    "realm": "us0",
                    "access_token": fake,
                }
            },
        )
        op.verify_install(self.prefix)
        path = self.prefix / "config/environment.json"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        configured = json.loads(path.read_text())
        self.assertEqual(configured["SANCTUM_O11Y_ENABLED"], "1")
        self.assertEqual(configured["SPLUNK_REALM"], "us0")
        self.assertEqual(configured["SPLUNK_ACCESS_TOKEN"], fake)
        mod.configure(self.prefix, {"observability": {"enabled": False}})
        disabled = json.loads(path.read_text())
        self.assertEqual(disabled["SANCTUM_O11Y_ENABLED"], "0")
        self.assertNotIn("SPLUNK_ACCESS_TOKEN", disabled)
        self.assertNotIn("SPLUNK_REALM", disabled)
        logs = sorted((self.prefix / "state/amendments").iterdir())
        mod.rollback(self.prefix, logs[-1])
        self.assertEqual(json.loads(path.read_text())["SPLUNK_ACCESS_TOKEN"], fake)
        mod.rollback(self.prefix, logs[0])
        self.assertEqual(path.read_bytes(), before)

    def test_observability_rejects_missing_or_malformed_private_values(self):
        spec = importlib.util.spec_from_file_location(
            "configure_o11y_invalid", ROOT / "scripts/configure.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        op.setup(self.prefix)
        before = (self.prefix / "receipt.json").read_bytes()
        for value in (
            {"enabled": True, "realm": "bad realm", "access_token": "x"},
            {"enabled": True, "realm": "us0", "access_token": ""},
            {"enabled": "yes"},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                mod.configure(self.prefix, {"observability": value})
        self.assertEqual((self.prefix / "receipt.json").read_bytes(), before)

    def test_content_telemetry_policy_is_validated_reversible_and_frozen(self):
        spec = importlib.util.spec_from_file_location(
            "configure_content_telemetry", ROOT / "scripts/configure.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        op.setup(self.prefix)
        settings_path = self.prefix / "gate/SETTINGS.json"
        freeze_path = self.prefix / "gate/FREEZE.json"
        before = settings_path.read_bytes()
        mod.configure(
            self.prefix,
            {
                "content_telemetry": {
                    "enabled": True,
                    "retention_days": 30,
                    "access_policy": "owner_only",
                }
            },
        )
        op.verify_install(self.prefix)
        settings = json.loads(settings_path.read_text())
        self.assertEqual(
            settings["content_telemetry"],
            {
                "enabled": True,
                "retention_days": 30,
                "access_policy": "owner_only",
            },
        )
        freeze = json.loads(freeze_path.read_text())
        self.assertEqual(op.sha(settings_path), freeze["SETTINGS.json"])
        log = next((self.prefix / "state/amendments").iterdir())
        mod.rollback(self.prefix, log)
        op.verify_install(self.prefix)
        self.assertEqual(before, settings_path.read_bytes())

    def test_content_telemetry_rejects_unsafe_or_incomplete_policy(self):
        spec = importlib.util.spec_from_file_location(
            "configure_content_telemetry_invalid", ROOT / "scripts/configure.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        op.setup(self.prefix)
        before = (self.prefix / "receipt.json").read_bytes()
        for value in (
            {"enabled": True, "retention_days": None, "access_policy": "owner_only"},
            {"enabled": True, "retention_days": 0, "access_policy": "owner_only"},
            {
                "enabled": True,
                "retention_days": 30,
                "access_policy": "everyone",
            },
            {
                "enabled": "yes",
                "retention_days": 30,
                "access_policy": "owner_only",
            },
            {
                "enabled": False,
                "retention_days": None,
                "access_policy": "owner_only",
                "bucket": "not-allowed",
            },
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                mod.configure(self.prefix, {"content_telemetry": value})
        self.assertEqual((self.prefix / "receipt.json").read_bytes(), before)


class WorkProfileAmendments(unittest.TestCase):
    setUp = Setup.setUp

    def fixture(self):
        spec = importlib.util.spec_from_file_location(
            "configure_work", ROOT / "scripts/configure.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        op.setup(self.prefix)
        policy = {
            "repository": "unused",
            "staging_root": "unused",
            "max_model_calls": 16,
            "max_cost_usd": 1.5,
            "reviewer": True,
            "capabilities": ["worktree_read"],
            "operations": {"test": ["node", "--test"]},
        }
        op.write(
            self.prefix / "config/work-mode.json",
            json.dumps(
                {
                    "schema": "sanctum-work-mode-profiles/v1",
                    "profiles": {"reviewed": policy},
                }
            ),
        )
        receipt = op.receipt(self.prefix)
        receipt["files"]["config/work-mode.json"] = op.sha(
            self.prefix / "config/work-mode.json"
        )
        (self.prefix / "receipt.json").write_text(json.dumps(receipt))
        repo = op.private(self.prefix / "test-repo")
        (repo / "index.js").write_text("export const value=1;")
        for args in (
            ["init", "-q"],
            ["add", "."],
            [
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "baseline",
            ],
        ):
            subprocess.run(
                ["/usr/bin/git", *args], cwd=repo, check=True, capture_output=True
            )
        op.private(
            self.prefix / "state/gate/private-lead/work-mode/registered/unseen/staging"
        )
        return (
            mod,
            repo,
            policy,
            {
                "work_profile": {
                    "name": "unseen",
                    "copy_from": "reviewed",
                    "repository": str(repo),
                }
            },
        )

    def test_registration_preserves_policy_and_rolls_back(self):
        mod, repo, policy, proposal = self.fixture()
        before = (self.prefix / "config/work-mode.json").read_bytes()
        mod.configure(self.prefix, proposal)
        op.verify_install(self.prefix)
        profiles = json.loads((self.prefix / "config/work-mode.json").read_text())[
            "profiles"
        ]
        self.assertEqual(profiles["reviewed"], policy)
        self.assertEqual(
            {
                k: v
                for k, v in profiles["unseen"].items()
                if k not in ("repository", "staging_root")
            },
            {
                k: v
                for k, v in policy.items()
                if k not in ("repository", "staging_root")
            },
        )
        self.assertEqual(profiles["unseen"]["repository"], str(repo))
        self.assertEqual(
            (self.prefix / "config/work-mode.json").stat().st_mode & 0o777, 0o600
        )
        mod.rollback(self.prefix, next((self.prefix / "state/amendments").iterdir()))
        op.verify_install(self.prefix)
        self.assertEqual((self.prefix / "config/work-mode.json").read_bytes(), before)

    def test_invalid_registration_leaves_receipt_and_profiles_untouched(self):
        mod, repo, policy, proposal = self.fixture()
        before = {
            n: (self.prefix / n).read_bytes()
            for n in ("receipt.json", "config/work-mode.json")
        }
        item = proposal["work_profile"]
        bad = [
            {**item, "name": "reviewed"},
            {**item, "copy_from": "missing"},
            {**item, "max_model_calls": 99},
            {**item, "repository": str(ROOT)},
            {**item, "name": "../escape"},
        ]
        link = self.prefix / "linked"
        link.symlink_to(repo, target_is_directory=True)
        bad.append({**item, "repository": str(link)})
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                mod.configure(self.prefix, {"work_profile": value})
        (repo / "untracked").write_text("dirty")
        with self.assertRaises(ValueError):
            mod.configure(self.prefix, proposal)
        for n, raw in before.items():
            self.assertEqual((self.prefix / n).read_bytes(), raw)
        self.assertFalse((self.prefix / "state/amendments").exists())


class WorkBudgetAmendments(unittest.TestCase):
    setUp = Setup.setUp
    fixture = WorkProfileAmendments.fixture

    def budget_fixture(self):
        import sqlite3

        mod, repo, policy, proposal = self.fixture()
        mod.configure(self.prefix, proposal)
        settings = json.loads((self.prefix / "gate/SETTINGS.json").read_text())
        lead = Path(settings["state_directory"]) / "private-lead"
        lead.mkdir(parents=True, exist_ok=True, mode=0o700)
        (lead / "gpu.json").write_text(
            json.dumps(
                {
                    "phase": "READY",
                    "pod_id": "synthetic-pod",
                    "allocation_uncertain": False,
                }
            )
        )
        with sqlite3.connect(lead / "control.sqlite") as c:
            c.execute(
                "create table leases(scope text,active integer,closing integer,expires real)"
            )
            c.execute(
                "insert into leases values(?,?,?,?)", ("a" * 64, 1, 0, 4102444800)
            )
        proposal = {
            "work_budget": {
                "profile": "unseen",
                "max_iterations": 32,
                "max_model_calls": 32,
                "max_tokens": 200000,
                "retained_scope": "a" * 64,
            }
        }
        return mod, lead, proposal

    def test_retained_budget_change_preserves_every_other_profile_field(self):
        from unittest.mock import patch

        mod, lead, proposal = self.budget_fixture()
        before = json.loads((self.prefix / "config/work-mode.json").read_text())
        old = (self.prefix / "receipt.json").read_bytes()
        with (
            patch.object(mod, "active_janitor", return_value=True),
            patch.object(
                mod.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stdout=""),
            ),
        ):
            mod.configure(self.prefix, proposal)
        op.verify_install(self.prefix)
        after = json.loads((self.prefix / "config/work-mode.json").read_text())
        changed = after["profiles"]["unseen"]
        expected = {
            **before["profiles"]["unseen"],
            "max_iterations": 32,
            "max_model_calls": 32,
            "max_tokens": 200000,
        }
        self.assertEqual(changed, expected)
        self.assertEqual(after["profiles"]["reviewed"], before["profiles"]["reviewed"])
        logs = sorted((self.prefix / "state/amendments").iterdir())
        mod.rollback(self.prefix, logs[-1])
        self.assertEqual((self.prefix / "receipt.json").read_bytes(), old)
        op.verify_install(self.prefix)

    def test_budget_refuses_unknown_ownership_worker_and_excess_limits(self):
        from unittest.mock import patch

        mod, lead, proposal = self.budget_fixture()
        before = (self.prefix / "receipt.json").read_bytes()
        item = proposal["work_budget"]
        with (
            patch.object(mod, "active_janitor", return_value=True),
            patch.object(
                mod.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stdout=""),
            ),
        ):
            for value in (
                {**item, "max_iterations": 33},
                {**item, "max_model_calls": 33},
                {**item, "max_tokens": 200001},
                {**item, "retained_scope": "b" * 64},
                {**item, "profile": "reviewed"},
            ):
                with self.assertRaises(ValueError):
                    mod.configure(self.prefix, {"work_budget": value})
        with (
            patch.object(mod, "active_janitor", return_value=True),
            patch.object(
                mod.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    [], 0, stdout="python -B " + str(self.prefix / "gate/worker.py")
                ),
            ),
        ):
            with self.assertRaises(ValueError):
                mod.configure(self.prefix, proposal)
        with patch.object(mod, "active_janitor", return_value=False):
            with self.assertRaises(ValueError):
                mod.configure(self.prefix, proposal)
        self.assertEqual((self.prefix / "receipt.json").read_bytes(), before)

    def test_host_interface_amendment_requires_named_freeze_and_preserves_configuration(
        self,
    ):
        from unittest.mock import patch

        mod, lead, budget = self.budget_fixture()
        item = budget["work_budget"]
        before = (self.prefix / "config/work-mode.json").read_bytes()
        receipt = (self.prefix / "receipt.json").read_bytes()
        proposal = {
            "work_host": {
                "profile": item["profile"],
                "retained_scope": item["retained_scope"],
                "source_manifest_sha256": "0" * 64,
            }
        }
        with self.assertRaises(ValueError):
            mod.configure(self.prefix, proposal)
        self.assertEqual((self.prefix / "receipt.json").read_bytes(), receipt)
        proposal["work_host"]["source_manifest_sha256"] = op.sha(
            ROOT / "SOURCE-MANIFEST.json"
        )
        with (
            patch.object(mod, "active_janitor", return_value=True),
            patch.object(
                mod.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stdout=""),
            ),
        ):
            mod.configure(self.prefix, proposal)
        op.verify_install(self.prefix)
        self.assertEqual((self.prefix / "config/work-mode.json").read_bytes(), before)
        log = sorted((self.prefix / "state/amendments").iterdir())[-1]
        tx = json.loads((log / "transaction.json").read_text())
        self.assertEqual(
            set(tx["after"]),
            {"gate/src/backends.py", "gate/plugin/work-mode.mjs", "gate/FREEZE.json"},
        )
        mod.rollback(self.prefix, log)
        op.verify_install(self.prefix)
        self.assertEqual((self.prefix / "receipt.json").read_bytes(), receipt)


class WorkIntegrityAmendments(unittest.TestCase):
    setUp = Setup.setUp
    fixture = WorkProfileAmendments.fixture

    def test_explicit_task_contract_registration_preserves_limits_and_rolls_back(self):
        mod, repo, policy, proposal = self.fixture()
        evidence = mod.protection_module()
        contract = evidence.unrestricted_contract()
        contract.update(protected=["index.js"], mutable=[], allow_new=True)
        proposal["work_profile"]["task_protection"] = contract
        before = (self.prefix / "config/work-mode.json").read_bytes()
        mod.configure(self.prefix, proposal)
        op.verify_install(self.prefix)
        current = json.loads((self.prefix / "config/work-mode.json").read_text())[
            "profiles"
        ]["unseen"]
        self.assertEqual(current["task_protection"], contract)
        self.assertEqual(current["max_model_calls"], policy["max_model_calls"])
        self.assertEqual(current["max_cost_usd"], policy["max_cost_usd"])
        mod.rollback(self.prefix, next((self.prefix / "state/amendments").iterdir()))
        self.assertEqual(before, (self.prefix / "config/work-mode.json").read_bytes())

    def test_integrity_amendment_has_fixed_closure_preserves_profiles_and_rolls_back(
        self,
    ):
        from unittest.mock import patch

        mod, repo, policy, proposal = self.fixture()
        profiles = json.loads((self.prefix / "config/work-mode.json").read_text())
        for name in [*(f"grade{n:02d}" for n in range(1, 11)), "adversarial"]:
            profiles["profiles"][name] = {
                **policy,
                "repository": str(
                    self.prefix
                    / "state/gate/private-lead/work-mode/qualification"
                    / name
                    / "repo"
                ),
            }
        (self.prefix / "config/work-mode.json").write_text(json.dumps(profiles))
        receipt = op.receipt(self.prefix)
        receipt["files"]["config/work-mode.json"] = op.sha(
            self.prefix / "config/work-mode.json"
        )
        (self.prefix / "receipt.json").write_text(json.dumps(receipt))
        op.write(
            self.prefix / "state/gate/gpu.json",
            json.dumps({"phase": "RETIRED", "retired_confirmed_at": 1}),
        )
        op.write(
            self.prefix / "state/gate/private-lead/gpu.json",
            json.dumps({"phase": "OFFLINE"}),
        )
        before = {
            n: (self.prefix / n).read_bytes()
            for n in (
                "config/work-mode.json",
                "gate/SETTINGS.json",
                "receipt.json",
                "gate/FREEZE.json",
            )
        }
        item = {"source_manifest_sha256": op.sha(ROOT / "SOURCE-MANIFEST.json")}
        with self.assertRaises(ValueError):
            mod.configure(self.prefix, {"work_integrity": {**item, "extra": True}})
        with self.assertRaises(ValueError):
            mod.configure(
                self.prefix, {"work_integrity": {"source_manifest_sha256": "0" * 64}}
            )
        # Exercise the Mac amendment contract on every offline test host.
        with (
            patch("platform.system", return_value="Darwin"),
            patch.object(
                mod.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stdout=""),
            ),
        ):
            mod.configure(self.prefix, {"work_integrity": item})
        op.verify_install(self.prefix)
        after = json.loads((self.prefix / "config/work-mode.json").read_text())
        for name, profile in after["profiles"].items():
            self.assertEqual(
                {k: v for k, v in profile.items() if k != "task_protection"},
                profiles["profiles"][name],
            )
            self.assertEqual(
                profile["task_protection"]["protected"],
                [] if name == "reviewed" else ["index.test.js", "package.json"],
            )
        self.assertEqual(
            before["gate/SETTINGS.json"],
            (self.prefix / "gate/SETTINGS.json").read_bytes(),
        )
        log = next((self.prefix / "state/amendments").iterdir())
        tx = json.loads((log / "transaction.json").read_text())
        self.assertEqual(
            set(tx["after"]),
            {"gate/" + n for n in mod.INTEGRITY_FILES}
            | {"gate/FREEZE.json", "config/work-mode.json"},
        )
        mod.rollback(self.prefix, log)
        op.verify_install(self.prefix)
        for n, raw in before.items():
            self.assertEqual(raw, (self.prefix / n).read_bytes())

    def test_editing_amendment_preserves_contracts_limits_and_rollback(self):
        from unittest.mock import patch

        mod, repo, policy, proposal = self.fixture()
        profiles = json.loads((self.prefix / "config/work-mode.json").read_text())
        for profile in profiles["profiles"].values():
            profile["capabilities"] = [
                "worktree_read",
                "worktree_patch",
                "worktree_command",
            ]
        (self.prefix / "config/work-mode.json").write_text(json.dumps(profiles))
        receipt = op.receipt(self.prefix)
        receipt["files"]["config/work-mode.json"] = op.sha(
            self.prefix / "config/work-mode.json"
        )
        (self.prefix / "receipt.json").write_text(json.dumps(receipt))
        op.write(
            self.prefix / "state/gate/gpu.json",
            json.dumps({"phase": "RETIRED", "retired_confirmed_at": 1}),
        )
        op.write(
            self.prefix / "state/gate/private-lead/gpu.json",
            json.dumps({"phase": "OFFLINE"}),
        )
        before = {
            n: (self.prefix / n).read_bytes()
            for n in (
                "config/work-mode.json",
                "config/openclaw.json",
                "gate/SETTINGS.json",
                "receipt.json",
                "gate/FREEZE.json",
            )
        }
        item = {"source_manifest_sha256": op.sha(ROOT / "SOURCE-MANIFEST.json")}
        with self.assertRaises(ValueError):
            mod.configure(
                self.prefix, {"work_editing": {"source_manifest_sha256": "0" * 64}}
            )
        with (
            patch("platform.system", return_value="Darwin"),
            patch.object(
                mod.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0, stdout=""),
            ),
        ):
            mod.configure(self.prefix, {"work_editing": item})
        op.verify_install(self.prefix)
        after = json.loads((self.prefix / "config/work-mode.json").read_text())
        for name, profile in after["profiles"].items():
            self.assertEqual(
                {k: v for k, v in profile.items() if k != "capabilities"},
                {
                    k: v
                    for k, v in profiles["profiles"][name].items()
                    if k != "capabilities"
                },
            )
            self.assertEqual(
                profile["capabilities"],
                ["worktree_read", "worktree_edit", "worktree_command"],
            )
        self.assertEqual(
            before["gate/SETTINGS.json"],
            (self.prefix / "gate/SETTINGS.json").read_bytes(),
        )
        log = next((self.prefix / "state/amendments").iterdir())
        tx = json.loads((log / "transaction.json").read_text())
        self.assertEqual(
            set(tx["after"]),
            {"gate/" + n for n in mod.EDIT_FILES}
            | {"gate/FREEZE.json", "config/work-mode.json", "config/openclaw.json"},
        )
        mod.rollback(self.prefix, log)
        op.verify_install(self.prefix)
        for n, raw in before.items():
            self.assertEqual(raw, (self.prefix / n).read_bytes())

    def test_integrity_amendment_refuses_active_ownership(self):
        from unittest.mock import patch

        mod, repo, policy, proposal = self.fixture()
        op.write(
            self.prefix / "state/gate/gpu.json",
            json.dumps({"phase": "RETIRED", "retired_confirmed_at": 1}),
        )
        op.write(
            self.prefix / "state/gate/private-lead/gpu.json",
            json.dumps({"phase": "READY", "pod_id": "synthetic"}),
        )
        before = (self.prefix / "receipt.json").read_bytes()
        with (
            patch("platform.system", return_value="Darwin"),
            self.assertRaisesRegex(ValueError, "Unresolved GPU ownership"),
        ):
            mod.configure(
                self.prefix,
                {
                    "work_integrity": {
                        "source_manifest_sha256": op.sha(ROOT / "SOURCE-MANIFEST.json")
                    }
                },
            )
        self.assertEqual(before, (self.prefix / "receipt.json").read_bytes())

    def test_live_amendments_refuse_non_macos_without_effects(self):
        from unittest.mock import patch

        mod, repo, policy, proposal = self.fixture()
        before = {
            p.relative_to(self.prefix): p.read_bytes()
            for p in self.prefix.rglob("*")
            if p.is_file()
        }
        with (
            patch("platform.system", return_value="Linux"),
            patch.object(mod.subprocess, "run") as commands,
        ):
            for field in ("work_integrity", "work_editing"):
                with (
                    self.subTest(amendment=field),
                    self.assertRaisesRegex(ValueError, "live amendment requires macOS"),
                ):
                    mod.configure(
                        self.prefix,
                        {
                            field: {
                                "source_manifest_sha256": op.sha(
                                    ROOT / "SOURCE-MANIFEST.json"
                                )
                            }
                        },
                    )
            commands.assert_not_called()
        self.assertEqual(
            before,
            {
                p.relative_to(self.prefix): p.read_bytes()
                for p in self.prefix.rglob("*")
                if p.is_file()
            },
        )


class Publication(unittest.TestCase):
    @staticmethod
    def audit_module():
        spec = importlib.util.spec_from_file_location(
            "publication_audit", ROOT / "scripts/audit.py"
        )
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        return audit

    def test_project_python_names_do_not_shadow_standard_library(self):
        excluded = {
            ".git",
            ".venv",
            "node_modules",
            "build",
            "dist",
            ".local",
            "__pycache__",
        }
        collisions = []
        for path in ROOT.rglob("*.py"):
            relative = path.relative_to(ROOT)
            if (
                not set(relative.parts) & excluded
                and path.stem in sys.stdlib_module_names
            ):
                collisions.append(str(relative))
        self.assertEqual(collisions, [])

    def test_script_directory_can_import_pathlib_in_isolated_startup(self):
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                "-B",
                "-c",
                "from pathlib import Path; print(Path.__name__)",
            ],
            cwd=ROOT / "scripts",
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "Path")

    def test_finder_metadata_is_rejected(self):
        audit = self.audit_module()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / ".DS_Store").write_bytes(b"\x00\x80metadata")
            self.assertIn(
                (".DS_Store", "private/generated Finder metadata"), audit.scan(base)
            )

    def test_owner_home_paths_have_no_documentation_exceptions(self):
        audit = self.audit_module()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "docs").mkdir()
            baseline = base / "docs/history.md"
            baseline.write_text("/Users/" + "owner/private/runtime")
            agents = base / "AGENTS.md"
            agents.write_text("/Users/" + "owner/Projects/sanctum")
            self.assertIn(("docs/history.md", "owner_home"), audit.scan(base))
            self.assertIn(("AGENTS.md", "owner_home"), audit.scan(base))

    def test_common_secret_classes_are_rejected_without_echoing_values(self):
        audit = self.audit_module()
        samples = {
            "linear.txt": "lin_" + "api_" + "A" * 32,
            "github.txt": "github_" + "pat_" + "B" * 40,
            "firecrawl.txt": "fc-" + "C" * 32,
            "runpod.env.example": "RUNPOD_API_KEY=" + "D" * 32,
            "pgp.txt": "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----",
        }
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for name, value in samples.items():
                (base / name).write_text(value)
            issues = audit.scan(base)
        self.assertEqual(
            issues,
            [
                ("firecrawl.txt", "provider_key"),
                ("github.txt", "github_token"),
                ("linear.txt", "linear_token"),
                ("pgp.txt", "private_key"),
                ("runpod.env.example", "credential_assignment"),
            ],
        )
        rendered = repr(issues)
        for value in samples.values():
            self.assertNotIn(value, rendered)

    def test_secret_placeholders_are_allowed(self):
        audit = self.audit_module()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "instructions.txt").write_text(
                "export LINEAR_API_KEY=...\n"
                "FIRECRAWL_API_KEY=fc-YOUR-API-KEY\n"
                "SPLUNK_ACCESS_TOKEN=<token>\n"
            )
            self.assertEqual(audit.scan(base), [])


class IntegrationAmendments(unittest.TestCase):
    setUp = Setup.setUp

    def module(self):
        spec = importlib.util.spec_from_file_location(
            "integration_config", ROOT / "scripts/configure.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_web_uses_parallel_search_and_core_fetch(self):
        op.setup(self.prefix)
        plugin = self.prefix / "runtime/web/node_modules/@openclaw/parallel-plugin"
        plugin.mkdir(parents=True)
        (plugin / "package.json").write_text(
            json.dumps({"name": "@openclaw/parallel-plugin", "version": "2026.8.1"})
        )
        self.module().configure(self.prefix, {"integrations": ["web"]})
        cfg = json.loads((self.prefix / "config/openclaw.json").read_text())
        self.assertEqual(cfg["tools"]["web"]["search"]["provider"], "parallel")
        self.assertNotIn("provider", cfg["tools"]["web"]["fetch"])
        self.assertNotIn("firecrawl", cfg["plugins"]["entries"])
        self.assertNotIn("firecrawl", cfg["plugins"]["allow"])
        op.verify_install(self.prefix)

    def test_isolated_mcp_notes_and_tunnel_rollback(self):
        op.setup(self.prefix)
        before = (self.prefix / "receipt.json").read_bytes()
        notes = self.prefix.parent / "notes"
        notes.mkdir()
        self.module().configure(
            self.prefix,
            {
                "integrations": ["mcp"],
                "notes_dir": str(notes),
                "gpu": {"local_port": 28001},
            },
        )
        op.verify_install(self.prefix)
        cfg = json.loads((self.prefix / "config/openclaw.json").read_text())
        server = cfg["mcp"]["servers"]["vinceai"]
        self.assertEqual(
            server["toolFilter"]["include"],
            ["get_current_time", "convert_to_markdown", "hub_repo_search"],
        )
        self.assertIn(str(self.prefix), server["args"])
        self.assertIn("exec", cfg["tools"]["deny"])
        self.assertTrue(
            json.loads((self.prefix / "config/mcp-profile.json").read_text())[
                "id"
            ].startswith("sanctum-")
        )
        self.assertEqual(op.environment(self.prefix)["VINCEAI_NOTES_DIR"], str(notes))
        self.assertFalse(
            json.loads((self.prefix / "gate/SETTINGS.json").read_text())["gpu"][
                "auto_start"
            ]
        )
        self.module().rollback(
            self.prefix, next((self.prefix / "state/amendments").iterdir())
        )
        self.assertEqual(before, (self.prefix / "receipt.json").read_bytes())

    def test_reject_source_symlink_and_overlapping_port_without_mutation(self):
        op.setup(self.prefix)
        before = (self.prefix / "receipt.json").read_bytes()
        link = self.prefix.parent / "link"
        link.symlink_to(self.prefix)
        for proposal in [
            {"notes_dir": str(ROOT)},
            {"notes_dir": str(link)},
            {"notes_dir": "relative"},
            {"gpu": {"local_port": True}},
            {"gpu": {"local_port": 28080}},
            {"gpu": {"local_port": 28000}},
            {"gpu": {"local_port": 70000}},
            {"integrations": ["mcp"], "command": "exec"},
        ]:
            with self.assertRaises(ValueError):
                self.module().configure(self.prefix, proposal)
            self.assertEqual(before, (self.prefix / "receipt.json").read_bytes())

    def test_mcp_profile_signature_covers_transport_mounts_and_tools(self):
        spec = importlib.util.spec_from_file_location(
            "mcp_gateway", ROOT / "scripts/mcp_gateway.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        base = json.loads((ROOT / "mcp-integration/config/profile.json").read_text())
        for field, value in [
            ("endpoint", "https://example.com"),
            ("tools", ["unreviewed"]),
            ("image", "unreviewed"),
        ]:
            changed = json.loads(json.dumps(base))
            changed["servers"][0][field] = value
            self.assertNotEqual(mod.signature(base), mod.signature(changed))
        changed = json.loads(json.dumps(base))
        changed["servers"][2]["snapshot"]["server"]["volumes"] = ["/:/mcp-input"]
        self.assertNotEqual(mod.signature(base), mod.signature(changed))
