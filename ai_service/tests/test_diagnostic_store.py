import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

class DiagnosticStoreTests(unittest.TestCase):
    def test_expiry_boundary_and_unrelated_files(self):
        from agentfit_ai.diagnostics import LocalDiagnosticsStore
        now = datetime(2026, 9, 25, tzinfo=timezone.utc)
        clock = [now]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            other = root / "keep.json"
            other.write_text("{}")
            store = LocalDiagnosticsStore(root, clock=lambda: clock[0])
            store.write({"run_id": "a"*32}, [])
            owned = root / ("analysis-" + "a"*32 + ".json")
            self.assertTrue(owned.exists())
            clock[0] = now + timedelta(days=7) - timedelta(microseconds=1)
            self.assertEqual(store.purge(), 0)
            clock[0] += timedelta(microseconds=1)
            self.assertEqual(store.purge(), 1)
            self.assertFalse(owned.exists())
            self.assertTrue(other.exists())

    def test_duplicate_run_cannot_overwrite(self):
        from agentfit_ai.diagnostics import LocalDiagnosticsStore
        with tempfile.TemporaryDirectory() as folder:
            store = LocalDiagnosticsStore(Path(folder))
            store.write({"run_id": "b"*32}, [])
            with self.assertRaises(FileExistsError):
                store.write({"run_id": "b"*32}, [])

    def test_run_id_cannot_escape_directory(self):
        from agentfit_ai.diagnostics import LocalDiagnosticsStore
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                LocalDiagnosticsStore(Path(folder)).write({"run_id": "../outside"}, [])

    def test_read_purges_expired_run(self):
        from agentfit_ai.diagnostics import LocalDiagnosticsStore
        now = datetime(2026, 9, 25, tzinfo=timezone.utc)
        clock = [now]
        with tempfile.TemporaryDirectory() as folder:
            store = LocalDiagnosticsStore(Path(folder), clock=lambda: clock[0])
            store.write({"run_id": "c"*32}, [])
            self.assertEqual(store.read("c"*32)["failed_responses"], [])
            clock[0] += timedelta(days=7)
            with self.assertRaises(FileNotFoundError):
                store.read("c"*32)

    def test_corrupt_owned_file_expires_by_mtime(self):
        import os
        from agentfit_ai.diagnostics import LocalDiagnosticsStore
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ("analysis-" + "d"*32 + ".json")
            path.write_text("{broken")
            old = (now - timedelta(days=8)).timestamp()
            os.utime(path, (old, old))
            self.assertEqual(LocalDiagnosticsStore(Path(folder), clock=lambda: now).purge(), 1)
