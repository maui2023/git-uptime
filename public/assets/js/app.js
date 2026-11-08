/**
 * Main application script for Sabily Uptime Monitor dashboard.
 */

document.addEventListener("DOMContentLoaded", () => {
  const REFRESH_INTERVAL_SECONDS = 60;
  let countdown = REFRESH_INTERVAL_SECONDS;
  let countdownTimer = null;

  const elements = {
    statusBanner: document.getElementById("status-banner"),
    bannerTitle: document.getElementById("banner-title"),
    bannerSubtitle: document.getElementById("banner-subtitle"),
    bannerIcon: document.getElementById("banner-icon"),
    lastUpdated: document.getElementById("last-updated"),
    refreshCountdown: document.getElementById("refresh-countdown"),
    btnRefresh: document.getElementById("btn-refresh"),
    refreshAlert: document.getElementById("refresh-alert"),
    metricTotal: document.getElementById("metric-total"),
    metricOperational: document.getElementById("metric-operational"),
    metricDegraded: document.getElementById("metric-degraded"),
    metricDown: document.getElementById("metric-down"),
    metricUptime: document.getElementById("metric-uptime"),
    activeIncidentsContainer: document.getElementById("active-incidents-container"),
    monitorsContainer: document.getElementById("monitors-container"),
    pastIncidentsContainer: document.getElementById("past-incidents-container"),
  };

  /**
   * Escape HTML utility to prevent XSS
   */
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  /**
   * Format ISO date string into human-friendly relative or local time
   */
  function formatTimestamp(isoStr) {
    if (!isoStr) return "--";
    try {
      const dt = new Date(isoStr);
      return dt.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    } catch (_) {
      return isoStr;
    }
  }

  /**
   * Format duration in seconds into human-readable string (e.g. "12m 30s")
   */
  function formatDuration(seconds) {
    if (!seconds || seconds <= 0) return "< 1m";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    if (m === 0) return `${s}s`;
    if (m < 60) return `${m}m ${s}s`;
    const h = Math.floor(m / 60);
    const remM = m % 60;
    return `${h}h ${remM}m`;
  }

  /**
   * Render System Status Hero Banner
   */
  function renderHeroBanner(latest, isStale, hasError) {
    elements.statusBanner.className = "status-banner";

    if (hasError && !latest) {
      elements.statusBanner.classList.add("is-stale");
      elements.bannerTitle.innerHTML = `<span class="banner-pulse"></span> Unable to Connect to Data Source`;
      elements.bannerSubtitle.textContent = "Could not fetch monitoring status. Check your network or GitHub connection.";
      return;
    }

    if (isStale) {
      elements.statusBanner.classList.add("is-stale");
      elements.bannerTitle.innerHTML = `<span class="banner-pulse"></span> Monitoring Data Stale`;
      elements.bannerSubtitle.textContent = `Last monitoring run occurred at ${formatTimestamp(latest.generated_at)} (> 15 minutes ago).`;
      return;
    }

    const status = latest.status || "operational";
    if (status === "outage") {
      elements.statusBanner.classList.add("is-outage");
      elements.bannerTitle.innerHTML = `<span class="banner-pulse"></span> Major System Outage`;
      elements.bannerSubtitle.textContent = "One or more critical services are currently experiencing downtime.";
    } else if (status === "degraded") {
      elements.statusBanner.classList.add("is-degraded");
      elements.bannerTitle.innerHTML = `<span class="banner-pulse"></span> Partial System Degradation`;
      elements.bannerSubtitle.textContent = "Some services are reporting degraded performance or elevated response times.";
    } else {
      elements.statusBanner.classList.add("is-operational");
      elements.bannerTitle.innerHTML = `<span class="banner-pulse"></span> All Systems Operational`;
      elements.bannerSubtitle.textContent = "All configured public endpoints are responsive and healthy.";
    }
  }

  /**
   * Render Metrics Summary
   */
  function renderMetrics(latest, summary) {
    if (!latest || !latest.summary) return;
    const s = latest.summary;

    if (elements.metricTotal) elements.metricTotal.textContent = s.total ?? 0;
    if (elements.metricOperational) elements.metricOperational.textContent = s.up ?? 0;
    if (elements.metricDegraded) elements.metricDegraded.textContent = s.degraded ?? 0;
    if (elements.metricDown) elements.metricDown.textContent = s.down ?? 0;

    const overallPct = summary && summary.overall_uptime_30d !== null && summary.overall_uptime_30d !== undefined
      ? `${summary.overall_uptime_30d.toFixed(2)}%`
      : "--";
    if (elements.metricUptime) {
      elements.metricUptime.textContent = overallPct;
    }
  }

  /**
   * Render Active Incidents
   */
  function renderActiveIncidents(incidentsData) {
    const active = (incidentsData && incidentsData.incidents)
      ? incidentsData.incidents.filter((i) => i.status !== "resolved")
      : [];

    if (active.length === 0) {
      elements.activeIncidentsContainer.innerHTML = `
        <div class="card border-0 bg-white shadow-sm mb-4">
          <div class="card-body py-3 d-flex align-items-center text-muted">
            <svg class="text-success me-2 flex-shrink-0" width="20" height="20" fill="currentColor" viewBox="0 0 16 16">
              <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>
            </svg>
            <span class="small fw-medium">All services are operating normally. No active incidents reported.</span>
          </div>
        </div>
      `;
      return;
    }

    let html = `<div class="mb-4"><h5 class="fw-bold text-danger mb-3">Active Incidents (${active.length})</h5>`;
    active.forEach((inc) => {
      const updates = (inc.updates || []).map((u) => `
        <div class="timeline-item">
          <div class="timeline-marker"></div>
          <div class="small fw-semibold text-dark">${escapeHtml(u.status.toUpperCase())} &bull; <span class="text-muted fw-normal">${formatTimestamp(u.timestamp)}</span></div>
          <div class="small text-muted mt-1">${escapeHtml(u.message)}</div>
        </div>
      `).join("");

      html += `
        <div class="incident-card active">
          <div class="incident-header">
            <div>
              <span class="badge bg-danger text-uppercase me-2">${escapeHtml(inc.status)}</span>
              <strong class="text-dark">${escapeHtml(inc.monitor_name)}</strong>
            </div>
            <span class="small text-muted">Started: ${formatTimestamp(inc.started_at)}</span>
          </div>
          <div class="incident-body">
            <p class="text-dark mb-3">${escapeHtml(inc.error_description)}</p>
            <div class="incident-timeline">${updates}</div>
          </div>
        </div>
      `;
    });
    html += `</div>`;
    elements.activeIncidentsContainer.innerHTML = html;
  }

  /**
   * Render Monitors Grouped by Category with 30-Day Uptime Bars
   */
  function renderMonitors(monitors, summary) {
    if (!monitors || monitors.length === 0) {
      elements.monitorsContainer.innerHTML = `<div class="p-4 text-center text-muted">No monitors configured.</div>`;
      return;
    }

    const monitorsSummary = (summary && summary.monitors) || {};

    // Group monitors
    const groups = {};
    monitors.forEach((m) => {
      const g = m.group || "Default";
      if (!groups[g]) groups[g] = [];
      groups[g].push(m);
    });

    let html = "";
    Object.keys(groups).sort().forEach((grp) => {
      html += `<div class="mb-4">`;
      html += `<div class="group-header"><span>${escapeHtml(grp)}</span><span class="badge bg-light text-secondary border">${groups[grp].length} services</span></div>`;

      groups[grp].forEach((mon) => {
        const monStats = monitorsSummary[mon.id] || {};
        const dailyHistory = monStats.daily_history || [];
        const uptime30d = mon.uptime_30d !== null && mon.uptime_30d !== undefined
          ? `${mon.uptime_30d.toFixed(2)}%`
          : (monStats.uptime_30d !== null && monStats.uptime_30d !== undefined ? `${monStats.uptime_30d.toFixed(2)}%` : "--");

        // Status badge
        let statusBadgeClass = "up";
        let statusText = "Operational";
        if (mon.status === "DOWN") {
          statusBadgeClass = "down";
          statusText = mon.state === "pending_down" ? "Pending Outage" : "Down";
        } else if (mon.status === "DEGRADED" || mon.state === "degraded") {
          statusBadgeClass = "degraded";
          statusText = "Degraded";
        }

        // Response time badge
        const respTime = mon.response_time_ms ? `${Math.round(mon.response_time_ms)} ms` : "--";
        const statusCodeBadge = mon.http_status_code ? `HTTP ${mon.http_status_code}` : (mon.error_category ? mon.error_category : "--");

        // Build 30-day uptime bar segments
        let barSegmentsHtml = "";
        if (dailyHistory.length > 0) {
          dailyHistory.forEach((day) => {
            let cls = "status-nodata";
            if (day.status === "UP") cls = "status-up";
            else if (day.status === "DEGRADED") cls = "status-degraded";
            else if (day.status === "DOWN") cls = "status-down";

            const pctStr = day.uptime_percentage !== null ? `${day.uptime_percentage.toFixed(1)}%` : "No data";
            const tooltipTitle = `${day.date}: ${pctStr} (${day.successful_checks}/${day.total_checks} checks)`;

            barSegmentsHtml += `<div class="uptime-segment ${cls}" data-bs-toggle="tooltip" data-bs-placement="top" title="${escapeHtml(tooltipTitle)}"></div>`;
          });
        } else {
          // Fallback placeholder segments
          for (let i = 0; i < 30; i++) {
            barSegmentsHtml += `<div class="uptime-segment status-nodata" title="No history recorded"></div>`;
          }
        }

        html += `
          <div class="monitor-card shadow-sm">
            <div class="monitor-top">
              <div>
                <a href="${escapeHtml(mon.url)}" target="_blank" rel="noopener noreferrer" class="monitor-title">
                  ${escapeHtml(mon.name)}
                  <svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                </a>
              </div>
              <div class="monitor-meta">
                <span class="badge bg-light text-dark border">${escapeHtml(statusCodeBadge)}</span>
                <span>${respTime}</span>
                <span class="badge-status ${statusBadgeClass}">${statusText}</span>
              </div>
            </div>

            <div class="uptime-bar-container">
              <div class="uptime-bar">${barSegmentsHtml}</div>
              <div class="uptime-bar-header mt-1">
                <span>30 days ago</span>
                <span class="fw-semibold text-dark">${uptime30d} uptime</span>
                <span>Today</span>
              </div>
            </div>
          </div>
        `;
      });

      html += `</div>`;
    });

    elements.monitorsContainer.innerHTML = html;

    // Initialize Bootstrap tooltips
    if (window.bootstrap && window.bootstrap.Tooltip) {
      const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
      tooltipTriggerList.forEach((el) => new window.bootstrap.Tooltip(el));
    }
  }

  /**
   * Render Past Incidents
   */
  function renderPastIncidents(incidentsData) {
    const resolved = (incidentsData && incidentsData.incidents)
      ? incidentsData.incidents.filter((i) => i.status === "resolved").slice(0, 10)
      : [];

    if (resolved.length === 0) {
      elements.pastIncidentsContainer.innerHTML = `<div class="p-3 text-muted small bg-white border rounded">No past incidents recorded in the last 30 days.</div>`;
      return;
    }

    let html = "";
    resolved.forEach((inc) => {
      html += `
        <div class="border rounded p-3 mb-2 bg-white shadow-sm">
          <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-1">
            <strong class="text-dark">${escapeHtml(inc.monitor_name)}</strong>
            <span class="badge bg-success-subtle text-success border border-success-subtle">Resolved</span>
          </div>
          <div class="small text-muted mb-2">${escapeHtml(inc.error_description)}</div>
          <div class="small text-muted d-flex gap-3 flex-wrap">
            <span>Started: ${formatTimestamp(inc.started_at)}</span>
            <span>Resolved: ${formatTimestamp(inc.resolved_at)}</span>
            <span>Duration: ${formatDuration(inc.duration_seconds)}</span>
          </div>
        </div>
      `;
    });
    elements.pastIncidentsContainer.innerHTML = html;
  }

  /**
   * Load and refresh all status data
   */
  async function refreshData() {
    countdown = REFRESH_INTERVAL_SECONDS;
    if (elements.refreshCountdown) elements.refreshCountdown.textContent = `${countdown}s`;

    const result = await API.fetchAllStatus();
    const data = result.data;
    const latest = data.latest;
    const summary = data.summary;
    const incidents = data.incidents;

    if (!result.success) {
      elements.refreshAlert.classList.remove("d-none");
      elements.refreshAlert.innerHTML = `<strong>Data Refresh Notice:</strong> ${escapeHtml(result.error || "Unable to reach server")}. Showing cached monitoring data.`;
    } else {
      elements.refreshAlert.classList.add("d-none");
    }

    if (latest) {
      if (elements.lastUpdated) elements.lastUpdated.textContent = formatTimestamp(latest.generated_at);
      try { renderHeroBanner(latest, data.isStale, !result.success); } catch (e) { console.error("renderHeroBanner error:", e); }
      try { renderMetrics(latest, summary); } catch (e) { console.error("renderMetrics error:", e); }
      try { renderActiveIncidents(incidents); } catch (e) { console.error("renderActiveIncidents error:", e); }
      try { renderMonitors(latest.monitors, summary); } catch (e) { console.error("renderMonitors error:", e); }
      try { renderPastIncidents(incidents); } catch (e) { console.error("renderPastIncidents error:", e); }

      const chartsModule = window.StatusCharts || (typeof StatusCharts !== "undefined" ? StatusCharts : null);
      if (summary && summary.charts && chartsModule) {
        try { chartsModule.renderCharts(summary.charts, summary); } catch (e) { console.error("renderCharts error:", e); }
      }
    } else {
      try { renderHeroBanner(null, true, true); } catch (e) { console.error("renderHeroBanner error:", e); }
    }
  }

  // Setup Countdown Timer
  function startCountdown() {
    if (countdownTimer) clearInterval(countdownTimer);
    countdownTimer = setInterval(() => {
      countdown -= 1;
      if (elements.refreshCountdown) elements.refreshCountdown.textContent = `${countdown}s`;
      if (countdown <= 0) {
        refreshData();
      }
    }, 1000);
  }

  // Manual refresh button listener
  if (elements.btnRefresh) {
    elements.btnRefresh.addEventListener("click", () => {
      refreshData();
    });
  }

  // Initial load
  refreshData();
  startCountdown();
});
