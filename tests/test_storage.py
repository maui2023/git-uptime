"""Tests for storage operations, history rotation, pruning, stale data detection, and JSON schema validation."""

from __future__ import annotations

import datetime
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.storage import StorageManager
from scripts.utils import parse_iso_datetime
from scripts.validate import validate_config, validate_data_files


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "data"
        self.storage = StorageManager(data_dir=self.data_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_save_and_load_latest(self):
        """Test persisting and reading latest.json."""
        payload = {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "operational",
            "summary": {"total": 1, "up": 1, "down": 0, "degraded": 0, "paused": 0},
            "monitors": [{"id": "s1", "name": "Service 1", "status": "UP"}],
        }
        self.storage.save_latest(payload)
        loaded = self.storage.load_latest()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["status"], "operational")
        self.assertEqual(len(loaded["monitors"]), 1)

    def test_append_daily_history_compact(self):
        """Test compact daily history file generation."""
        date_str = "2026-11-06"
        records_1 = [{"timestamp": "2026-11-06T10:00:00Z", "id": "s1", "status": "UP"}]
        records_2 = [{"timestamp": "2026-11-06T10:05:00Z", "id": "s1", "status": "UP"}]

        self.storage.append_daily_history(records_1, date_str)
        self.storage.append_daily_history(records_2, date_str)

        history_file = self.storage.history_dir / f"{date_str}.json"
        self.assertTrue(history_file.is_file())

        with open(history_file, "r", encoding="utf-8") as f:
            content = f.read()
            # Compact JSON should not contain unnecessary newlines
            self.assertNotIn("\n", content)
            parsed = json.loads(content)
            self.assertEqual(len(parsed), 2)

    def test_prune_old_history(self):
        """History files older than keep_days must be deleted."""
        now = datetime.datetime.now(datetime.timezone.utc).date()

        # Create a file 5 days old (should keep)
        recent_date = (now - datetime.timedelta(days=5)).strftime("%Y-%m-%d")
        with open(self.storage.history_dir / f"{recent_date}.json", "w") as f:
            f.write("[]")

        # Create a file 35 days old (should prune)
        old_date = (now - datetime.timedelta(days=35)).strftime("%Y-%m-%d")
        with open(self.storage.history_dir / f"{old_date}.json", "w") as f:
            f.write("[]")

        deleted = self.storage.prune_old_history(keep_days=30)
        self.assertEqual(deleted, 1)
        self.assertTrue((self.storage.history_dir / f"{recent_date}.json").is_file())
        self.assertFalse((self.storage.history_dir / f"{old_date}.json").is_file())

    def test_stale_data_detection(self):
        """Data older than 15 minutes is classified as stale."""
        now = datetime.datetime.now(datetime.timezone.utc)
        fresh_ts = (now - datetime.timedelta(minutes=4)).isoformat()
        stale_ts = (now - datetime.timedelta(minutes=20)).isoformat()

        def is_data_stale(iso_timestamp: str, max_age_minutes: int = 15) -> bool:
            dt = parse_iso_datetime(iso_timestamp)
            if not dt:
                return True
            age = (now - dt).total_seconds()
            return age > (max_age_minutes * 60)

        self.assertFalse(is_data_stale(fresh_ts))
        self.assertTrue(is_data_stale(stale_ts))

    def test_validate_data_files(self):
        """Test validate_data_files helper on empty and populated folders."""
        ok, errors = validate_data_files(self.data_dir)
        # Should fail initially because files don't exist yet
        self.assertFalse(ok)

        # Populate valid files
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.storage.save_latest({
            "generated_at": now_iso,
            "status": "operational",
            "summary": {"total": 0, "up": 0, "down": 0, "degraded": 0, "paused": 0},
            "monitors": [],
        })
        with open(self.data_dir / "incidents.json", "w") as f:
            json.dump({"last_updated": now_iso, "incidents": []}, f)
        self.storage.save_uptime_summary({
            "generated_at": now_iso,
            "overall_uptime_30d": 100.0,
            "monitors": {},
        })

        ok, errors = validate_data_files(self.data_dir)
        self.assertTrue(ok)
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
