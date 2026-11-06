"""Tests for incident lifecycle, threshold evaluation, duplicate prevention, and resolution."""

from __future__ import annotations

import datetime
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check import check_single_monitor
from scripts.incidents import IncidentManager


class TestIncidents(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.incidents_file = Path(self.temp_dir) / "incidents.json"
        self.manager = IncidentManager(incidents_file=self.incidents_file)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_create_and_resolve_incident(self):
        """Test incident creation, deduplication, and resolution."""
        # 1. Create incident
        t_start = "2026-11-06T10:00:00+00:00"
        inc = self.manager.create_incident(
            monitor_id="srv1",
            monitor_name="Service 1",
            error_description="Connection timed out",
            timestamp=t_start,
        )
        self.assertIsNotNone(inc)
        self.assertEqual(inc["status"], "investigating")
        self.assertEqual(len(self.manager.get_active_incidents()), 1)

        # 2. Prevent duplicate incident while one is ongoing
        inc2 = self.manager.create_incident(
            monitor_id="srv1",
            monitor_name="Service 1",
            error_description="Still failing",
            timestamp="2026-11-06T10:05:00+00:00",
        )
        self.assertEqual(inc["id"], inc2["id"])
        self.assertEqual(len(self.manager.get_active_incidents()), 1)

        # 3. Update status
        self.manager.update_incident_status(
            incident_id=inc["id"],
            new_status="identified",
            message="Identified upstream network issue.",
            timestamp="2026-11-06T10:07:00+00:00",
        )
        self.assertEqual(inc["status"], "identified")
        self.assertEqual(len(inc["updates"]), 2)

        # 4. Resolve incident
        t_resolve = "2026-11-06T10:20:00+00:00"
        resolved = self.manager.resolve_incident(
            monitor_id="srv1",
            resolution_message="Service recovered.",
            timestamp=t_resolve,
        )
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["status"], "resolved")
        self.assertEqual(resolved["duration_seconds"], 1200)  # 20 minutes = 1200 seconds
        self.assertEqual(len(self.manager.get_active_incidents()), 0)

        # 5. Save and reload
        self.manager.save()
        new_mgr = IncidentManager(incidents_file=self.incidents_file)
        self.assertEqual(len(new_mgr.incidents), 1)
        self.assertEqual(new_mgr.incidents[0]["status"], "resolved")

    def test_failure_threshold_logic(self):
        """Test failure threshold behavior in monitor check."""
        from unittest.mock import patch

        monitor = {"id": "srv1", "name": "Service 1", "url": "https://example.com"}
        settings = {"failure_threshold": 2, "retry_delay_seconds": 0}

        # First failure: pending_down, consecutive_failures = 1
        with patch("scripts.check.execute_http_probe", return_value={"status": "DOWN", "http_status_code": 500, "response_time_ms": 100, "error_category": "http_5xx", "error_message": "Error"}):
            res1 = check_single_monitor(monitor, settings, prev_state={"consecutive_failures": 0})
            self.assertEqual(res1["status"], "DOWN")
            self.assertEqual(res1["state"], "pending_down")
            self.assertEqual(res1["consecutive_failures"], 1)

            # Second consecutive failure: confirmed down
            res2 = check_single_monitor(monitor, settings, prev_state={"consecutive_failures": 1})
            self.assertEqual(res2["status"], "DOWN")
            self.assertEqual(res2["state"], "down")
            self.assertEqual(res2["consecutive_failures"], 2)

        # Recovery on subsequent check
        with patch("scripts.check.execute_http_probe", return_value={"status": "UP", "http_status_code": 200, "response_time_ms": 50, "error_category": None, "error_message": None}):
            res3 = check_single_monitor(monitor, settings, prev_state={"consecutive_failures": 2})
            self.assertEqual(res3["status"], "UP")
            self.assertEqual(res3["state"], "operational")
            self.assertEqual(res3["consecutive_failures"], 0)


if __name__ == "__main__":
    unittest.main()
