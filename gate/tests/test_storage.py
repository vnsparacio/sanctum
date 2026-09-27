"""Synthetic disk pressure: admission closes, ordinary cleanup remains authorized."""

import errno
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE / "src"), str(BASE / "tests")]
from common import (
    Refused,
    database,
    prepare_cleanup_reserve,
    release_cleanup_reserve,
    storage_error,
    storage_headroom,
)
from lifecycle import PrivateLeadLifecycle
from test_runtime import FakeBackend, FakeProvider, settings


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)

    def test_classifies_only_storage_failures(self):
        self.assertEqual(
            storage_error(OSError(errno.ENOSPC, "private")), "local_disk_full"
        )
        self.assertEqual(
            storage_error(OSError(errno.EDQUOT, "private")), "local_disk_full"
        )
        self.assertIsNone(storage_error(OSError(errno.EACCES, "private")))
        error = sqlite3.OperationalError("private")
        error.sqlite_errorcode = sqlite3.SQLITE_FULL
        self.assertEqual(storage_error(error), "local_disk_full")

    def test_admission_checks_nearest_existing_filesystem(self):
        with patch(
            "common.shutil.disk_usage", return_value=SimpleNamespace(free=1)
        ) as usage:
            with self.assertRaisesRegex(Refused, "local_disk_low"):
                storage_headroom(self.root / "not-created")
            usage.assert_called_once_with(self.root)

    def test_reserve_is_single_flight_and_released_only_under_pressure(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(prepare_cleanup_reserve, [self.root] * 4))
        reserve = self.root / "cleanup-storage.reserve"
        self.assertEqual(reserve.stat().st_size, 4 * 1024**2)
        with patch(
            "common.shutil.disk_usage", return_value=SimpleNamespace(free=10**10)
        ):
            release_cleanup_reserve(self.root)
        self.assertTrue(reserve.exists())
        with patch("common.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
            release_cleanup_reserve(self.root)
            release_cleanup_reserve(self.root)
        self.assertFalse(reserve.exists())

    def test_does_not_remove_unowned_or_substituted_content(self):
        reserve = self.root / "cleanup-storage.reserve"
        reserve.write_text("not a reserve")
        reserve.chmod(0o600)
        with patch("common.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(Refused, "cleanup_reserve_invalid"):
                release_cleanup_reserve(self.root)
        self.assertEqual(reserve.read_text(), "not a reserve")

    def test_low_disk_refuses_allocation_but_frees_reserve_before_lease_cleanup(self):
        provider = FakeProvider()
        lc = PrivateLeadLifecycle(
            settings(self.root), provider, FakeBackend(), now=lambda: 1000
        )
        prepare_cleanup_reserve(lc.root)
        with database(lc.root) as conn:
            conn.execute("insert into leases values(?, ?, 1, 0)", ("a" * 32, 2000))
        with patch("common.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(Refused, "local_disk_low"):
                lc.acquire("b" * 32)
            with self.assertRaisesRegex(Refused, "local_disk_low"):
                lc.ensure_ready("a" * 32)
            self.assertEqual(provider.created, 0)
            original = database

            def guarded(root):
                self.assertFalse((lc.root / "cleanup-storage.reserve").exists())
                return original(root)

            with patch("lifecycle.database", side_effect=guarded):
                lc.release("a" * 32)
        with database(lc.root) as conn:
            self.assertEqual(conn.execute("select active from leases").fetchone()[0], 0)

    def test_low_disk_cleanup_reconciles_owned_provider_and_preserves_active_lease(
        self,
    ):
        provider = FakeProvider()
        config = settings(self.root)
        config["private_lead"]["enabled"] = True
        lc = PrivateLeadLifecycle(
            config, provider, FakeBackend(), now=lambda: 1000, sleep=lambda _: None
        )
        lc.acquire("a" * 32)
        lc.ensure_ready("a" * 32, explicit=True)
        self.assertEqual(provider.created, 1)
        with patch("common.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
            lc.sweep(immediate=True)
            self.assertEqual(provider.deleted, [])
            lc.release("a" * 32)
            lc.release("a" * 32, close=True)
        self.assertEqual(provider.deleted, ["pod1"])
        self.assertEqual(lc.state()["phase"], "OFFLINE")
        with database(lc.root) as conn:
            self.assertEqual(
                conn.execute("select count(*) from leases").fetchone()[0], 0
            )
