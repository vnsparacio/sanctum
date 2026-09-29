"""Synthetic task-bound Qwen snapshot handoff; no model or paid resource."""

import hashlib
import hmac
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import qwen_snapshot
import task_evidence
import worktree_edit
from authority import authorize
from common import Refused, canonical


class QwenSnapshot(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / "workspace"
        self.root.mkdir()
        self.settings = {"state_directory": str(self.base / "private")}
        (self.base / "private").mkdir(mode=0o700)
        self.key = os.urandom(32)
        (self.base / "private" / "authority.key").write_bytes(self.key)
        (self.base / "private" / "authority.key").chmod(0o600)
        self.record = {
            "workspace_id": "a" * 32,
            "root": str(self.root),
            "profile": "synthetic",
        }
        self.contract = {
            "schema": task_evidence.VERSION,
            "protected": ["oracle.test.js"],
            "mutable": ["app.js", "README.md"],
            "mutable_tests": [],
            "allow_new": True,
            "acceptance": None,
        }
        (self.root / "app.js").write_text("export const value = 1;\n")
        (self.root / "README.md").write_text("Initial app.\n")
        (self.root / "oracle.test.js").write_text("protected acceptance\n")
        (self.root / "vendor").mkdir()
        (self.root / "vendor" / "keep.txt").write_text("unmodified dependency\n")
        subprocess.run(["/usr/bin/git", "init", "-q"], cwd=self.root, check=True)
        task_evidence.snapshot(self.settings, self.record, self.contract)

    def output(self):
        exported = qwen_snapshot.export(self.settings, self.record)
        input_root = Path(exported["input"])
        output_root = Path(exported["output"])
        shutil.copytree(input_root, output_root)
        return exported, output_root

    def refused(self, code, fn):
        with self.assertRaises(Refused) as caught:
            fn()
        self.assertEqual(str(caught.exception), code)

    def test_exact_import_uses_mac_patch_authority_and_is_one_use(self):
        exported, output = self.output()
        self.refused(
            "qwen_snapshot_exists",
            lambda: qwen_snapshot.export(self.settings, self.record),
        )
        self.assertFalse((Path(exported["input"]) / ".git").exists())
        self.assertTrue(Path(exported["input"]).is_relative_to(self.base / "private"))
        self.assertEqual(
            (output / "oracle.test.js").read_text(), "protected acceptance\n"
        )
        (output / "app.js").write_text("export const value = 2;\n")
        (output / "README.md").write_text("Persistent app.\n")
        (output / "new.js").write_text("export const created = true;\n")
        result = qwen_snapshot.import_output(self.settings, self.record)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["receipt"]["authorityResult"], "ALLOW")
        self.assertEqual(result["receipt"]["paths"], ["README.md", "app.js", "new.js"])
        self.assertEqual(
            (self.root / "app.js").read_text(), "export const value = 2;\n"
        )
        self.assertEqual(
            (self.root / "new.js").read_text(), "export const created = true;\n"
        )
        self.assertEqual(
            (self.root / "oracle.test.js").read_text(), "protected acceptance\n"
        )
        self.assertEqual(
            task_evidence.check(self.settings, self.record)["integrity"], "PASS"
        )
        self.refused(
            "qwen_snapshot_import_replayed",
            lambda: qwen_snapshot.import_output(self.settings, self.record),
        )

    def test_protected_edit_and_symlink_are_refused_before_import(self):
        _, output = self.output()
        (output / "oracle.test.js").write_text("weakened\n")
        self.refused(
            "qwen_snapshot_path_denied",
            lambda: qwen_snapshot.import_output(self.settings, self.record),
        )
        self.assertEqual(
            (self.root / "oracle.test.js").read_text(), "protected acceptance\n"
        )
        (output / "oracle.test.js").unlink()
        (output / "oracle.test.js").symlink_to(self.root / "oracle.test.js")
        self.refused(
            "qwen_snapshot_type",
            lambda: qwen_snapshot.import_output(self.settings, self.record),
        )

    def test_deleted_file_new_directory_and_git_metadata_are_refused(self):
        _, output = self.output()
        (output / "app.js").unlink()
        self.refused(
            "qwen_snapshot_deletion",
            lambda: qwen_snapshot.import_output(self.settings, self.record),
        )
        (output / "app.js").write_text("export const value = 1;\n")
        (output / "extra").mkdir()
        self.refused(
            "qwen_snapshot_structure",
            lambda: qwen_snapshot.import_output(self.settings, self.record),
        )
        (output / "extra").rmdir()
        (output / ".git").symlink_to(self.root / ".git")
        self.refused(
            "qwen_snapshot_output_invalid",
            lambda: qwen_snapshot.import_output(self.settings, self.record),
        )

    def test_no_edit_vendor_path_and_stale_workspace_are_refused(self):
        _, output = self.output()
        self.refused(
            "qwen_snapshot_no_edit",
            lambda: qwen_snapshot.import_output(self.settings, self.record),
        )
        (output / "vendor" / "new.js").write_text("vendor\n")
        self.refused(
            "qwen_snapshot_path_denied",
            lambda: qwen_snapshot.import_output(self.settings, self.record),
        )
        (output / "vendor" / "new.js").unlink()
        (self.root / "app.js").write_text("out of band\n")
        self.refused(
            "qwen_snapshot_baseline_changed",
            lambda: qwen_snapshot.import_output(self.settings, self.record),
        )

    def test_race_at_mac_patch_lock_refuses_import_and_blocks_replay(self):
        _, output = self.output()
        (output / "app.js").write_text("export const value = 2;\n")
        original = worktree_edit.apply_patch

        def race(*args, **kwargs):
            (self.root / "app.js").write_text("concurrent edit\n")
            return original(*args, **kwargs)

        with patch.object(qwen_snapshot.worktree_edit, "apply_patch", race):
            result = qwen_snapshot.import_output(self.settings, self.record)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "EDIT_APPLY_RACE")
        self.assertEqual((self.root / "app.js").read_text(), "concurrent edit\n")
        self.refused(
            "qwen_snapshot_import_replayed",
            lambda: qwen_snapshot.import_output(self.settings, self.record),
        )

    def test_changed_output_between_reads_is_refused(self):
        _, output = self.output()
        (output / "app.js").write_text("export const value = 2;\n")
        inventory = task_evidence.inventory
        reads = 0

        def changed(root):
            nonlocal reads
            if Path(root) == output:
                reads += 1
                if reads == 2:
                    (output / "README.md").write_text("changed after inventory\n")
            return inventory(root)

        with patch.object(qwen_snapshot.task_evidence, "inventory", changed):
            self.refused(
                "qwen_snapshot_race",
                lambda: qwen_snapshot.import_output(self.settings, self.record),
            )
        self.assertEqual(
            (self.root / "app.js").read_text(), "export const value = 1;\n"
        )

    def test_cross_task_identity_is_refused(self):
        self.output()
        wrong = {**self.record, "workspace_id": "b" * 32}
        self.refused(
            "qwen_snapshot_identity",
            lambda: qwen_snapshot.import_output(self.settings, wrong),
        )

    def test_signed_routes_allow_only_task_bound_profile_without_host_paths(self):
        for operation in ("worktree_qwen_export", "worktree_qwen_import"):
            body = {
                "operation": operation,
                "tier": "PRIVATE_LEAD",
                "packet": {"task_id": "a" * 32, "profile": "synthetic"},
                "state": {
                    "scope": "a" * 32,
                    "revision": 0,
                    "privacy_floor": "PERSONAL",
                    "high_stakes": False,
                },
                "nonce": os.urandom(32).hex(),
                "expires": 200,
                "spec_sha256": "f" * 64,
                "scope": "a" * 32,
                "approval": "private_lead_workmode",
                "strong": False,
            }

            def check(value):
                raw = canonical(value)
                signed = {
                    "body": raw,
                    "mac": hmac.new(self.key, raw.encode(), hashlib.sha256).hexdigest(),
                }
                return authorize(
                    signed, self.settings, now=lambda: 100, settings_hash="f" * 64
                )

            for change in (
                {"packet": {**body["packet"], "output": "/tmp/forged"}},
                {"packet": {"task_id": "b" * 32, "profile": "synthetic"}},
                {"tier": "PRIVATE_80B"},
                {"approval": "model_grant"},
            ):
                self.refused_any(lambda: check({**body, **change}))
            self.assertEqual(check(body)["operation"], operation)

    def test_qwen_run_route_requires_exact_task_goal_and_no_host_path(self):
        body = {
            "operation": "worktree_qwen_run",
            "tier": "PRIVATE_LEAD",
            "packet": {
                "task_id": "a" * 32,
                "profile": "synthetic",
                "goal": "Fix MoodLog",
            },
            "state": {
                "scope": "a" * 32,
                "revision": 0,
                "privacy_floor": "PERSONAL",
                "high_stakes": False,
            },
            "nonce": os.urandom(32).hex(),
            "expires": 200,
            "spec_sha256": "f" * 64,
            "scope": "a" * 32,
            "approval": "private_lead_workmode",
            "strong": False,
        }

        def check(value):
            raw = canonical(value)
            signed = {
                "body": raw,
                "mac": hmac.new(self.key, raw.encode(), hashlib.sha256).hexdigest(),
            }
            return authorize(
                signed, self.settings, now=lambda: 100, settings_hash="f" * 64
            )

        for packet in (
            {**body["packet"], "workspace": "/tmp/forged"},
            {**body["packet"], "task_id": "b" * 32},
            {**body["packet"], "goal": ""},
            {**body["packet"], "goal": "x" * 32769},
        ):
            self.refused_any(lambda: check({**body, "packet": packet}))
        self.assertEqual(check(body)["operation"], "worktree_qwen_run")

    def refused_any(self, fn):
        with self.assertRaises(Refused):
            fn()


if __name__ == "__main__":
    unittest.main()
