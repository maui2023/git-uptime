"""Telegram notification module for Sabily Uptime Monitor.

Sends alert messages to a Telegram chat or channel when service outages or
recoveries occur. Credentials are read securely from environment variables
(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID) provided by GitHub Actions Secrets.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds into a human-readable string (e.g. '12m 30s')."""
    if not seconds or seconds <= 0:
        return "< 1 minute"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)

    parts = []
    if d > 0:
        parts.append(f"{d}d")
    if h > 0:
        parts.append(f"{h}h")
    if m > 0:
        parts.append(f"{m}m")
    if s > 0 and d == 0 and h == 0:
        parts.append(f"{s}s")

    return " ".join(parts) if parts else "< 1 minute"


class TelegramNotifier:
    """Manages sending alert and recovery notifications to Telegram."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        api_base_url: str = "https://api.telegram.org",
        dashboard_url: str = "https://maui2023.github.io/git-uptime/",
    ):
        self.bot_token = (
            bot_token if bot_token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")
        ).strip()
        self.chat_id = (
            chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")
        ).strip()
        self.api_base_url = api_base_url.rstrip("/")
        self.dashboard_url = dashboard_url

    def is_configured(self) -> bool:
        """Check if both bot token and chat ID are configured."""
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a formatted message to Telegram.

        Fails gracefully without raising exceptions to protect the monitoring workflow.
        """
        if not self.is_configured():
            return False

        endpoint = f"{self.api_base_url}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Sabily-Uptime-Monitor/1.0",
        }

        req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status_code = resp.getcode()
                return 200 <= status_code < 300
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore") if hasattr(he, "read") else ""
            print(f"[!] Telegram API error (HTTP {he.code}): {err_body}")
            return False
        except Exception as exc:
            print(f"[!] Telegram notification error: {exc}")
            return False

    def notify_outage(self, monitor_result: Dict[str, Any], incident: Dict[str, Any]) -> bool:
        """Send a critical outage notification."""
        if not self.is_configured():
            return False

        name = monitor_result.get("name") or incident.get("monitor_name") or "Unknown Service"
        url = monitor_result.get("url") or "--"
        status_code = monitor_result.get("http_status_code")
        status_code_str = f"HTTP {status_code}" if status_code else (monitor_result.get("error_category") or "Connection Error")
        error_msg = monitor_result.get("error_message") or incident.get("error_description") or "Service is unreachable"
        started_at = incident.get("started_at", "Just now")

        # HTML formatting for Telegram
        text = (
            f"🚨 <b>ALERT: Service Outage Detected</b>\n\n"
            f"<b>Service:</b> {name}\n"
            f"<b>URL:</b> <code>{url}</code>\n"
            f"<b>Status:</b> <b>DOWN</b> ({status_code_str})\n"
            f"<b>Reason:</b> {error_msg}\n"
            f"<b>Detected:</b> <code>{started_at}</code>\n\n"
            f"🔗 <a href=\"{self.dashboard_url}\">View Status Dashboard</a>"
        )

        success = self.send_message(text)
        if success:
            print(f"[+] Telegram alert sent for {name} (OUTAGE)")
        return success

    def notify_recovery(self, monitor_result: Dict[str, Any], incident: Dict[str, Any]) -> bool:
        """Send a recovery notification when a service is restored."""
        if not self.is_configured():
            return False

        name = monitor_result.get("name") or incident.get("monitor_name") or "Unknown Service"
        url = monitor_result.get("url") or "--"
        status_code = monitor_result.get("http_status_code")
        status_code_str = f"HTTP {status_code}" if status_code else "200 OK"
        duration_sec = incident.get("duration_seconds")
        duration_str = format_duration(duration_sec)
        resolved_at = incident.get("resolved_at", "Just now")
        resp_time = monitor_result.get("response_time_ms")
        resp_time_str = f"{round(resp_time)}ms" if resp_time else "--"

        text = (
            f"✅ <b>RESOLVED: Service Restored</b>\n\n"
            f"<b>Service:</b> {name}\n"
            f"<b>URL:</b> <code>{url}</code>\n"
            f"<b>Status:</b> <b>UP</b> ({status_code_str})\n"
            f"<b>Latency:</b> {resp_time_str}\n"
            f"<b>Downtime Duration:</b> {duration_str}\n"
            f"<b>Resolved:</b> <code>{resolved_at}</code>\n\n"
            f"🔗 <a href=\"{self.dashboard_url}\">View Status Dashboard</a>"
        )

        success = self.send_message(text)
        if success:
            print(f"[+] Telegram recovery alert sent for {name} (RESOLVED)")
        return success
