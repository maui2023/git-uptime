PRD — SABİLY UPTIME MONITOR

Version: 1.0
Project: Sabily Uptime Monitor
Product Type: Public Website Status Monitoring Platform
Deployment: GitHub Pages
Monitoring Engine: GitHub Actions
Storage: Git Repository + JSON
Monitoring Interval: 5 Minutes
Target Capacity: 10–30 websites
Status: Ready for Implementation

⸻

1. PROJECT OBJECTIVE

Build a fully independent website uptime monitoring platform using GitHub Pages and GitHub Actions.

The platform must monitor public websites directly using its own monitoring engine without depending on any external uptime monitoring provider, commercial monitoring API, VPS, external backend, or third-party monitoring infrastructure.

The system must automatically:

1. Check website availability every 5 minutes.
2. Measure HTTP response time.
3. Detect HTTP errors, connection failures, DNS failures and SSL errors.
4. Record uptime and downtime history.
5. Calculate uptime percentages.
6. Track incidents and recovery events.
7. Publish monitoring data for the public status dashboard.
8. Display real-time-ish status information through a responsive website.

Core principle:

GitHub Actions performs the monitoring. GitHub Repository stores monitoring data. GitHub Pages displays monitoring results.

No external monitoring service is permitted.

2. SYSTEM ARCHITECTURE

2.1 Architecture Components

Component	Technology	Responsibility
Frontend	HTML5	Public status page
CSS	Bootstrap 5.3 + Custom CSS	UI and responsive layout
JavaScript	Vanilla JS	Fetch and render status data
Charts	Chart.js	Uptime and response charts
Monitoring Engine	Python 3	Website availability checks
Scheduler	GitHub Actions	Execute every 5 minutes
Storage	JSON	Monitoring records
Version Control	Git	History and persistence
Hosting	GitHub Pages	Public dashboard

No PHP, MySQL, Node.js server, Docker, VPS or external backend is required.

2.2 Monitoring Flow

1. GitHub Actions starts on a 5-minute schedule.
2. Python monitoring engine reads config/monitors.json.
3. Engine checks all enabled websites concurrently.
4. Each website receives an HTTP/HTTPS request.
5. Engine records status code, response time and errors.
6. Engine updates uptime history and incident records.
7. Engine commits updated JSON data to the repository.
8. GitHub Pages frontend fetches the latest published JSON.
9. Dashboard renders the updated monitoring results.

2.3 Important Deployment Architecture

Deploy the frontend separately from monitoring data updates.

* GitHub Pages hosts the static frontend.
* Monitoring workflow commits JSON data to the repository.
* Frontend fetches public JSON directly from the repository’s raw content URL.
* Frontend must not require a new GitHub Pages deployment for every monitoring cycle.

This avoids unnecessary Pages deployments every five minutes.

Use a configurable repository data URL and cache-busting query parameters when fetching JSON.

3. MONITORING REQUIREMENTS

3.1 Website Configuration

Create:

config/monitors.json

Example:

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
      "id": "sabily-main",
      "name": "Sabily Enterprise",
      "url": "https://sabily.info",
      "group": "Main Website",
      "method": "GET",
      "enabled": true,
      "expected_status_codes": [200, 201, 204, 301, 302, 307, 308]
    },
    {
      "id": "mpanel",
      "name": "MPanel Hosting",
      "url": "https://pats.my",
      "group": "Hosting",
      "method": "GET",
      "enabled": true,
      "expected_status_codes": [200, 301, 302]
    }
  ]
}

Requirements:

* Support at least 30 monitors.
* Each monitor must have a unique ID.
* Allow monitor grouping.
* Allow enabling and disabling individual monitors.
* Allow custom expected HTTP status codes.
* Allow GET or HEAD methods.
* Support configurable timeout.
* Support optional keyword validation.
* Validate URLs before executing checks.
* Reject unsupported URL schemes.
* Do not permit arbitrary internal IP monitoring by default.

3.2 HTTP Monitoring Logic

Implement direct HTTP/HTTPS requests.

Check the following:

* DNS resolution.
* TCP connection.
* TLS/SSL validation.
* HTTP response.
* HTTP status code.
* Response time.
* Connection timeout.
* Redirect handling.

