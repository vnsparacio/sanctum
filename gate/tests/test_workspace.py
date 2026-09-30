import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE / "src")]
from common import Refused
from workspace import (
    apply_patch,
    cleanup_worktree,
    contained,
    create_worktree,
    inspect_worktree,
    list_entries,
    read_text,
)


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.stage = self.root / "stage"
        self.repo.mkdir()
        self.stage.mkdir()
        subprocess.run(["/usr/bin/git", "init", "-q"], cwd=self.repo, check=True)
        (self.repo / "a.txt").write_text("synthetic\n")
        subprocess.run(["/usr/bin/git", "add", "a.txt"], cwd=self.repo, check=True)
        subprocess.run(
            [
                "/usr/bin/git",
                "-c",
                "user.name=test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "synthetic",
            ],
            cwd=self.repo,
            check=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_owner_creates_clean_detached_worktree(self):
        result = create_worktree(str(self.repo), str(self.stage), "task-1")
        self.assertEqual(result["workspace_id"], "task-1")
        self.assertEqual(result["initial_status"], "")
        self.assertTrue((Path(result["root"]) / "a.txt").is_file())

    def test_refuses_dirty_source_and_escape_names(self):
        (self.repo / "dirty").write_text("x")
        with self.assertRaises(Refused):
            create_worktree(str(self.repo), str(self.stage), "task-2")
        (self.repo / "dirty").unlink()
        for name in ("../outside", "x/y", ""):
            with self.assertRaises(Refused):
                create_worktree(str(self.repo), str(self.stage), name)

    def test_containment_has_no_parent_escape(self):
        self.assertTrue(contained(self.stage, self.stage / "new"))
        self.assertFalse(contained(self.stage, self.root / "other"))

    def test_no_follow_traversal_absolute_symlink_and_hardlink(self):
        result = create_worktree(str(self.repo), str(self.stage), "task-links")
        root = Path(result["root"])
        outside = self.root / "secret"
        outside.write_text("marker")
        (root / "link").symlink_to(outside)
        os.link(outside, root / "hard")
        for name in (
            "../secret",
            str(outside),
            "link",
            "hard",
            ".git",
            ".GIT",
            ".git/config",
        ):
            with self.assertRaises(Refused):
                read_text(root, name)
        self.assertEqual(
            list_entries(root)["entries"],
            [{"path": "a.txt", "kind": "file", "size": 10}],
        )

    def test_patch_and_fixed_git_inspection(self):
        result = create_worktree(str(self.repo), str(self.stage), "task-patch")
        root = Path(result["root"])
        patch = "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-synthetic\n+changed\n"
        applied = apply_patch(root, patch)
        self.assertTrue(applied["ok"])
        self.assertEqual(applied["changed"], ["a.txt"])
        self.assertTrue(inspect_worktree(root, "status")["output_bytes"])
        self.assertTrue(inspect_worktree(root, "diff")["output_bytes"])
        # Stale line counts are safely recounted, while stale context is a bounded
        # proposal rejection rather than a false worktree outage.
        recount = "--- a/a.txt\n+++ b/a.txt\n@@ -1,7 +1,7 @@\n-changed\n+recounted\n"
        self.assertTrue(apply_patch(root, recount)["ok"])
        rejected = apply_patch(root, patch)
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["code"], "WORKSPACE_PATCH_REJECTED")
        self.assertIn("patch", rejected["diagnostic"].lower())
        self.assertTrue(cleanup_worktree(str(self.repo), result)["cleaned"])

    def test_fixed_diff_describes_complete_current_worktree(self):
        (self.repo / "b.txt").write_text("remove me\n")
        subprocess.run(["/usr/bin/git", "add", "b.txt"], cwd=self.repo, check=True)
        subprocess.run(
            [
                "/usr/bin/git",
                "-c",
                "user.name=test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "second fixture",
            ],
            cwd=self.repo,
            check=True,
        )
        result = create_worktree(str(self.repo), str(self.stage), "task-complete")
        root = Path(result["root"])

        (root / "a.txt").write_text("first edit\n")
        (root / "created.txt").write_text("first created value\n")
        (root / "empty.txt").write_text("")
        (root / "b.txt").unlink()

        first = inspect_worktree(root, "diff")
        self.assertIn("first edit", first["output"])
        self.assertIn("created.txt", first["output"])
        self.assertIn("empty.txt", first["output"])
        self.assertIn("deleted file mode", first["output"])

        # A later edit must replace prior evidence with the current worktree.
        (root / "created.txt").write_text("latest created value\n")
        (root / "a.txt").write_text("synthetic\n")
        second = inspect_worktree(root, "diff")
        self.assertIn("latest created value", second["output"])
        self.assertNotIn("first created value", second["output"])
        self.assertNotIn("first edit", second["output"])
        self.assertNotIn("a/a.txt", second["output"])
        self.assertNotEqual(first["output_digest"], second["output_digest"])

        # Removing the created file must also remove its stale edit evidence.
        (root / "created.txt").unlink()
        third = inspect_worktree(root, "diff")
        self.assertNotIn("created.txt", third["output"])
        self.assertNotIn("latest created value", third["output"])
        self.assertIn("empty.txt", third["output"])
        self.assertIn("b/b.txt", third["output"])
        self.assertTrue(cleanup_worktree(str(self.repo), result)["cleaned"])
