"""Unit tests for Telegram notification module and incident alert integration."""

from __future__ import annotations

import http.server
import json
import socketserver
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.incidents import IncidentManager
from scripts.notifier import TelegramNotifier, format_duration


class MockTelegramHandler(http.server.BaseHTTPRequestHandler):
    received_requests = []

    def log_message(self, format, *args):
        pass  # Suppress console logging during tests

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {}

        MockTelegramHandler.received_requests.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": parsed,
        })

        if "fail" in self.path:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"ok":false,"description":"Internal server error"}')
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true,"result":{"message_id":123}}')


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class TestNotifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadedHTTPServer(("127.0.0.1", 0), MockTelegramHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        MockTelegramHandler.received_requests.clear()

    def test_format_duration(self):
        """Test duration formatting helper."""
        self.assertEqual(format_duration(None), "< 1 minute")
        self.assertEqual(format_duration(0), "< 1 minute")
        self.assertEqual(format_duration(45), "45s")
        self.assertEqual(format_duration(90), "1m 30s")
        self.assertEqual(format_duration(3600), "1h")
        self.assertEqual(format_duration(3665), "1h 1m")
        self.assertEqual(format_duration(86400 * 2 + 3600 * 3), "2d 3h")

    def test_unconfigured_notifier(self):
        """When token or chat ID is missing, notifier is disabled and fails silently."""
        notifier = TelegramNotifier(bot_token="", chat_id="")
        self.assertFalse(notifier.is_configured())
        self.assertFalse(notifier.send_message("Test message"))
        self.assertFalse(notifier.notify_outage({}, {}))
        self.assertFalse(notifier.notify_recovery({}, {}))
        self.assertEqual(len(MockTelegramHandler.received_requests), 0)

    def test_send_message_success(self):
        """Send message successfully sends formatted POST request."""
        mock_url = f"http://127.0.0.1:{self.port}"
        notifier = TelegramNotifier(
            bot_token="test_token_123",
            chat_id="test_chat_456",
            api_base_url=mock_url,
        )
        self.assertTrue(notifier.is_configured())

        ok = notifier.send_message("<b>Hello World</b>")
        self.assertTrue(ok)
        self.assertEqual(len(MockTelegramHandler.received_requests), 1)

        req = MockTelegramHandler.received_requests[0]
        self.assertEqual(req["path"], "/bottest_token_123/sendMessage")
        self.assertEqual(req["body"]["chat_id"], "test_chat_456")
        self.assertEqual(req["body"]["text"], "<b>Hello World</b>")
        self.assertEqual(req["body"]["parse_mode"], "HTML")
        self.assertTrue(req["body"]["disable_web_page_preview"])

    def test_notify_outage(self):
        """notify_outage generates clean HTML outage alert."""
        mock_url = f"http://127.0.0.1:{self.port}"
        notifier = TelegramNotifier(
            bot_token="test_token_123",
            chat_id="test_chat_456",
            api_base_url=mock_url,
        )

        monitor_res = {
            "name": "Sabily Enterprise",
            "url": "https://sabily.info",
            "http_status_code": 502,
            "error_category": "http_5xx",
            "error_message": "Bad Gateway",
        }
        incident = {
            "started_at": "2026-11-07T00:00:00Z",
            "error_description": "HTTP 502 Bad Gateway",
        }

        ok = notifier.notify_outage(monitor_res, incident)
        self.assertTrue(ok)
        self.assertEqual(len(MockTelegramHandler.received_requests), 1)

        text = MockTelegramHandler.received_requests[0]["body"]["text"]
        self.assertIn("ALERT: Service Outage Detected", text)
        self.assertIn("Sabily Enterprise", text)
        self.assertIn("https://sabily.info", text)
        self.assertIn("HTTP 502", text)
        self.assertIn("Bad Gateway", text)

    def test_notify_recovery(self):
        """notify_recovery generates clean HTML recovery alert with downtime duration."""
        mock_url = f"http://127.0.0.1:{self.port}"
        notifier = TelegramNotifier(
            bot_token="test_token_123",
            chat_id="test_chat_456",
            api_base_url=mock_url,
        )

        monitor_res = {
            "name": "Commit KPST",
            "url": "https://commit.kpst.my",
            "http_status_code": 200,
            "response_time_ms": 150.5,
        }
        incident = {
            "started_at": "2026-11-07T00:00:00Z",
            "resolved_at": "2026-11-07T00:15:30Z",
            "duration_seconds": 930,  # 15m 30s
        }

        ok = notifier.notify_recovery(monitor_res, incident)
        self.assertTrue(ok)
        self.assertEqual(len(MockTelegramHandler.received_requests), 1)

        text = MockTelegramHandler.received_requests[0]["body"]["text"]
        self.assertIn("RESOLVED: Service Restored", text)
        self.assertIn("Commit KPST", text)
        self.assertIn("15m 30s", text)
        self.assertIn("150ms", text)

    def test_network_failure_resilience(self):
        """Notifier handles network or HTTP failures without throwing exceptions."""
        mock_url = f"http://127.0.0.1:{self.port}"
        # Endpoint with 'fail' triggers 500 error on mock server
        notifier = TelegramNotifier(
            bot_token="fail_token",
            chat_id="test_chat_456",
            api_base_url=mock_url,
        )

        ok = notifier.send_message("Test failure")
        self.assertFalse(ok)

    def test_incident_is_new_flag(self):
        """IncidentManager sets is_new: True on creation and False on duplicates."""
        test_file = Path("public/data/test_incidents_tmp.json")
        try:
            mgr = IncidentManager(test_file)
            inc1 = mgr.create_incident("mon-1", "Service 1", "Timeout error")
            self.assertTrue(inc1.get("is_new"))

            inc2 = mgr.create_incident("mon-1", "Service 1", "Still timeout")
            self.assertFalse(inc2.get("is_new"))
            self.assertEqual(inc1["id"], inc2["id"])
        finally:
            if test_file.exists():
                test_file.unlink()


if __name__ == "__main__":
    unittest.main()