Use Python standard library where practical. Third-party monitoring SDKs and APIs are prohibited.

HEAD requests should be supported, with optional GET fallback for servers that do not support HEAD.

Do not disable SSL certificate verification.

3.3 Status Classification

Condition	Status
Expected HTTP response	UP
Unexpected HTTP 4xx	DEGRADED
HTTP 5xx	DOWN
DNS resolution failure	DOWN
Connection refused	DOWN
Connection timeout	DOWN
SSL verification failure	DOWN
Response keyword mismatch	DEGRADED

The expected HTTP status code list must be configurable per monitor.

3.4 False Positive Prevention

Implement failure confirmation.

1. Perform the first request.
2. If unsuccessful, wait 5 seconds.
3. Retry once.
4. Record both attempts.
5. Apply the configured failure threshold across scheduled monitoring cycles.

A monitor should be declared DOWN only after two consecutive failed scheduled checks.

Recovery should be recorded when a subsequent check succeeds.

The dashboard must distinguish:

* Current observed state.
* Pending failure confirmation.
* Confirmed incident.

3.5 Concurrent Monitoring

Monitoring 30 websites must not require 30 separate workflow jobs.

Use concurrent requests with a configurable concurrency limit.

Requirements:

* Default concurrency: 30.
* Per-request timeout: 10 seconds.
* Retry only failed requests.
* Prevent overlapping monitoring workflow executions.
* Handle individual monitor exceptions without stopping the entire monitoring run.

4. DATA STORAGE

Use JSON files committed to the Git repository.

No external database.

4.1 Required Data Files

public/
└── data/
    ├── latest.json
    ├── incidents.json
    ├── uptime-summary.json
    └── history/
        ├── 2026-11-06.json
        ├── 2026-11-07.json
        └── ...

Dates above are illustrative.

4.2 latest.json

Contains:

* Last monitoring timestamp.
* Overall system status.
* Total monitors.
* UP count.
* DOWN count.
* DEGRADED count.
* Individual monitor results.
* Response time.
* HTTP status code.
* Last successful check.
* Consecutive failure count.

4.3 Daily History

Store one JSON file per monitoring day.

Each record should include:

* Timestamp.
* Monitor ID.
* Status.
* HTTP status code.
* Response time.
* Error category.
* Check result.

Use compact JSON to reduce repository size.

Retain 30 days of detailed monitoring records.

4.4 Uptime Summary

Calculate:

* Last 24 hours.
* Last 7 days.
* Last 30 days.

Formula:

Uptime Percentage = Successful Monitoring Checks / Total Valid Monitoring Checks × 100

Exclude checks that have not yet been performed.

Do not silently classify missing monitoring data as successful.

Store summary information in uptime-summary.json.

4.5 Incident History

Create an incident when a monitor becomes DOWN.

Incident fields:

* Incident ID.
* Monitor ID.
* Monitor name.
* Started timestamp.
* Resolved timestamp.
* Duration.
* Incident status.
* Error description.

Incident lifecycle:

* Investigating.
* Identified.
* Monitoring.
* Resolved.

Do not generate duplicate incidents for the same ongoing outage.

5. PUBLIC STATUS DASHBOARD

5.1 Design Direction

Create a premium enterprise-grade status dashboard.

Design references:

* Atlassian Statuspage.
* Better Stack Status.
* Professional enterprise SaaS dashboards.

Design requirements:

* Clean and minimal.
* Professional typography.
* Excellent spacing.
* Light theme by default.
* White background.
* Neutral grey surfaces.
* Green for operational.
* Amber for degraded.
* Red for down.
* Responsive mobile layout.
* No unnecessary gradients.
* No excessive rounded cards.
* No generic AI-generated dashboard appearance.
* Avoid oversized decorative graphics.

Use Bootstrap 5.3 and custom CSS.

5.2 Dashboard Header

Display:

* Brand logo / text.
* Platform name.
* Current overall status.
* Last updated timestamp.
* Automatic refresh indicator.

5.3 Overall Status

Possible messages:

* All Systems Operational.
* Partial System Degradation.
* Major System Outage.
* Monitoring Data Stale.

The overall status must be calculated from monitor results, not hardcoded.

5.4 Summary Statistics

Display:

* Total Monitors.
* Operational.
* Degraded.
* Down.

