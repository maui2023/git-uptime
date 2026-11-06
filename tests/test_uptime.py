"""Tests for uptime percentage calculation, time windows, and summary metrics."""

from __future__ import annotations

import datetime
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.uptime import UptimeCalculator, calculate_uptime_percentage


class TestUptime(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir)
        self.history_dir = self.data_dir / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_calculate_uptime_percentage_formula(self):
        """Test calculation formula: Successful / Total * 100."""
        self.assertEqual(calculate_uptime_percentage(100, 100), 100.0)
        self.assertEqual(calculate_uptime_percentage(95, 100), 95.0)
        self.assertEqual(calculate_uptime_percentage(0, 50), 0.0)
        self.assertEqual(calculate_uptime_percentage(287, 288), 99.65)
        # Missing or zero checks must return None, not fake 100%
        self.assertIsNone(calculate_uptime_percentage(0, 0))

    def test_compute_summary_empty(self):
        """When no history exists, uptime is None and not fabricated."""
        calc = UptimeCalculator(data_dir=self.data_dir, history_days=30)
        monitors = [{"id": "srv1", "name": "Service 1"}]
        summary = calc.compute_summary(monitors=monitors, incidents=[])

        self.assertIsNone(summary["overall_uptime_30d"])
        srv_stat = summary["monitors"]["srv1"]
        self.assertIsNone(srv_stat["uptime_24h"])
        self.assertIsNone(srv_stat["uptime_7d"])
        self.assertIsNone(srv_stat["uptime_30d"])
        self.assertEqual(len(srv_stat["daily_history"]), 30)
        # Every daily bucket should be NODATA
        self.assertTrue(all(d["status"] == "NODATA" for d in srv_stat["daily_history"]))

    def test_compute_summary_with_records(self):
        """Test summary computation with known success and failure records."""
        now = datetime.datetime.now(datetime.timezone.utc)
        today_str = now.strftime("%Y-%m-%d")

        # 9 successes, 1 failure today
        records = []
        for i in range(9):
            records.append({
                "timestamp": now.isoformat(),
                "monitor_id": "srv1",
                "status": "UP",
                "http_status_code": 200,
                "response_time_ms": 100.0,
                "error_category": None,
                "check_result": "success",
            })
        records.append({
            "timestamp": now.isoformat(),
            "monitor_id": "srv1",
            "status": "DOWN",
            "http_status_code": 500,
            "response_time_ms": 500.0,
            "error_category": "http_5xx",
            "check_result": "failure",
        })

        with open(self.history_dir / f"{today_str}.json", "w", encoding="utf-8") as f:
            json.dump(records, f)

        calc = UptimeCalculator(data_dir=self.data_dir, history_days=30)
        monitors = [{"id": "srv1", "name": "Service 1"}]
        summary = calc.compute_summary(monitors=monitors, incidents=[])

        srv_stat = summary["monitors"]["srv1"]
        self.assertEqual(srv_stat["uptime_24h"], 90.0)
        self.assertEqual(srv_stat["uptime_7d"], 90.0)
        self.assertEqual(srv_stat["uptime_30d"], 90.0)
        self.assertEqual(srv_stat["total_checks_30d"], 10)
        self.assertEqual(srv_stat["successful_checks_30d"], 9)
        self.assertEqual(srv_stat["avg_response_time_24h"], 140.0)

        # Overall uptime
        self.assertEqual(summary["overall_uptime_30d"], 90.0)

        # Today's daily bucket in daily_history should have 90.0% and status DOWN because of down check
        today_bucket = next(b for b in srv_stat["daily_history"] if b["date"] == today_str)
        self.assertEqual(today_bucket["total_checks"], 10)
        self.assertEqual(today_bucket["uptime_percentage"], 90.0)
        self.assertEqual(today_bucket["status"], "DOWN")


if __name__ == "__main__":
    unittest.main()
