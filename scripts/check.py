"""Monitoring Engine for Sabily Uptime Monitor.

Executes concurrent HTTP/HTTPS checks directly using Python standard library,
measures response times, verifies SSL/DNS, prevents SSRF, handles false positives,
and persists records to public/data.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import functools
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Support running directly as a script or as a module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from scripts.incidents import IncidentManager
    from scripts.notifier import TelegramNotifier
    from scripts.storage import StorageManager
    from scripts.uptime import UptimeCalculator
    from scripts.utils import (
        get_date_str_now,
        get_iso_now,
        parse_iso_datetime,
        validate_url,
    )
except ImportError:
    from incidents import IncidentManager
    from notifier import TelegramNotifier
    from storage import StorageManager
    from uptime import UptimeCalculator
    from utils import (
        get_date_str_now,
        get_iso_now,
        parse_iso_datetime,
        validate_url,
    )


@functools.lru_cache(maxsize=1)
def get_ssl_context() -> ssl.SSLContext:
    """Cached SSL context to avoid re-parsing certificates on every probe."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except (ImportError, Exception):
        return ssl.create_default_context()


class SSRFSafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Intercepts HTTP redirects and aborts if redirect target points to a private/reserved address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        is_valid, err = validate_url(newurl)
        if not is_valid:
            raise urllib.error.URLError(f"SSRF protection blocked redirect to {newurl}: {err}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def execute_http_probe(
    url: str,
    method: str = "GET",
    timeout: int = 10,
    expected_status_codes: Optional[List[int]] = None,
    keyword: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a single HTTP/HTTPS probe with strict SSL verification and SSRF checking."""
    expected_codes = expected_status_codes or [200]

    # Pre-check URL and SSRF validation
    is_valid, err_msg = validate_url(url)
    if not is_valid:
        return {
            "status": "DOWN",
            "http_status_code": None,
            "response_time_ms": None,
            "error_category": "ssrf_blocked" if "SSRF" in (err_msg or "") or "private" in (err_msg or "") else "dns_error",
            "error_message": err_msg,
        }

    https_handler = urllib.request.HTTPSHandler(context=get_ssl_context())
    opener = urllib.request.build_opener(SSRFSafeRedirectHandler(), https_handler)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (compatible; Sabily-Uptime-Monitor/1.0; +https://github.com/maui2023/git-uptime)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    req_method = method.upper()

    def _do_request(actual_method: str) -> Tuple[int, float, bytes]:
        req = urllib.request.Request(url, headers=headers, method=actual_method)
        t0 = time.perf_counter()
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read(1024 * 1024) if actual_method == "GET" else b""
            code = resp.getcode()
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return code, elapsed_ms, body

    try:
        try:
            status_code, elapsed_ms, body = _do_request(req_method)
        except urllib.error.HTTPError as he:
            # Fallback if server doesn't support HEAD
            if req_method == "HEAD" and he.code in (405, 501):
                status_code, elapsed_ms, body = _do_request("GET")
            else:
                raise he

        # Check response body keyword if specified
        if keyword:
            body_text = body.decode("utf-8", errors="ignore")
            if keyword not in body_text:
                return {
                    "status": "DEGRADED",
                    "http_status_code": status_code,
                    "response_time_ms": elapsed_ms,
                    "error_category": "keyword_mismatch",
                    "error_message": f"Response did not contain required keyword: '{keyword}'",
                }

        # Classify status code
        if status_code in expected_codes:
            return {
                "status": "UP",
                "http_status_code": status_code,
                "response_time_ms": elapsed_ms,
                "error_category": None,
                "error_message": None,
            }
        elif 400 <= status_code < 500:
            return {
                "status": "DEGRADED",
                "http_status_code": status_code,
                "response_time_ms": elapsed_ms,
                "error_category": "http_4xx",
                "error_message": f"Unexpected HTTP status {status_code}",
            }
        else:
            return {
                "status": "DOWN",
                "http_status_code": status_code,
                "response_time_ms": elapsed_ms,
                "error_category": "http_5xx",
                "error_message": f"HTTP server error status {status_code}",
            }

    except urllib.error.HTTPError as e:
        status_code = e.code
        if status_code in expected_codes:
            return {
                "status": "UP",
                "http_status_code": status_code,
                "response_time_ms": None,
                "error_category": None,
                "error_message": None,
            }
        elif 400 <= status_code < 500:
            return {
                "status": "DEGRADED",
                "http_status_code": status_code,
                "response_time_ms": None,
                "error_category": "http_4xx",
                "error_message": f"Unexpected HTTP client error {status_code}",
            }
        else:
            return {
                "status": "DOWN",
                "http_status_code": status_code,
                "response_time_ms": None,
                "error_category": "http_5xx",
                "error_message": f"HTTP server error {status_code}",
            }

    except urllib.error.URLError as ue:
        reason_str = str(ue.reason)
        reason_lower = reason_str.lower()
        if "ssrf protection" in reason_lower or "private" in reason_lower:
            cat = "ssrf_blocked"
        elif isinstance(ue.reason, ssl.SSLError) or "ssl" in reason_lower or "certificate" in reason_lower:
            cat = "ssl_error"
        elif isinstance(ue.reason, socket.timeout) or "timed out" in reason_lower:
            cat = "timeout"
        elif isinstance(ue.reason, socket.gaierror) or "name resolution" in reason_lower or "getaddrinfo" in reason_lower:
            cat = "dns_error"
        elif "connection refused" in reason_lower:
            cat = "connection_refused"
        else:
            cat = "connection_error"

        return {
            "status": "DOWN",
            "http_status_code": None,
            "response_time_ms": None,
            "error_category": cat,
            "error_message": f"Connection failed: {reason_str}",
        }

    except (socket.timeout, TimeoutError):
        return {
            "status": "DOWN",
            "http_status_code": None,
            "response_time_ms": None,
            "error_category": "timeout",
            "error_message": f"Request timed out after {timeout}s",
        }

    except ssl.SSLError as se:
        return {
            "status": "DOWN",
            "http_status_code": None,
            "response_time_ms": None,
            "error_category": "ssl_error",
            "error_message": f"SSL verification failed: {se}",
        }

    except Exception as exc:
        return {
            "status": "DOWN",
            "http_status_code": None,
            "response_time_ms": None,
            "error_category": "unknown_error",
            "error_message": f"Unexpected check error: {exc}",
        }


def check_single_monitor(
    monitor: Dict[str, Any],
    settings: Dict[str, Any],
    prev_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute monitor check with retry and false positive prevention."""
    mon_id = monitor["id"]
    name = monitor.get("name", mon_id)
    url = monitor["url"]
    group = monitor.get("group", "Default")
    method = monitor.get("method", "GET")
    expected_codes = monitor.get("expected_status_codes", [200])
    keyword = monitor.get("keyword")

    timeout = settings.get("timeout_seconds", 10)
    retry_delay = settings.get("retry_delay_seconds", 5)
    failure_threshold = settings.get("failure_threshold", 2)
    recovery_threshold = settings.get("recovery_threshold", 1)

    prev_failures = (prev_state or {}).get("consecutive_failures", 0)
    prev_last_successful = (prev_state or {}).get("last_successful_check")

    now_iso = get_iso_now()

    # Attempt 1
    probe_result = execute_http_probe(
        url=url,
        method=method,
        timeout=timeout,
        expected_status_codes=expected_codes,
        keyword=keyword,
    )

    # False positive prevention: retry once if attempt 1 was not UP
    if probe_result["status"] != "UP" and retry_delay >= 0:
        if retry_delay > 0:
            time.sleep(retry_delay)
        probe_result_retry = execute_http_probe(
            url=url,
            method=method,
            timeout=timeout,
            expected_status_codes=expected_codes,
            keyword=keyword,
        )
        # Use retry result
        probe_result = probe_result_retry

    status = probe_result["status"]
    status_code = probe_result["http_status_code"]
    resp_ms = probe_result["response_time_ms"]
    err_cat = probe_result["error_category"]
    err_msg = probe_result["error_message"]

    # Evaluate failure threshold & state
    if status == "UP":
        consecutive_failures = 0
        state = "operational"
        last_successful = now_iso
        check_result = "success"
    elif status == "DEGRADED":
        consecutive_failures = prev_failures + 1
        state = "degraded"
        last_successful = prev_last_successful
        check_result = "failure"
    else:  # DOWN
        consecutive_failures = prev_failures + 1
        if consecutive_failures >= failure_threshold:
            state = "down"
        else:
            state = "pending_down"
        last_successful = prev_last_successful
        check_result = "failure"

    return {
        "id": mon_id,
        "name": name,
        "url": url,
        "group": group,
        "enabled": monitor.get("enabled", True),
        "status": status,
        "state": state,
        "http_status_code": status_code,
        "response_time_ms": resp_ms,
        "last_checked": now_iso,
        "last_successful_check": last_successful,
        "consecutive_failures": consecutive_failures,
        "error_category": err_cat,
        "error_message": err_msg,
        "check_result": check_result,
    }


def run_monitoring_cycle(
    config_path: Path | str = "config/monitors.json",
    data_dir: Path | str = "public/data",
    dry_run: bool = False,
    single_monitor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run full monitoring cycle across all configured monitors."""
    cfg_file = Path(config_path)
    if not cfg_file.is_file():
        raise FileNotFoundError(f"Config file not found: {cfg_file}")

    with open(cfg_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    settings = config.get("settings", {})
    monitors = config.get("monitors", [])
    concurrency = settings.get("concurrency", 30)

    storage = StorageManager(data_dir=data_dir)
    incidents_file = Path(data_dir) / "incidents.json"
    incident_mgr = IncidentManager(incidents_file=incidents_file)

    # Load previous latest data
    prev_latest = storage.load_latest() or {}
    prev_monitors_map = {m["id"]: m for m in prev_latest.get("monitors", [])}

    active_monitors = [m for m in monitors if m.get("enabled", True)]
    if single_monitor_id:
        active_monitors = [m for m in active_monitors if m.get("id") == single_monitor_id]

    print(f"[*] Starting monitoring cycle at {get_iso_now()}")
    print(f"[*] Total monitors: {len(active_monitors)} (concurrency: {concurrency})")
    telegram_notifier = TelegramNotifier()
    if telegram_notifier.is_configured():
        print("  [*] Telegram notifications: ENABLED")
    else:
        print("  [*] Telegram notifications: DISABLED (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set)")

    results: List[Dict[str, Any]] = []

    # Concurrent execution
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(concurrency, max(1, len(active_monitors)))) as executor:
        future_map = {
            executor.submit(
                check_single_monitor,
                mon,
                settings,
                prev_monitors_map.get(mon["id"]),
            ): mon
            for mon in active_monitors
        }
        for future in concurrent.futures.as_completed(future_map):
            mon_ref = future_map[future]
            try:
                res = future.result()
                results.append(res)
                print(f"  [+] {res['name']} ({res['id']}): {res['status']} ({res['state']}) - {res['http_status_code']} in {res['response_time_ms']}ms")
            except Exception as e:
                # Individual exception must never stop the monitoring run
                print(f"  [-] Error checking {mon_ref['id']}: {e}")
                results.append({
                    "id": mon_ref["id"],
                    "name": mon_ref.get("name", mon_ref["id"]),
                    "url": mon_ref.get("url", ""),
                    "group": mon_ref.get("group", "Default"),
                    "enabled": True,
                    "status": "DOWN",
                    "state": "down",
                    "http_status_code": None,
                    "response_time_ms": None,
                    "last_checked": get_iso_now(),
                    "last_successful_check": None,
                    "consecutive_failures": prev_monitors_map.get(mon_ref["id"], {}).get("consecutive_failures", 0) + 1,
                    "error_category": "unknown_error",
                    "error_message": str(e),
                    "check_result": "failure",
                })

    # Sort results to match original monitor order
    order_map = {m["id"]: idx for idx, m in enumerate(monitors)}
    results.sort(key=lambda r: order_map.get(r["id"], 999))

    # Manage incidents & send alerts
    for res in results:
        mid = res["id"]
        mname = res["name"]
        mstate = res["state"]
        err_msg = res["error_message"] or f"Service {mname} is unreachable"

        if mstate == "down":
            inc = incident_mgr.create_incident(
                monitor_id=mid,
                monitor_name=mname,
                error_description=err_msg,
            )
            # Only send outage notification on a newly created incident to avoid spamming
            if inc.get("is_new"):
                telegram_notifier.notify_outage(res, inc)
        elif res["status"] == "UP":
            resolved_inc = incident_mgr.resolve_incident(
                monitor_id=mid,
                resolution_message=f"Service {mname} responded with HTTP {res['http_status_code']} and is operational.",
            )
            if resolved_inc:
                telegram_notifier.notify_recovery(res, resolved_inc)

    # Compute overall status
    down_count = sum(1 for r in results if r["status"] == "DOWN")
    degraded_count = sum(1 for r in results if r["status"] == "DEGRADED" or r["state"] == "pending_down")
    up_count = sum(1 for r in results if r["status"] == "UP")

    if down_count > 0:
        overall_status = "outage"
    elif degraded_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "operational"

    today_str = get_date_str_now()

    # Append to daily history
    history_records = [
        {
            "timestamp": r["last_checked"],
            "monitor_id": r["id"],
            "status": r["status"],
            "http_status_code": r["http_status_code"],
            "response_time_ms": r["response_time_ms"],
            "error_category": r["error_category"],
            "check_result": r["check_result"],
        }
        for r in results
    ]

    latest_data = {
        "generated_at": get_iso_now(),
        "status": overall_status,
        "summary": {
            "total": len(results),
            "up": up_count,
            "down": down_count,
            "degraded": degraded_count,
            "paused": len(monitors) - len(results),
        },
        "monitors": results,
    }

    if dry_run:
        print("[!] Dry-run enabled. Skipping file persistence.")
        return latest_data

    # Save daily history
    storage.append_daily_history(history_records, today_str)

    # Prune history older than 30 days
    pruned = storage.prune_old_history(keep_days=settings.get("history_days", 30))
    if pruned > 0:
        print(f"[*] Pruned {pruned} old history file(s).")

    # Compute uptime summary
    calculator = UptimeCalculator(data_dir=data_dir, history_days=settings.get("history_days", 30))
    summary_data = calculator.compute_summary(
        monitors=monitors,
        incidents=incident_mgr.incidents,
    )

    # Merge 30d uptime percentage into latest monitors list for convenience
    for r in latest_data["monitors"]:
        mid = r["id"]
        mon_stat = summary_data.get("monitors", {}).get(mid, {})
        r["uptime_30d"] = mon_stat.get("uptime_30d")

    # Persist data
    storage.save_latest(latest_data)
    storage.save_uptime_summary(summary_data)
    incident_mgr.save()

    print(f"[*] Monitoring cycle completed. System status: {overall_status.upper()}")
    print(f"    UP: {up_count} | DEGRADED: {degraded_count} | DOWN: {down_count}")

    return latest_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Sabily Uptime Monitoring cycle.")
    parser.add_argument("--config", default="config/monitors.json", help="Path to monitors.json")
    parser.add_argument("--data-dir", default="public/data", help="Path to data output directory")
    parser.add_argument("--dry-run", action="store_true", help="Perform checks without saving data")
    parser.add_argument("--monitor", help="Check only a single monitor by ID")
    args = parser.parse_args()

    try:
        run_monitoring_cycle(
            config_path=args.config,
            data_dir=args.data_dir,
            dry_run=args.dry_run,
            single_monitor_id=args.monitor,
        )
        return 0
    except Exception as e:
        print(f"[FATAL] Monitoring cycle failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