5.5 Service List

Group monitors by category.

Each monitor must display:

* Service name.
* Group.
* Current status.
* HTTP status code.
* Response time.
* Last checked timestamp.
* 30-day uptime percentage.
* 30-day uptime bar.

5.6 Uptime Bar

Show 30 daily segments or 30-day availability visualization.

Colors:

* Green: UP.
* Amber: DEGRADED.
* Red: DOWN.
* Grey: No data.

Hover or tap should display the date and daily uptime percentage.

5.7 Charts

Use Chart.js.

Required charts:

1. Response time over the last 24 hours.
2. Uptime percentage over the last 30 days.
3. Incident frequency.

Charts must use actual stored monitoring records.

Do not fabricate sample production metrics.

5.8 Incident Section

Display:

* Active incidents.
* Resolved incidents.
* Incident duration.
* Affected services.
* Start and resolution times.

Show a clear message when no incidents exist.

5.9 Auto Refresh

Refresh dashboard data every 60 seconds.

Display the last successful data update.

If JSON cannot be fetched:

* Keep the last valid data.
* Display a data refresh warning.
* Do not incorrectly display all services as operational.

Mark monitoring data stale if the latest successful monitoring run is older than 15 minutes.

6. GITHUB ACTIONS

Create:

.github/workflows/uptime.yml

Requirements:

* Schedule: */5 * * * *.
* Manual execution using workflow_dispatch.
* Ubuntu hosted runner.
* Python 3.
* Read/write repository contents permission.
* Concurrency protection.
* Execute monitoring engine.
* Validate generated JSON.
* Commit updated data.
* Avoid empty commits.
* Handle Git push conflicts safely.
* Preserve existing monitoring history.
* Never overwrite newer monitoring data with older data.

Do not run a GitHub Pages deployment on every monitoring cycle.

Use a separate workflow for frontend deployment.

Create:

.github/workflows/deploy.yml

Deployment triggers:

* Push to main when frontend source files change.
* Manual deployment.

Use the official GitHub Pages deployment actions.

Use least-privilege permissions.

Pin third-party actions to verified versions or immutable commit SHAs.

Important operational requirements:

* Scheduled workflows are not guaranteed to start at the exact scheduled minute.
* Prevent overlapping executions.
* Make monitoring idempotent.
* Record workflow execution timestamp.
* Record monitoring failures.
* Handle missed or delayed schedules without inventing successful checks.

7. SECURITY REQUIREMENTS

This project must be safe for a public GitHub repository.

Requirements:

1. No secrets in frontend JavaScript.
2. No tokens in public JSON.
3. No private URLs.
4. No internal network scanning.
5. HTTPS certificate verification enabled.
6. Validate monitor configuration.
7. Restrict monitoring to public HTTP/HTTPS destinations.
8. Protect against SSRF and redirect-based access to private IP ranges.
9. Validate redirect destinations.
10. Prevent arbitrary command execution from configuration.
11. No third-party monitoring APIs.
12. No external database credentials.

The monitoring engine must only access explicitly configured public websites.

No authentication is required for the public status dashboard.

8. PROJECT STRUCTURE

Implement this structure:

sabily-status/
│
├── .github/
│   └── workflows/
│       ├── uptime.yml
│       └── deploy.yml
│
├── config/
│   └── monitors.json
│
├── scripts/
│   ├── check.py
│   ├── storage.py
│   ├── uptime.py
│   ├── incidents.py
│   ├── validate.py
│   └── utils.py
│
├── tests/
│   ├── test_monitor.py
│   ├── test_uptime.py
│   ├── test_incidents.py
│   └── test_storage.py
│
├── public/
│   ├── index.html
│   ├── assets/
│   │   ├── css/
│   │   │   └── style.css
│   │   ├── js/
│   │   │   ├── app.js
│   │   │   ├── charts.js
│   │   │   └── api.js
│   │   └── images/
│   └── data/
│       ├── latest.json
│       ├── incidents.json
│       ├── uptime-summary.json
│       └── history/
│
├── requirements.txt
├── README.md
├── LICENSE
└── PRD.md

9. TESTING REQUIREMENTS

Implement automated tests.

Test cases:

