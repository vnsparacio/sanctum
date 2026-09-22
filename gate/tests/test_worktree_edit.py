"""Synthetic exact-edit boundary tests; no model, credential or provider use."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import task_evidence as evidence
import worktree_edit as editor


class ExactEdit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.settings = {"state_directory": str(self.base / "private")}
        self.record = {
            "root": str(self.root),
            "workspace_id": "a" * 32,
            "profile": "synthetic",
        }
        self.contract = {
            "schema": evidence.VERSION,
            "protected": ["oracle.test.js"],
            "mutable": ["a.js", "b.js"],
            "mutable_tests": [],
            "allow_new": True,
            "acceptance": None,
        }
        self.initial = b"  const x = 10;\n\treturn x;\n"
        for name, raw in [
            ("a.js", self.initial),
            ("b.js", b"const y = 1;\n"),
            ("oracle.test.js", b"original\n"),
        ]:
            (self.root / name).write_bytes(raw)
        for args in [
            ["init", "-q"],
            ["add", "."],
            [
                "-c",
                "user.name=Synthetic",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
        ]:
            subprocess.run(
                ["/usr/bin/git", *args], cwd=self.root, check=True, capture_output=True
            )
        evidence.snapshot(self.settings, self.record, self.contract)

    def read(self, path="a.js", max_chars=12000, confirm=True):
        r = editor.read(self.settings, self.record, path, max_chars)
        if confirm:
            editor.observe(self.settings, self.record, path, r["_observation"])
        return r

    def edit(self, old="10", new="30", path="a.js", **kw):
        return editor.apply(
            self.settings,
            self.record,
            {"path": path, "old_text": old, "new_text": new},
            **kw,
        )

    def fileop(self, operation, path, **arguments):
        return editor.apply(
            self.settings,
            self.record,
            {"operation": operation, "path": path, **arguments},
        )

    def assert_diff_receipt(self, result):
        directory = evidence.store_root(self.settings) / self.record["workspace_id"]
        diff = (
            directory / f"edit-{result['receipt']['workspace_generation']}.diff"
        ).read_bytes()
        self.assertEqual(
            result["receipt"]["canonical_diff_digest"], hashlib.sha256(diff).hexdigest()
        )
        subprocess.run(
            ["/usr/bin/git", "apply", "--reverse", "--check", "-"],
            cwd=self.root,
            input=diff,
            check=True,
            capture_output=True,
        )
        return diff

    def rejected(self, code, **kwargs):
        before = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        result = self.edit(**kwargs)
        self.assertEqual(result["code"], code, result)
        self.assertEqual(result["executionState"], "NOT_STARTED")
        self.assertEqual(
            before, {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        )

    def test_one_line_and_diff(self):
        self.read()
        r = self.edit()
        self.assertTrue(r["ok"], r)
        self.assertEqual(
            (self.root / "a.js").read_bytes(), self.initial.replace(b"10", b"30")
        )
        directory = evidence.store_root(self.settings) / self.record["workspace_id"]
        diff = (directory / "edit-1.diff").read_bytes()
        self.assertEqual(
            r["receipt"]["canonical_diff_digest"], hashlib.sha256(diff).hexdigest()
        )
        subprocess.run(
            ["/usr/bin/git", "apply", "--reverse", "--check", "-"],
            cwd=self.root,
            input=diff,
            check=True,
            capture_output=True,
        )
        self.assertEqual(
            evidence.check(self.settings, self.record)["integrity"], "PASS"
        )

    def test_create_delete_and_move_with_host_diffs(self):
        created = self.fileop("create", "created.js", new_text="export const n = 1;\n")
        self.assertTrue(created["ok"], created)
        self.assertEqual(
            (self.root / "created.js").read_text(), "export const n = 1;\n"
        )
        self.assertIn(b"created.js", self.assert_diff_receipt(created))

        self.read("created.js")
        moved = self.fileop("move", "created.js", destination="nested.js")
        self.assertTrue(moved["ok"], moved)
        self.assertFalse((self.root / "created.js").exists())
        self.assertEqual((self.root / "nested.js").read_text(), "export const n = 1;\n")
        move_diff = self.assert_diff_receipt(moved)
        self.assertIn(b"created.js", move_diff)
        self.assertIn(b"nested.js", move_diff)

        self.read("nested.js")
        deleted = self.fileop("delete", "nested.js")
        self.assertTrue(deleted["ok"], deleted)
        self.assertFalse((self.root / "nested.js").exists())
        self.assertIn(b"nested.js", self.assert_diff_receipt(deleted))

        empty = self.fileop("create", "empty.js", new_text="")
        self.assertTrue(empty["ok"], empty)
        self.assertEqual((self.root / "empty.js").read_bytes(), b"")
        self.assert_diff_receipt(empty)

    def test_file_operations_require_explicit_safe_paths_and_observations(self):
        self.assertEqual(
            self.fileop("delete", "a.js")["code"], "EDIT_SOURCE_NOT_OBSERVED"
        )
        self.assertEqual(
            self.fileop("move", "a.js", destination="moved.js")["code"],
            "EDIT_SOURCE_NOT_OBSERVED",
        )
        self.assertEqual(
            self.fileop("create", "../escape.js", new_text="x")["code"],
            "EDIT_PATH_INVALID",
        )
        self.assertEqual(
            self.fileop("create", "oracle.test.js", new_text="x")["code"],
            "EDIT_PROTECTED_INPUT",
        )
        self.read("oracle.test.js")
        self.assertEqual(
            self.fileop("delete", "oracle.test.js")["code"],
            "EDIT_PROTECTED_INPUT",
        )
        self.assertEqual(
            self.fileop("move", "oracle.test.js", destination="oracle-copy.test.js")[
                "code"
            ],
            "EDIT_PROTECTED_INPUT",
        )
        outside = self.base / "outside-create"
        outside.mkdir()
        (self.root / "linked").symlink_to(outside)
        self.assertEqual(
            self.fileop("create", "linked/escape.js", new_text="x")["code"],
            "EDIT_PROTECTED_INPUT",
        )
        self.assertFalse((outside / "escape.js").exists())

    def test_file_operation_duplicate_destinations_never_overwrite(self):
        before = (self.root / "b.js").read_bytes()
        duplicate = self.fileop("create", "b.js", new_text="replacement")
        self.assertEqual(duplicate["code"], "EDIT_DESTINATION_EXISTS")
        case_duplicate = self.fileop("create", "B.JS", new_text="replacement")
        self.assertEqual(case_duplicate["code"], "EDIT_PROTECTED_INPUT")
        self.read("a.js")
        duplicate = self.fileop("move", "a.js", destination="b.js")
        self.assertEqual(duplicate["code"], "EDIT_DESTINATION_EXISTS")
        self.assertEqual((self.root / "b.js").read_bytes(), before)
        self.assertEqual((self.root / "a.js").read_bytes(), self.initial)

    def test_case_alias_cannot_bypass_existing_file_scope(self):
        self.assertTrue(
            editor.protected_or_disallowed(
                self.contract, {"private.js": {"kind": "file"}}, "PRIVATE.JS"
            )
        )

    def test_file_operation_post_mutation_failure_is_unknown(self):
        original = evidence.check
        calls = 0

        def fail_after_mutation(settings, record):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("synthetic private state failure")
            return original(settings, record)

        with patch.object(
            editor.task_evidence, "check", side_effect=fail_after_mutation
        ):
            result = self.fileop("create", "uncertain.js", new_text="created\n")
        self.assertEqual(result["executionState"], "COMPLETION_UNKNOWN")
        self.assertTrue((self.root / "uncertain.js").exists())

    def test_multiline_and_exact_leading_trailing(self):
        self.read()
        new = "\n \t const x = 30;\n\treturn x; \n\n"
        r = self.edit(self.initial.decode(), new)
        self.assertTrue(r["ok"], r)
        self.assertEqual((self.root / "a.js").read_bytes(), new.encode())

    def test_empty_replacement(self):
        self.read()
        self.assertTrue(self.edit("  const x = 10;\n", "")["ok"])
        self.assertEqual((self.root / "a.js").read_bytes(), b"\treturn x;\n")

    def test_zero_match(self):
        self.read()
        self.rejected("EDIT_TARGET_NOT_FOUND", old="99")

    def test_whitespace_mismatch(self):
        self.read()
        self.rejected("EDIT_TARGET_NOT_FOUND", old="return  x;")

    def test_duplicate_and_overlapping(self):
        for raw, old in [(b"x x", "x"), (b"aaa", "aa")]:
            (self.root / "a.js").write_bytes(raw)
            self.read()
            self.rejected("EDIT_TARGET_NOT_UNIQUE", old=old)

    def test_stale(self):
        self.read()
        (self.root / "a.js").write_bytes(b"new bytes")
        self.rejected("EDIT_SOURCE_STALE")

    def test_unobserved_and_unconfirmed(self):
        self.rejected("EDIT_SOURCE_NOT_OBSERVED")
        self.read(confirm=False)
        self.rejected("EDIT_SOURCE_NOT_OBSERVED")

    def test_unseen_range(self):
        self.read(max_chars=4)
        self.rejected("EDIT_SOURCE_NOT_OBSERVED")

    def test_fresh_read_recovery_and_second_edit(self):
        self.read()
        self.rejected("EDIT_TARGET_NOT_FOUND", old="99")
        self.rejected("EDIT_SOURCE_NOT_OBSERVED")
        self.read()
        self.assertTrue(self.edit()["ok"])
        self.rejected("EDIT_SOURCE_NOT_OBSERVED", old="30")
        self.read()
        self.assertTrue(self.edit(old="30", new="40")["ok"])

    def test_two_files_observed_then_sequentially_edited(self):
        self.read()
        self.read("b.js")
        self.assertTrue(self.edit()["ok"])
        self.assertTrue(self.edit("1", "2", "b.js")["ok"])

    def test_race_during_authority(self):
        self.read()

        def race(settings, record, diff):
            result = editor.mutation_authority(settings, record, diff)
            (self.root / "a.js").write_bytes(b"concurrent owner write")
            return result

        r = self.edit(authorize=race)
        self.assertEqual(r["code"], "EDIT_APPLY_RACE")
        self.assertEqual((self.root / "a.js").read_bytes(), b"concurrent owner write")

    def test_parent_symlink_race(self):
        # A parent replacement cannot redirect the anchored atomic write.
        (self.root / "d").mkdir()
        (self.root / "d/a.js").write_bytes(self.initial)
        self.contract["mutable"].append("d/a.js")
        # New independent snapshot with the directory in scope.
        self.record["workspace_id"] = "b" * 32
        evidence.snapshot(self.settings, self.record, self.contract)
        self.read("d/a.js")
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "a.js").write_bytes(b"outside")

        def race(settings, record, diff):
            result = editor.mutation_authority(settings, record, diff)
            (self.root / "d").rename(self.root / "moved")
            (self.root / "d").symlink_to(outside)
            return result

        result = self.edit(path="d/a.js", authorize=race)
        self.assertFalse(result["ok"])
        self.assertEqual((outside / "a.js").read_bytes(), b"outside")
        self.assertEqual((self.root / "moved/a.js").read_bytes(), self.initial)

    def test_protected_and_scope(self):
        self.read("oracle.test.js")
        self.rejected("EDIT_PROTECTED_INPUT", path="oracle.test.js", old="original")
        self.rejected("EDIT_PATH_NOT_MUTABLE", path="else.js")

    def test_path_traversal(self):
        for path in [
            "../a.js",
            "/a.js",
            ".git/config",
            "a/../a.js",
            "a//b",
            "./a.js",
            "a\\b",
        ]:
            self.rejected("EDIT_PATH_INVALID", path=path)

    def test_symlink_hardlink_and_fifo(self):
        (self.root / "a.js").unlink()
        (self.root / "a.js").symlink_to(self.root / "b.js")
        self.rejected("EDIT_PATH_INVALID")
        (self.root / "a.js").unlink()
        os.link(self.root / "b.js", self.root / "a.js")
        self.rejected("EDIT_FILE_TYPE_UNSUPPORTED")
        (self.root / "a.js").unlink()
        os.mkfifo(self.root / "a.js")
        r = self.edit()
        self.assertEqual(r["code"], "EDIT_FILE_TYPE_UNSUPPORTED")

    def test_utf8_and_crlf(self):
        raw = '\tconst café = "雪";\r\nreturn café;\r\n'.encode()
        (self.root / "a.js").write_bytes(raw)
        self.read()
        r = self.edit('"雪"', '"é🌿"')
        self.assertTrue(r["ok"], r)
        self.assertEqual(
            (self.root / "a.js").read_bytes(),
            raw.replace('"雪"'.encode(), '"é🌿"'.encode()),
        )
        self.read()
        self.rejected("EDIT_TARGET_NOT_FOUND", old="return café;\n")

    def test_braces_quotes_escapes(self):
        self.read()
        new = '"\\t\\n{\\"a\\": 3}"'
        self.assertTrue(self.edit("10", new)["ok"])
        self.assertEqual(
            (self.root / "a.js").read_bytes(), self.initial.replace(b"10", new.encode())
        )

    def test_noop_and_oversize(self):
        self.read()
        self.rejected("EDIT_NO_CHANGE", new="10")
        self.rejected("EDIT_REPLACEMENT_TOO_LARGE", new="雪" * 3000)
        self.rejected("EDIT_REPLACEMENT_TOO_LARGE", old="x" * 4097)

    def test_schema_and_encoding(self):
        for args in [
            {},
            {"path": "a.js", "old_text": "", "new_text": "x"},
            {"path": "a.js", "old_text": "10", "new_text": "x", "edits": []},
            {"operation": "create", "path": "new.js"},
            {"operation": "delete", "path": "a.js", "new_text": "x"},
            {"operation": "move", "path": "a.js"},
            {"operation": "unknown", "path": "a.js"},
        ]:
            self.assertEqual(
                editor.apply(self.settings, self.record, args)["code"],
                "EDIT_SCHEMA_INVALID",
            )
        self.rejected("EDIT_ENCODING_UNSUPPORTED", new="\ud800")
        self.rejected("EDIT_ENCODING_UNSUPPORTED", new="\0")
        (self.root / "a.js").write_bytes(b"\xff")
        self.rejected("EDIT_ENCODING_UNSUPPORTED")

    def test_authority_denial(self):
        self.read()
        self.rejected(
            "EDIT_AUTHORITY_DENIED", authorize=lambda *args: {"outcome": "DENY"}
        )

    def test_failure_never_returns_source_or_internal_exception(self):
        self.read()
        r = self.edit(old="missing")
        self.assertEqual(set(r), {"ok", "code", "executionState"})

    def test_unobserved_cross_task(self):
        self.read()
        self.record["workspace_id"] = "b" * 32
        evidence.snapshot(self.settings, self.record, self.contract)
        self.rejected("EDIT_SOURCE_NOT_OBSERVED")

    def test_private_state_persistence_failure_after_write_is_uncertain(self):
        self.read()
        real = editor.atomic

        def unavailable(path, data):
            if path.name == "editor.json":
                raise OSError("synthetic failure")
            return real(path, data)

        with patch.object(editor, "atomic", unavailable):
            result = self.edit()
        self.assertEqual(result["executionState"], "COMPLETION_UNKNOWN")
        self.assertEqual(result["code"], "EDIT_STATE_UNAVAILABLE")
        self.assertEqual(
            (self.root / "a.js").read_bytes(), self.initial.replace(b"10", b"30")
        )

    def test_private_proposal_reconstructs_exact_candidate_and_diff(self):
        self.read()
        result = self.edit()
        self.assertTrue(result["ok"])
        directory = evidence.store_root(self.settings) / self.record["workspace_id"]
        args = json.loads((directory / "edit-1.proposal.json").read_text())
        before = (directory / "edit-1.before").read_bytes()
        self.assertEqual(
            before.replace(args["old_text"].encode(), args["new_text"].encode(), 1),
            (self.root / "a.js").read_bytes(),
        )
        self.assertEqual(
            editor.canonical_diff(
                args["path"], before, (self.root / "a.js").read_bytes()
            ),
            (directory / "edit-1.diff").read_bytes(),
        )

    def test_unrelated_mutation_during_commit_is_uncertain(self):
        self.read()
        replace = editor.os.replace

        def race(src, dst, **kwargs):
            if dst == "a.js":
                (self.root / "b.js").write_bytes(b"concurrent write")
            return replace(src, dst, **kwargs)

        with patch.object(editor.os, "replace", race):
            result = self.edit()
        self.assertEqual(result["code"], "EDIT_APPLY_RACE")
        self.assertEqual(result["executionState"], "COMPLETION_UNKNOWN")

    def test_all_supported_noneditor_routes_share_task_lock(self):
        import importlib.util

        module = importlib.util.spec_from_file_location(
            "editor_test_worker", Path(__file__).resolve().parents[1] / "worker.py"
        )
        worker = importlib.util.module_from_spec(module)
        module.loader.exec_module(worker)
        entered = []
        import contextlib

        @contextlib.contextmanager
        def lock(*args):
            entered.append(True)
            try:
                yield {}, None
            finally:
                entered.pop()

        for op in [
            "worktree_list",
            "worktree_patch",
            "worktree_command",
            "worktree_integrity",
            "worktree_acceptance",
            "worktree_cleanup",
        ]:
            with (
                patch.object(worker, "work_record", return_value=self.record),
                patch.object(editor, "locked", lock),
                patch.object(
                    worker,
                    "_execute",
                    side_effect=lambda *args: self.assertEqual(entered, [True]),
                ),
            ):
                worker.execute({"operation": op, "scope": "a" * 32}, self.settings)
