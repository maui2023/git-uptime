"""Incident management module for Sabily Uptime Monitor.

Handles incident creation, updating, deduplication, resolution, and history persistence.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

try:
    from .utils import get_iso_now, parse_iso_datetime
except ImportError:
    from utils import get_iso_now, parse_iso_datetime


class IncidentManager:
    """Manages system incidents for monitored services."""

    def __init__(self, incidents_file: Path | str):
        self.incidents_file = Path(incidents_file)
        self.incidents: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        """Load incidents from disk."""
        if self.incidents_file.is_file():
            try:
                with open(self.incidents_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.incidents = data.get("incidents", [])
            except Exception:
                self.incidents = []
        else:
            self.incidents = []

    def save(self) -> None:
        """Save incidents to disk."""
        self.incidents_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_updated": get_iso_now(),
            "total_incidents": len(self.incidents),
            "active_incidents": len(self.get_active_incidents()),
            "incidents": self.incidents,
        }
        with open(self.incidents_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def get_active_incident_for_monitor(self, monitor_id: str) -> Optional[Dict[str, Any]]:
        """Return the current open incident for a monitor, if any."""
        for inc in self.incidents:
            if inc.get("monitor_id") == monitor_id and inc.get("status") != "resolved":
                return inc
        return None

    def get_active_incidents(self) -> List[Dict[str, Any]]:
        """Return all active (unresolved) incidents."""
        return [inc for inc in self.incidents if inc.get("status") != "resolved"]

    def create_incident(
        self,
        monitor_id: str,
        monitor_name: str,
        error_description: str,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new incident if an ongoing one does not already exist."""
        existing = self.get_active_incident_for_monitor(monitor_id)
        if existing:
            # Do not duplicate ongoing incident
            return existing

        now_str = timestamp or get_iso_now()
        ts_clean = now_str.replace(":", "").replace("-", "").replace(".", "")[:15]
        incident_id = f"inc-{monitor_id}-{ts_clean}"

        incident: Dict[str, Any] = {
            "id": incident_id,
            "monitor_id": monitor_id,
            "monitor_name": monitor_name,
            "started_at": now_str,
            "resolved_at": None,
            "duration_seconds": None,
            "status": "investigating",
            "error_description": error_description,
            "updates": [
                {
                    "timestamp": now_str,
                    "status": "investigating",
                    "message": f"Outage detected: {error_description}",
                }
            ],
        }

        # Insert at the beginning so newest incidents appear first
        self.incidents.insert(0, incident)
        return incident

    def update_incident_status(
        self,
        incident_id: str,
        new_status: str,
        message: str,
        timestamp: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Add an update entry and change status of an active incident."""
        now_str = timestamp or get_iso_now()
        for inc in self.incidents:
            if inc.get("id") == incident_id and inc.get("status") != "resolved":
                inc["status"] = new_status
                inc.setdefault("updates", []).append({
                    "timestamp": now_str,
                    "status": new_status,
                    "message": message,
                })
                return inc
        return None

    def resolve_incident(
        self,
        monitor_id: str,
        resolution_message: str = "Service has recovered and is now operational.",
        timestamp: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Resolve any active incident for this monitor."""
        existing = self.get_active_incident_for_monitor(monitor_id)
        if not existing:
            return None

        now_str = timestamp or get_iso_now()
        existing["status"] = "resolved"
        existing["resolved_at"] = now_str

        # Calculate duration
        start_dt = parse_iso_datetime(existing.get("started_at", ""))
        end_dt = parse_iso_datetime(now_str)
        if start_dt and end_dt:
            delta = end_dt - start_dt
            existing["duration_seconds"] = max(0, int(delta.total_seconds()))
        else:
            existing["duration_seconds"] = 0

        existing.setdefault("updates", []).append({
            "timestamp": now_str,
            "status": "resolved",
            "message": resolution_message,
        })
        return existing
