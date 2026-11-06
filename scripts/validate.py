"""Validation module for Sabily Uptime Monitor.

Validates monitor configuration files and generated public JSON output data.
Can be run directly as a CLI tool: python scripts/validate.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Tuple


def validate_config(config_path: Path | str) -> Tuple[bool, List[str]]:
    """Validate configuration file (e.g. config/monitors.json)."""
    errors: List[str] = []
    path = Path(config_path)

    if not path.is_file():
        return False, [f"Config file not found at {path}"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, [f"Config file contains invalid JSON: {e}"]

    if not isinstance(data, dict):
        return False, ["Root configuration must be a JSON object"]

    # Validate settings
    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        errors.append("'settings' must be a JSON object")
    else:
        for field, min_val in [
            ("interval_seconds", 30),
            ("timeout_seconds", 1),
            ("retry_delay_seconds", 1),
            ("failure_threshold", 1),
            ("recovery_threshold", 1),
            ("history_days", 1),
            ("concurrency", 1),
        ]:
            val = settings.get(field)
            if val is None or not isinstance(val, int) or val < min_val:
                errors.append(f"Setting '{field}' must be an integer >= {min_val}")

    # Validate monitors
    monitors = data.get("monitors")
    if not isinstance(monitors, list):
        errors.append("'monitors' must be a list of monitor objects")
    else:
        seen_ids = set()
        for idx, mon in enumerate(monitors):
            if not isinstance(mon, dict):
                errors.append(f"Monitor at index {idx} must be an object")
                continue

            mon_id = mon.get("id")
            if not mon_id or not isinstance(mon_id, str):
                errors.append(f"Monitor at index {idx} has missing or non-string 'id'")
            elif not re.match(r"^[a-zA-Z0-9_\-]+$", mon_id):
                errors.append(f"Monitor ID '{mon_id}' must contain only letters, numbers, hyphens, and underscores")
            elif mon_id in seen_ids:
                errors.append(f"Duplicate monitor ID '{mon_id}' found")
            else:
                seen_ids.add(mon_id)

            name = mon.get("name")
            if not name or not isinstance(name, str):
                errors.append(f"Monitor '{mon_id or idx}' has missing or invalid 'name'")

            url = mon.get("url")
            if not url or not isinstance(url, str):
                errors.append(f"Monitor '{mon_id or idx}' has missing or invalid 'url'")
            else:
                parsed = urllib.parse.urlparse(url)
                if parsed.scheme not in ("http", "https"):
                    errors.append(f"Monitor '{mon_id}' has invalid URL scheme: '{parsed.scheme}'. Only http/https supported.")
                if not parsed.hostname:
                    errors.append(f"Monitor '{mon_id}' has invalid URL host: '{url}'")

            method = mon.get("method", "GET")
            if method not in ("GET", "HEAD"):
                errors.append(f"Monitor '{mon_id}' method must be GET or HEAD, got '{method}'")

            codes = mon.get("expected_status_codes", [200])
            if not isinstance(codes, list) or not all(isinstance(c, int) and 100 <= c <= 599 for c in codes):
                errors.append(f"Monitor '{mon_id}' 'expected_status_codes' must be a list of HTTP status code integers (100-599)")

    return len(errors) == 0, errors


def validate_data_files(data_dir: Path | str) -> Tuple[bool, List[str]]:
    """Validate generated public data files (latest.json, incidents.json, uptime-summary.json)."""
    errors: List[str] = []
    base_dir = Path(data_dir)

    if not base_dir.is_dir():
        return False, [f"Data directory '{base_dir}' does not exist"]

    latest_file = base_dir / "latest.json"
    incidents_file = base_dir / "incidents.json"
    summary_file = base_dir / "uptime-summary.json"

    # Validate latest.json
    if latest_file.is_file():
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                latest = json.load(f)
            required_fields = ["generated_at", "status", "summary", "monitors"]
            for field in required_fields:
                if field not in latest:
                    errors.append(f"latest.json missing required field: '{field}'")
            if "status" in latest and latest["status"] not in ("operational", "degraded", "outage", "stale"):
                errors.append(f"latest.json status invalid: '{latest['status']}'")
        except Exception as e:
            errors.append(f"latest.json corrupted or invalid: {e}")
    else:
        errors.append("latest.json does not exist")

    # Validate incidents.json
    if incidents_file.is_file():
        try:
            with open(incidents_file, "r", encoding="utf-8") as f:
                incidents_data = json.load(f)
            if "incidents" not in incidents_data or not isinstance(incidents_data["incidents"], list):
                errors.append("incidents.json must contain an 'incidents' array")
        except Exception as e:
            errors.append(f"incidents.json corrupted or invalid: {e}")
    else:
        errors.append("incidents.json does not exist")

    # Validate uptime-summary.json
    if summary_file.is_file():
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                summary = json.load(f)
            for field in ["generated_at", "monitors"]:
                if field not in summary:
                    errors.append(f"uptime-summary.json missing field: '{field}'")
        except Exception as e:
            errors.append(f"uptime-summary.json corrupted or invalid: {e}")
    else:
        errors.append("uptime-summary.json does not exist")

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate monitor configuration and data files.")
    parser.add_argument("--config", default="config/monitors.json", help="Path to config file")
    parser.add_argument("--data-dir", default="public/data", help="Path to data directory")
    parser.add_argument("--check-data", action="store_true", help="Also validate public data files")
    args = parser.parse_args()

    all_passed = True

    print(f"[*] Validating config file: {args.config}")
    cfg_ok, cfg_errs = validate_config(args.config)
    if cfg_ok:
        print("  [OK] Config file is valid.")
    else:
        print("  [FAIL] Config validation errors:")
        for err in cfg_errs:
            print(f"    - {err}")
        all_passed = False

    if args.check_data:
        print(f"[*] Validating data directory: {args.data_dir}")
        data_ok, data_errs = validate_data_files(args.data_dir)
        if data_ok:
            print("  [OK] Data files are valid.")
        else:
            print("  [FAIL] Data validation errors:")
            for err in data_errs:
                print(f"    - {err}")
            all_passed = False

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
