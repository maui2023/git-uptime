"""Tests for monitoring probe, HTTP checks, SSRF filtering, retries, and concurrency."""

from __future__ import annotations

import http.server
import socket
import socketserver
import ssl
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check import check_single_monitor, execute_http_probe
from scripts.utils import is_ip_private_or_reserved, resolve_and_validate_hostname, validate_url


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class MockHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logging in test output

    def do_GET(self):
        if self.path == "/200":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK Sabily")
        elif self.path == "/301":
            self.send_response(301)
            self.send_header("Location", "/200")
            self.end_headers()
        elif self.path == "/redirect-ssrf":
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data")
            self.end_headers()
        elif self.path == "/404":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
        elif self.path == "/500":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Internal Error")
        elif self.path == "/keyword":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"System Operational Ready")
        elif self.path == "/timeout":
            time.sleep(1.5)
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Default response")

    def do_HEAD(self):
        if self.path == "/head-unsupported":
            # 405 Method Not Allowed triggers GET fallback
            self.send_response(405)
            self.end_headers()
        elif self.path == "/200":
            self.send_response(200)
            self.end_headers()
        else:
            self.do_GET()


class TestMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start a local multi-threaded HTTP server for testing
        cls.server = ThreadedHTTPServer(("127.0.0.1", 0), MockHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_ssrf_private_ip_rejection(self):
        """Ensure private IP ranges and loopbacks are rejected."""
        self.assertTrue(is_ip_private_or_reserved("127.0.0.1"))
        self.assertTrue(is_ip_private_or_reserved("10.0.1.5"))
        self.assertTrue(is_ip_private_or_reserved("172.16.0.1"))
        self.assertTrue(is_ip_private_or_reserved("192.168.1.1"))
        self.assertTrue(is_ip_private_or_reserved("169.254.169.254"))
        self.assertTrue(is_ip_private_or_reserved("::1"))
        self.assertFalse(is_ip_private_or_reserved("8.8.8.8"))
        self.assertFalse(is_ip_private_or_reserved("1.1.1.1"))

    def test_validate_url_rejects_private_ips(self):
        """validate_url must block private/loopback/unsupported URLs."""
        valid, msg = validate_url("ftp://example.com")
        self.assertFalse(valid)

        valid, msg = validate_url("http://localhost:8080")
        self.assertFalse(valid)

        valid, msg = validate_url("http://127.0.0.1:8080")
        self.assertFalse(valid)

        valid, msg = validate_url("http://169.254.169.254/latest/meta-data")
        self.assertFalse(valid)

    def test_http_200_success(self):
        """Website returning HTTP 200 is classified as UP."""
        with patch("scripts.check.validate_url", return_value=(True, None)):
            res = execute_http_probe(
                url=f"http://127.0.0.1:{self.port}/200",
                expected_status_codes=[200],
            )
            self.assertEqual(res["status"], "UP")
            self.assertEqual(res["http_status_code"], 200)
            self.assertIsNotNone(res["response_time_ms"])
            self.assertIsNone(res["error_category"])

    def test_http_301_redirect(self):
        """Website returning 301 followed or classified based on expected_status_codes."""
        with patch("scripts.check.validate_url", return_value=(True, None)):
            res = execute_http_probe(
                url=f"http://127.0.0.1:{self.port}/301",
                expected_status_codes=[200, 301],
            )
            self.assertEqual(res["status"], "UP")

    def test_http_404_degraded(self):
        """Website returning unexpected 404 is classified as DEGRADED."""
        with patch("scripts.check.validate_url", return_value=(True, None)):
            res = execute_http_probe(
                url=f"http://127.0.0.1:{self.port}/404",
                expected_status_codes=[200],
            )
            self.assertEqual(res["status"], "DEGRADED")
            self.assertEqual(res["http_status_code"], 404)
            self.assertEqual(res["error_category"], "http_4xx")

    def test_http_500_down(self):
        """Website returning 500 is classified as DOWN."""
        with patch("scripts.check.validate_url", return_value=(True, None)):
            res = execute_http_probe(
                url=f"http://127.0.0.1:{self.port}/500",
                expected_status_codes=[200],
            )
            self.assertEqual(res["status"], "DOWN")
            self.assertEqual(res["http_status_code"], 500)
            self.assertEqual(res["error_category"], "http_5xx")

    def test_connection_timeout(self):
        """Connection timeout is classified as DOWN with timeout error category."""
        with patch("scripts.check.validate_url", return_value=(True, None)):
            res = execute_http_probe(
                url=f"http://127.0.0.1:{self.port}/timeout",
                timeout=1,
            )
            self.assertEqual(res["status"], "DOWN")
            self.assertEqual(res["error_category"], "timeout")

    def test_dns_resolution_failure(self):
        """DNS resolution failure returns DOWN with dns_error."""
        res = execute_http_probe(url="https://non-existent-domain-xyz-404-check.test")
        self.assertEqual(res["status"], "DOWN")
        self.assertIn(res["error_category"], ("dns_error", "connection_error"))

    def test_ssl_verification_failure(self):
        """SSL verification failure returns DOWN with ssl_error category."""
        # Simulate SSL error by mocking urllib opener
        with patch("urllib.request.OpenerDirector.open", side_effect=ssl.SSLCertVerificationError("Certificate verify failed")):
            with patch("scripts.check.validate_url", return_value=(True, None)):
                res = execute_http_probe(url="https://expired.badssl.com")
                self.assertEqual(res["status"], "DOWN")
                self.assertEqual(res["error_category"], "ssl_error")

    def test_head_unsupported_get_fallback(self):
        """HEAD request returning 405 falls back to GET seamlessly."""
        with patch("scripts.check.validate_url", return_value=(True, None)):
            res = execute_http_probe(
                url=f"http://127.0.0.1:{self.port}/head-unsupported",
                method="HEAD",
                expected_status_codes=[200],
            )
            self.assertEqual(res["status"], "UP")
            self.assertEqual(res["http_status_code"], 200)

    def test_keyword_matching(self):
        """Keyword matching marks UP on match, DEGRADED on mismatch."""
        with patch("scripts.check.validate_url", return_value=(True, None)):
            # Match
            res_ok = execute_http_probe(
                url=f"http://127.0.0.1:{self.port}/keyword",
                keyword="Operational",
            )
            self.assertEqual(res_ok["status"], "UP")

            # Mismatch
            res_bad = execute_http_probe(
                url=f"http://127.0.0.1:{self.port}/keyword",
                keyword="NonExistentString12345",
            )
            self.assertEqual(res_bad["status"], "DEGRADED")
            self.assertEqual(res_bad["error_category"], "keyword_mismatch")

    def test_redirect_to_private_ip_rejection(self):
        """Redirecting to private IP must trigger SSRF block and be classified as DOWN."""
        with patch("scripts.check.validate_url", side_effect=lambda u: (False, "SSRF protection blocked") if "169.254" in u else (True, None)):
            res = execute_http_probe(url=f"http://127.0.0.1:{self.port}/redirect-ssrf")
            self.assertEqual(res["status"], "DOWN")
            self.assertEqual(res["error_category"], "ssrf_blocked")

    def test_retry_behavior_on_failure(self):
        """Probe retries once if first attempt is not UP."""
        attempt_count = 0

        def mock_probe(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                return {"status": "DOWN", "http_status_code": 500, "response_time_ms": 50, "error_category": "http_5xx", "error_message": "Fail 1"}
            return {"status": "UP", "http_status_code": 200, "response_time_ms": 40, "error_category": None, "error_message": None}

        monitor = {"id": "test-mon", "name": "Test Mon", "url": "https://example.com"}
        settings = {"timeout_seconds": 5, "retry_delay_seconds": 0, "failure_threshold": 2}

        with patch("scripts.check.execute_http_probe", side_effect=mock_probe):
            res = check_single_monitor(monitor, settings)
            self.assertEqual(attempt_count, 2)
            self.assertEqual(res["status"], "UP")
            self.assertEqual(res["state"], "operational")

    def test_concurrent_monitoring_30_websites(self):
        """Test monitoring 30 websites concurrently finishes quickly without thread errors."""
        import concurrent.futures

        monitors = [
            {"id": f"mon-{i}", "name": f"Service {i}", "url": f"http://127.0.0.1:{self.port}/200"}
            for i in range(30)
        ]
        settings = {"timeout_seconds": 5, "retry_delay_seconds": 0, "failure_threshold": 2}

        with patch("scripts.check.validate_url", return_value=(True, None)):
            t0 = time.time()
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                futures = [executor.submit(check_single_monitor, m, settings) for m in monitors]
                for f in concurrent.futures.as_completed(futures):
                    results.append(f.result())
            elapsed = time.time() - t0

            self.assertEqual(len(results), 30)
            self.assertTrue(all(r["status"] == "UP" for r in results))
            # 30 concurrent checks against local mock server should complete quickly
            self.assertLess(elapsed, 10.0)


if __name__ == "__main__":
    unittest.main()
