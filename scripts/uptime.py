"""Uptime calculation module for Sabily Uptime Monitor.

Calculates 24-hour, 7-day, and 30-day uptime percentages, daily historical segments,
response time distributions, and incident frequency for dashboard charts.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

try:
    from .utils import parse_iso_datetime
except ImportError:
    from utils import parse_iso_datetime


def calculate_uptime_percentage(successful: int, total: int) -> Optional[float]:
    """Calculate uptime percentage.

    Uptime Percentage = Successful Monitoring Checks / Total Valid Monitoring Checks * 100.
    Returns None if no checks were performed (never invent fake 100% for no data).
    """
    if total <= 0:
        return None
    pct = (successful / total) * 100.0
    return round(pct, 2)


class UptimeCalculator:
    """Computes uptime statistics and time-series summaries from historical check files."""

    def __init__(self, data_dir: Path | str, history_days: int = 30):
        self.data_dir = Path(data_dir)
        self.history_dir = self.data_dir / "history"
        self.history_days = history_days

    def load_recent_history_records(self, max_days: int = 30, now_date: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
        """Load records from daily history JSON files within the last max_days."""
        records: List[Dict[str, Any]] = []
        if not self.history_dir.is_dir():
            return records

        today = now_date or datetime.datetime.now(datetime.timezone.utc).date()
        cutoff_date = today - datetime.timedelta(days=max_days)

        for json_file in sorted(self.history_dir.glob("*.json")):
            stem = json_file.stem  # e.g. "2026-11-06"
            try:
                file_date = datetime.date.fromisoformat(stem)
                if file_date < cutoff_date:
                    continue
            except ValueError:
                continue

            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    day_records = json.load(f)
                    if isinstance(day_records, list):
                        records.extend(day_records)
            except Exception:
                continue

        return records

    def compute_summary(
        self,
        monitors: List[Dict[str, Any]],
        incidents: List[Dict[str, Any]],
        now: Optional[datetime.datetime] = None,
    ) -> Dict[str, Any]:
        """Compute comprehensive uptime summary for all monitors and overall system."""
        now_utc = now or datetime.datetime.now(datetime.timezone.utc)
        today = now_utc.date()
        records = self.load_recent_history_records(self.history_days, now_date=today)

        # Time cutoffs
        t_24h = now_utc - datetime.timedelta(hours=24)
        t_7d = now_utc - datetime.timedelta(days=7)
        t_30d = now_utc - datetime.timedelta(days=30)

        # Build date list for the last 30 days (chronological)
        date_list = [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(self.history_days - 1, -1, -1)]

        # Group records by monitor_id
        monitor_records: Dict[str, List[Dict[str, Any]]] = {m["id"]: [] for m in monitors}
        for rec in records:
            mid = rec.get("monitor_id")
            if mid in monitor_records:
                monitor_records[mid].append(rec)

        monitors_summary: Dict[str, Any] = {}
        total_30d_success = 0
        total_30d_checks = 0

        # Hourly buckets for the last 24h response time chart
        hourly_response_times: Dict[str, List[float]] = {}
        for h in range(24):
            dt_hour = (now_utc - datetime.timedelta(hours=23 - h)).strftime("%Y-%m-%d %H:00")
            hourly_response_times[dt_hour] = []

        for mon in monitors:
            mid = mon["id"]
            m_recs = monitor_records.get(mid, [])

            # 24h, 7d, 30d counters
            checks_24h = 0
            success_24h = 0
            response_times_24h: List[float] = []

            checks_7d = 0
            success_7d = 0

            checks_30d = 0
            success_30d = 0

            # Daily bucket for 30-day bars
            daily_buckets: Dict[str, Dict[str, int]] = {d: {"total": 0, "success": 0, "degraded": 0, "down": 0} for d in date_list}

            for rec in m_recs:
                ts_str = rec.get("timestamp", "")
                dt = parse_iso_datetime(ts_str)
                if not dt:
                    continue

                is_success = rec.get("check_result") == "success" or rec.get("status") == "UP"
                is_degraded = rec.get("status") == "DEGRADED"
                is_down = rec.get("status") == "DOWN"
                resp_ms = rec.get("response_time_ms")

                # Date bucket
                rec_date = dt.date().strftime("%Y-%m-%d")
                if rec_date in daily_buckets:
                    daily_buckets[rec_date]["total"] += 1
                    if is_success:
                        daily_buckets[rec_date]["success"] += 1
                    elif is_degraded:
                        daily_buckets[rec_date]["degraded"] += 1
                    elif is_down:
                        daily_buckets[rec_date]["down"] += 1

                # 30 days
                if dt >= t_30d:
                    checks_30d += 1
                    if is_success:
                        success_30d += 1

                # 7 days
                if dt >= t_7d:
                    checks_7d += 1
                    if is_success:
                        success_7d += 1

                # 24 hours
                if dt >= t_24h:
                    checks_24h += 1
                    if is_success:
                        success_24h += 1
                    if isinstance(resp_ms, (int, float)) and resp_ms > 0:
                        response_times_24h.append(float(resp_ms))
                        hour_key = dt.strftime("%Y-%m-%d %H:00")
                        if hour_key in hourly_response_times:
                            hourly_response_times[hour_key].append(float(resp_ms))

            total_30d_checks += checks_30d
            total_30d_success += success_30d

            pct_24h = calculate_uptime_percentage(success_24h, checks_24h)
            pct_7d = calculate_uptime_percentage(success_7d, checks_7d)
            pct_30d = calculate_uptime_percentage(success_30d, checks_30d)
            avg_resp_24h = round(sum(response_times_24h) / len(response_times_24h), 1) if response_times_24h else None

            # Build daily history list for 30-day bar display
            daily_history = []
            for d in date_list:
                bucket = daily_buckets[d]
                tot = bucket["total"]
                suc = bucket["success"]
                deg = bucket["degraded"]
                dwn = bucket["down"]
                day_pct = calculate_uptime_percentage(suc, tot) if tot > 0 else None

                if tot == 0:
                    day_status = "NODATA"
                elif dwn > 0:
                    day_status = "DOWN"
                elif deg > 0 or (day_pct is not None and day_pct < 99.0):
                    day_status = "DEGRADED"
                else:
                    day_status = "UP"

                daily_history.append({
                    "date": d,
                    "uptime_percentage": day_pct,
                    "status": day_status,
                    "total_checks": tot,
                    "successful_checks": suc,
                })

            monitors_summary[mid] = {
                "id": mid,
                "name": mon.get("name", mid),
                "uptime_24h": pct_24h,
                "uptime_7d": pct_7d,
                "uptime_30d": pct_30d,
                "avg_response_time_24h": avg_resp_24h,
                "total_checks_30d": checks_30d,
                "successful_checks_30d": success_30d,
                "daily_history": daily_history,
            }

        overall_30d = calculate_uptime_percentage(total_30d_success, total_30d_checks)

        # 24-hour response time series for Chart.js
        chart_response_series = []
        for hour_lbl, r_list in hourly_response_times.items():
            avg_val = round(sum(r_list) / len(r_list), 1) if r_list else None
            # Display format: "14:00"
            display_label = hour_lbl.split(" ")[-1]
            chart_response_series.append({
                "time": display_label,
                "datetime": hour_lbl,
                "iso": hour_lbl.replace(" ", "T") + ":00Z",
                "avg_ms": avg_val,
            })

        # Incident frequency per day for the last 30 days
        incident_counts_by_date = {d: 0 for d in date_list}
        for inc in incidents:
            start_iso = inc.get("started_at", "")
            inc_dt = parse_iso_datetime(start_iso)
            if inc_dt:
                inc_date = inc_dt.date().strftime("%Y-%m-%d")
                if inc_date in incident_counts_by_date:
                    incident_counts_by_date[inc_date] += 1

        chart_incident_series = [
            {"date": d, "count": incident_counts_by_date[d]} for d in date_list
        ]

        # 30-day overall availability series
        chart_availability_series = []
        for d in date_list:
            day_success = 0
            day_total = 0
            for mid, m_data in monitors_summary.items():
                for dh in m_data.get("daily_history", []):
                    if dh["date"] == d:
                        day_success += dh["successful_checks"]
                        day_total += dh["total_checks"]
            day_pct = calculate_uptime_percentage(day_success, day_total)
            chart_availability_series.append({
                "date": d,
                "uptime_percentage": day_pct,
            })

        return {
            "generated_at": now_utc.isoformat(),
            "overall_uptime_30d": overall_30d,
            "monitors": monitors_summary,
            "charts": {
                "response_time_24h": chart_response_series,
                "availability_30d": chart_availability_series,
                "incident_frequency_30d": chart_incident_series,
            },
        }
