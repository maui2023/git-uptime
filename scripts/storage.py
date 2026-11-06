"""Storage module for Sabily Uptime Monitor.

Manages saving and loading of JSON data: latest.json, incidents.json,
uptime-summary.json, and daily history files with 30-day retention pruning.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class StorageManager:
    """Manages file persistence for monitoring data in public/data/."""

    def __init__(self, data_dir: Path | str = "public/data"):
        self.data_dir = Path(data_dir)
        self.history_dir = self.data_dir / "history"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def load_latest(self) -> Optional[Dict[str, Any]]:
        """Load latest.json if it exists."""
        target = self.data_dir / "latest.json"
        if not target.is_file():
            return None
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_latest(self, data: Dict[str, Any]) -> None:
        """Save latest.json."""
        target = self.data_dir / "latest.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def append_daily_history(self, records: List[Dict[str, Any]], date_str: str) -> None:
        """Append records to history/YYYY-MM-DD.json using compact JSON formatting."""
        target = self.history_dir / f"{date_str}.json"
        existing_records: List[Dict[str, Any]] = []

        if target.is_file():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, list):
                        existing_records = content
            except Exception:
                existing_records = []

        existing_records.extend(records)

        with open(target, "w", encoding="utf-8") as f:
            # Compact JSON to keep repository size minimal
            json.dump(existing_records, f, separators=(",", ":"))

    def prune_old_history(self, keep_days: int = 30) -> int:
        """Prune daily history files older than keep_days. Returns count of deleted files."""
        if not self.history_dir.is_dir():
            return 0

        today = datetime.datetime.now(datetime.timezone.utc).date()
        cutoff_date = today - datetime.timedelta(days=keep_days)
        deleted_count = 0

        for file_path in self.history_dir.glob("*.json"):
            stem = file_path.stem
            try:
                file_date = datetime.date.fromisoformat(stem)
                if file_date < cutoff_date:
                    file_path.unlink()
                    deleted_count += 1
            except ValueError:
                continue

        return deleted_count

    def save_uptime_summary(self, data: Dict[str, Any]) -> None:
        """Save uptime-summary.json."""
        target = self.data_dir / "uptime-summary.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_uptime_summary(self) -> Optional[Dict[str, Any]]:
        """Load uptime-summary.json if it exists."""
        target = self.data_dir / "uptime-summary.json"
        if not target.is_file():
            return None
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
