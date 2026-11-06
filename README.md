# ⚡ Sabily Uptime Monitor

> Independent, enterprise-grade website availability and latency monitoring platform powered entirely by **GitHub Actions** and **GitHub Pages**. Zero external monitoring services, zero VPS, zero databases.

[![Uptime Monitoring Engine](https://github.com/maui2023/git-uptime/actions/workflows/uptime.yml/badge.svg)](https://github.com/maui2023/git-uptime/actions/workflows/uptime.yml)
[![Deploy Status Dashboard to GitHub Pages](https://github.com/maui2023/git-uptime/actions/workflows/deploy.yml/badge.svg)](https://github.com/maui2023/git-uptime/actions/workflows/deploy.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 🌟 Overview

**Sabily Uptime Monitor** checks public websites and APIs directly using its own native Python 3 engine running on GitHub Actions. Results are persisted as Git-versioned JSON datasets and presented through a clean, responsive status dashboard hosted on GitHub Pages.

### ✨ Key Features
- **100% Self-Contained:** No dependence on third-party uptime providers (no UptimeRobot, no Upptime, no Better Stack).
- **Concurrent Probing:** Checks up to 30+ endpoints concurrently with configurable limits.
- **Enterprise Status Classification:** Accurately classifies status as `UP`, `DEGRADED`, or `DOWN` based on HTTP status codes, DNS resolution, TCP handshakes, TLS/SSL validation, response latency, and keyword validation.
- **False Positive Prevention:** Dual-attempt probes per cycle with a 2-cycle failure threshold before declaring outages.
- **Automated Incident Lifecycle:** Tracks incidents through `investigating` ➔ `identified` ➔ `monitoring` ➔ `resolved` states without duplicate alerts.
- **30-Day Availability Bars & Charts:** Daily uptime segments and Chart.js telemetry charts (Response Time 24h, Availability 30d, Incident Frequency).
- **Decoupled Architecture:** Frontend fetches live JSON directly from Git raw storage with cache-busting, eliminating the need to redeploy GitHub Pages on every 5-minute monitoring cycle.
- **SSRF & Security Hardened:** Protects against private IP / RFC 1918 redirection attacks, link-local abuse, and SSL certificate bypass.

---

## 🏗️ Architecture

```
                                    +-----------------------+
                                    |    GitHub Actions     |
                                    |  (Cron: */5 * * * *)  |
                                    +-----------+-----------+
                                                |
                                                v
                                  +---------------------------+
                                  |   Python 3 Check Engine   |
                                  |    (scripts/check.py)     |
                                  +-------------+-------------+
                                                |
                         +----------------------+----------------------+
                         |                      |                      |
                         v                      v                      v
                +-----------------+    +-----------------+    +-----------------+
                |   Endpoint 1    |    |   Endpoint 2    |    |   Endpoint N    |
                +-----------------+    +-----------------+    +-----------------+
                         |                      |                      |
                         +----------------------+----------------------+
                                                |
                                                v
                                    +-----------------------+
                                    |   JSON Persistence    |
                                    |    (public/data/)     |
                                    +-----------+-----------+
                                                |
                                                v
                                    +-----------------------+
                                    |  GitHub Pages Static  |
                                    |   Status Dashboard    |
                                    +-----------------------+
```

---

## 📁 Project Structure

```
git-uptime/
├── .github/
│   └── workflows/
│       ├── uptime.yml          # Executes monitoring engine every 5 minutes
│       └── deploy.yml          # Deploys dashboard to GitHub Pages on frontend changes
├── config/
│   └── monitors.json           # Monitored websites and global engine settings
├── scripts/
│   ├── check.py                # Main monitoring engine entrypoint
│   ├── incidents.py            # Incident lifecycle & deduplication manager
│   ├── storage.py              # File persistence & 30-day retention pruning
│   ├── uptime.py               # 24h, 7d, 30d uptime & chart metrics calculator
│   ├── validate.py             # Configuration & output JSON validation CLI
│   └── utils.py                # SSRF filtering, DNS validation, time helpers
├── tests/
│   ├── test_monitor.py         # HTTP 200, 301, 404, 500, timeout, DNS, SSL, SSRF tests
│   ├── test_uptime.py          # Uptime percentage formula and window calculation tests
│   ├── test_incidents.py       # Threshold, deduplication, and resolution tests
│   └── test_storage.py         # Storage, history rotation, and stale data tests
├── public/
│   ├── index.html              # Public status dashboard HTML
│   ├── assets/
│   │   ├── css/style.css       # Enterprise theme & 30-day uptime bar styles
│   │   └── js/
│   │       ├── api.js          # Fetch client with cache-busting & stale detection
│   │       ├── app.js          # DOM rendering & 60s auto-refresh loop
│   │       └── charts.js       # Chart.js response time & uptime visualizations
│   └── data/
│       ├── latest.json         # Real-time state of all monitors
│       ├── incidents.json      # Active & resolved incidents
│       ├── uptime-summary.json # 30-day history metrics for charts & bars
│       └── history/            # Compact daily JSON records (30-day retention)
├── requirements.txt
├── README.md
├── LICENSE
└── PRD.md
```

---

## 🚀 Setup & Deployment Guide

### 1. Enable GitHub Pages
1. Go to repository **Settings** ➔ **Pages**.
2. Under **Build and deployment** ➔ **Source**, select **GitHub Actions**.

### 2. Enable Workflow Read & Write Permissions
1. Go to repository **Settings** ➔ **Actions** ➔ **General**.
2. Scroll to **Workflow permissions**.
3. Select **Read and write permissions** and click **Save**.

### 3. Set Up Telegram Bot Notifications (Optional & 100% Confidential)
Receive instant alerts when an outage is detected or resolved without exposing tokens in public repositories:

1. **Create a Telegram Bot**:
   - Search for [@BotFather](https://t.me/BotFather) on Telegram.
   - Send `/newbot`, follow the prompts, and copy the generated **HTTP API Token** (e.g. `123456789:ABCdefGHI...`).
2. **Get your Telegram Chat ID**:
   - Start a conversation with your new bot (press **Start**).
   - Find your Chat ID via [@userinfobot](https://t.me/userinfobot) (or forward a message to [@GetIDsBot](https://t.me/GetIDsBot)). Copy the numeric ID.
3. **Store Secrets in GitHub**:
   - In your GitHub repository, go to **Settings** ➔ **Secrets and variables** ➔ **Actions**.
   - Click **New repository secret** and add:
     - `TELEGRAM_BOT_TOKEN`: `<your bot token>`
     - `TELEGRAM_CHAT_ID`: `<your chat ID>`
   - *These secrets are encrypted by GitHub and are never displayed in git history or publicly visible files.*

### 4. Add or Modify Monitored Websites
Edit `config/monitors.json`:

```json
{
  "settings": {
    "interval_seconds": 300,
    "timeout_seconds": 10,
    "retry_delay_seconds": 5,
    "failure_threshold": 2,
    "recovery_threshold": 1,
    "history_days": 30,
    "concurrency": 30
  },
  "monitors": [
    {
      "id": "my-service",
      "name": "My Production API",
      "url": "https://api.example.com/health",
      "group": "Core APIs",
      "method": "GET",
      "enabled": true,
      "expected_status_codes": [200, 204],
      "keyword": "HEALTHY"
    }
  ]
}
```

#### Monitor Fields:
| Field | Type | Description |
|---|---|---|
| `id` | String | Unique identifier (letters, numbers, hyphens, underscores). |
| `name` | String | Display name shown on dashboard. |
| `url` | String | Must be a public `http://` or `https://` endpoint. |
| `group` | String | Logical group for dashboard organization. |
| `method` | String | `GET` or `HEAD` (defaults to `GET`). |
| `enabled` | Boolean | `true` to monitor, `false` to pause. |
| `expected_status_codes` | List[Int] | Status codes considered operational (e.g. `[200, 301]`). |
| `keyword` *(Optional)* | String | Substring that must be present in response body. |

### 5. Running Locally

#### Run Unit Tests:
```bash
pytest -v
# or
python3 -m unittest discover tests
```

#### Run Monitoring Engine Manually:
```bash
python3 scripts/check.py
```

#### Validate Config & Data:
```bash
python3 scripts/validate.py --check-data
```

#### Preview Dashboard Locally:
```bash
python3 -m http.server 8000 --directory public
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 🛡️ Security & Reliability

1. **SSRF Guard:** Prohibits connections to private IP spaces (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`, `::1`, `fc00::/7`). Redirect targets are checked prior to each hop.
2. **TLS Verification:** Strict SSL verification is always enforced.
3. **No Stale False Positives:** Retries transient failures after a configurable delay. Declares outages only when consecutive failure threshold is breached.
4. **No Inventory Leaks:** No API tokens, passwords, or private URLs are recorded.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