1. Website returns HTTP 200.
2. Website returns HTTP 301.
3. Website returns HTTP 404.
4. Website returns HTTP 500.
5. Website connection timeout.
6. DNS resolution failure.
7. SSL verification failure.
8. HEAD unsupported and GET fallback.
9. Retry behavior.
10. Failure threshold.
11. Recovery detection.
12. Duplicate incident prevention.
13. Uptime percentage calculation.
14. Daily history generation.
15. JSON validation.
16. Concurrent monitoring of 30 websites.
17. Redirect to private IP rejection.
18. Stale monitoring data detection.

Tests must use local mock HTTP servers or controlled fixtures.

Do not rely on production websites to pass automated unit tests.

10. PERFORMANCE REQUIREMENTS

* Support 30 monitors.
* Monitoring requests must run concurrently.
* Default HTTP timeout: 10 seconds.
* Retry delay: 5 seconds.
* Monitoring job should normally finish within 60 seconds for 30 responsive websites.
* Dashboard must remain usable on mobile.
* Minimize JSON payload size.
* Avoid unnecessary Git commits.
* Preserve 30 days of detailed history.
* Avoid rebuilding GitHub Pages every five minutes.

11. ACCEPTANCE CRITERIA

The project is considered complete when:

* [ ]	GitHub repository contains the complete source code.
* [ ]	GitHub Pages successfully deploys.
* [ ]	Public dashboard loads without a backend server.
* [ ]	Monitoring executes every five minutes.
* [ ]	At least 30 monitors can be configured.
* [ ]	Websites are checked directly using Python.
* [ ]	HTTP response time is recorded.
* [ ]	HTTP errors are classified correctly.
* [ ]	DNS and SSL failures are detected.
* [ ]	False positive prevention works.
* [ ]	Incident lifecycle works.
* [ ]	Uptime calculations are accurate.
* [ ]	Daily history is persisted.
* [ ]	Dashboard refreshes automatically.
* [ ]	Stale monitoring data is detected.
* [ ]	No external uptime provider is required.
* [ ]	No VPS or paid backend is required.
* [ ]	No external database is required.
* [ ]	Automated tests pass.
* [ ]	README contains setup and deployment instructions.

12. IMPLEMENTATION INSTRUCTIONS FOR CODEX

You are the lead software engineer responsible for implementing this project.

Do not merely produce a tutorial or architecture proposal. Build the complete working application.

Phase 1 — Repository Inspection

1. Inspect the current GitHub repository.
2. Identify the default branch.
3. Preserve existing user files.
4. Inspect existing GitHub Pages settings if accessible.
5. Do not overwrite unrelated projects.

If no repository exists, request the repository name or explicit permission to create one.

Phase 2 — Implementation

Implement all required files.

Do not leave:

* Placeholder functions.
* Fake monitoring data.
* Non-functional buttons.
* Empty modules.
* Mock production responses.
* TODO-only implementations.

Use real monitoring logic.

Phase 3 — Testing

Run Python unit tests.

Run JSON validation.

Test the dashboard locally.

Validate workflow YAML.

Check the monitoring logic with controlled HTTP responses.

Phase 4 — Deployment

1. Commit the completed source code.
2. Configure GitHub Actions workflows.
3. Configure GitHub Pages deployment.
4. Deploy the frontend.
5. Execute the monitoring workflow manually.
6. Verify generated JSON.
7. Verify the public dashboard.
8. Verify automatic refresh.
9. Confirm scheduled workflow configuration.

Do not claim deployment success until GitHub confirms successful deployment.

Phase 5 — Final Report

Provide:

* GitHub repository URL.
* GitHub Pages URL.
* List of implemented features.
* Deployment status.
* Monitoring workflow status.
* Test results.
* How to add new websites.
* Any remaining manual GitHub configuration.

IMPORTANT RESTRICTIONS

* Do not integrate UptimeRobot.
* Do not integrate Upptime.
* Do not integrate Better Stack.
* Do not integrate external monitoring APIs.
* Do not require an external VPS.
* Do not require an external database.
* Do not use an external backend to perform monitoring.
* Do not replace GitHub Actions with a third-party scheduler.

The platform must perform all website availability checks directly through its own Python monitoring engine running on GitHub Actions.

GitHub is the only required infrastructure provider.

⸻

END OF PRD
