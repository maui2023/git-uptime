/**
 * Chart.js visualization module for Sabily Uptime Monitor.
 * Renders Response Time (24h), System Uptime % (30d), and Incident Frequency (30d).
 */

const StatusCharts = (() => {
  let responseChart = null;
  let availabilityChart = null;
  let incidentChart = null;

  const THEME = {
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    gridColor: "#f1f5f9",
    tickColor: "#94a3b8",
    blue: "#0284c7",
    blueLight: "rgba(2, 132, 199, 0.08)",
    green: "#10b981",
    greenLight: "rgba(16, 185, 129, 0.15)",
    amber: "#f59e0b",
    red: "#ef4444",
    slotBg: "rgba(226, 232, 240, 0.55)",
  };

  /**
   * Helper to format hour labels in local time from ISO or UTC datetime string
   */
  function formatLocalHour(item) {
    if (!item) return "";
    try {
      if (item.iso) {
        return new Date(item.iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
      }
      if (item.datetime) {
        const iso = (!item.datetime.endsWith("Z") && !item.datetime.includes("+"))
          ? item.datetime.replace(" ", "T") + ":00Z"
          : item.datetime;
        return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
      }
    } catch (_) {}
    return item.time || "";
  }

  /**
   * Helper to format MM/DD date label
   */
  function formatDateLabel(dateStr) {
    if (!dateStr) return "";
    const parts = dateStr.split("-");
    return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : dateStr;
  }

  /**
   * Initialize or update all charts with real summary data
   */
  function renderCharts(chartsData, summaryStats) {
    if (!chartsData) return;
    if (typeof Chart === "undefined") {
      console.warn("Chart.js library not detected. Skipping chart rendering.");
      return;
    }

    renderResponseTimeChart(chartsData.response_time_24h || []);
    renderAvailabilityChart(chartsData.availability_30d || [], summaryStats);
    renderIncidentChart(chartsData.incident_frequency_30d || []);
  }

  /**
   * Render Response Time (Last 24 Hours)
   */
  function renderResponseTimeChart(series) {
    const ctx = document.getElementById("chart-response-time");
    if (!ctx) return;

    const badgeEl = document.getElementById("badge-response-time");
    const emptyEl = document.getElementById("empty-response-time");

    const validPoints = series.filter(
      (s) => s && s.avg_ms !== null && s.avg_ms !== undefined && !isNaN(s.avg_ms)
    );

    // Update Header Badge and Empty State Indicator
    if (validPoints.length > 0) {
      const avg = Math.round(validPoints.reduce((acc, c) => acc + c.avg_ms, 0) / validPoints.length);
      const latest = Math.round(validPoints[validPoints.length - 1].avg_ms);
      if (badgeEl) {
        badgeEl.textContent = `Avg: ${avg} ms · Latest: ${latest} ms`;
        badgeEl.className = "badge bg-primary-subtle text-primary border border-primary-subtle ms-2";
        badgeEl.classList.remove("d-none");
      }
      if (emptyEl) emptyEl.classList.add("d-none");
    } else {
      if (badgeEl) {
        badgeEl.textContent = "No 24h Data";
        badgeEl.className = "badge bg-light text-secondary border ms-2";
        badgeEl.classList.remove("d-none");
      }
      if (emptyEl) {
        emptyEl.textContent = "No latency telemetry recorded in the last 24 hours. Waiting for next cycle.";
        emptyEl.classList.remove("d-none");
      }
    }

    const labels = series.map((s) => formatLocalHour(s));
    const dataPoints = series.map((s) => (s ? s.avg_ms : null));

    if (responseChart) {
      responseChart.data.labels = labels;
      responseChart.data.datasets[0].data = dataPoints;
      responseChart.update();
      return;
    }

    responseChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Average Response Time (ms)",
            data: dataPoints,
            borderColor: THEME.blue,
            backgroundColor: THEME.blueLight,
            fill: true,
            tension: 0.3,
            borderWidth: 2,
            pointRadius: (context) => (context.raw !== null && context.raw !== undefined ? 3.5 : 0),
            pointHoverRadius: 6,
            pointBackgroundColor: THEME.blue,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => {
                const idx = items[0]?.dataIndex;
                const s = series[idx];
                const hourFormatted = labels[idx];
                return s?.datetime ? `${s.datetime} (${hourFormatted} Local)` : hourFormatted;
              },
              label: (ctx) => {
                const val = ctx.parsed.y;
                return val !== null && !isNaN(val) ? `${val} ms average latency` : "No checks recorded";
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: THEME.gridColor },
            ticks: {
              color: THEME.tickColor,
              maxTicksLimit: 12,
              font: { family: THEME.fontFamily },
            },
          },
          y: {
            beginAtZero: true,
            suggestedMax: 500,
            grid: { color: THEME.gridColor },
            ticks: {
              color: THEME.tickColor,
              callback: (val) => `${val} ms`,
              font: { family: THEME.fontFamily },
            },
          },
        },
      },
    });
  }

  /**
   * Render System Uptime % (Last 30 Days)
   */
  function renderAvailabilityChart(series, summaryStats) {
    const ctx = document.getElementById("chart-availability");
    if (!ctx) return;

    const badgeEl = document.getElementById("badge-availability");
    const emptyEl = document.getElementById("empty-availability");

    const validDays = series.filter(
      (s) => s && s.uptime_percentage !== null && s.uptime_percentage !== undefined && !isNaN(s.uptime_percentage)
    );

    // Compute or retrieve 30-day overall uptime
    let overallPct = summaryStats && summaryStats.overall_uptime_30d !== null && summaryStats.overall_uptime_30d !== undefined
      ? summaryStats.overall_uptime_30d
      : null;

    if (overallPct === null && validDays.length > 0) {
      overallPct = validDays.reduce((acc, c) => acc + c.uptime_percentage, 0) / validDays.length;
    }

    if (badgeEl) {
      if (overallPct !== null) {
        badgeEl.textContent = `${overallPct.toFixed(2)}% Uptime`;
        if (overallPct >= 99) {
          badgeEl.className = "badge bg-success-subtle text-success border border-success-subtle ms-2";
        } else if (overallPct >= 95) {
          badgeEl.className = "badge bg-warning-subtle text-warning border border-warning-subtle ms-2";
        } else {
          badgeEl.className = "badge bg-danger-subtle text-danger border border-danger-subtle ms-2";
        }
        badgeEl.classList.remove("d-none");
      } else {
        badgeEl.textContent = "No Data";
        badgeEl.className = "badge bg-light text-secondary border ms-2";
        badgeEl.classList.remove("d-none");
      }
    }

    if (emptyEl) {
      if (validDays.length === 0) {
        emptyEl.textContent = "No uptime history recorded yet.";
        emptyEl.classList.remove("d-none");
      } else {
        emptyEl.classList.add("d-none");
      }
    }

    const labels = series.map((s) => formatDateLabel(s?.date));
    const dataPoints = series.map((s) => s?.uptime_percentage ?? null);
    const backgroundSlotPoints = series.map(() => 100);

    const barColors = series.map((s) => {
      const pct = s?.uptime_percentage;
      if (pct === null || pct === undefined || isNaN(pct)) return "transparent";
      if (pct >= 99) return THEME.green;
      if (pct >= 95) return THEME.amber;
      return THEME.red;
    });

    if (availabilityChart) {
      availabilityChart.data.labels = labels;
      availabilityChart.data.datasets[0].data = backgroundSlotPoints;
      availabilityChart.data.datasets[1].data = dataPoints;
      availabilityChart.data.datasets[1].backgroundColor = barColors;
      availabilityChart.update();
      return;
    }

    availabilityChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Slot",
            data: backgroundSlotPoints,
            backgroundColor: THEME.slotBg,
            borderRadius: 3,
            maxBarThickness: 16,
            grouped: false,
            order: 2,
          },
          {
            label: "Uptime %",
            data: dataPoints,
            backgroundColor: barColors,
            borderRadius: 3,
            maxBarThickness: 16,
            grouped: false,
            order: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => {
                const idx = items[0]?.dataIndex;
                const s = series[idx];
                return s?.date || items[0]?.label;
              },
              label: (ctx) => {
                if (ctx.datasetIndex === 0) return null; // Ignore background slot in tooltip
                const val = ctx.parsed.y;
                if (val !== null && val !== undefined && !isNaN(val)) {
                  return `Availability: ${val.toFixed(2)}%`;
                }
                return "No checks recorded (before launch)";
              },
            },
            filter: (item) => item.datasetIndex === 1,
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: THEME.tickColor,
              maxTicksLimit: 15,
              font: { family: THEME.fontFamily },
            },
          },
          y: {
            suggestedMin: 90,
            max: 100,
            grid: { color: THEME.gridColor },
            ticks: {
              color: THEME.tickColor,
              callback: (val) => `${val}%`,
              font: { family: THEME.fontFamily },
            },
          },
        },
      },
    });
  }

  /**
   * Render Incident Frequency (Last 30 Days)
   */
  function renderIncidentChart(series) {
    const ctx = document.getElementById("chart-incidents");
    if (!ctx) return;

    const badgeEl = document.getElementById("badge-incidents");
    const emptyEl = document.getElementById("empty-incidents");

    const totalIncidents = series.reduce((acc, c) => acc + (c && c.count ? c.count : 0), 0);

    if (badgeEl) {
      if (totalIncidents === 0) {
        badgeEl.textContent = "0 Incidents · 100% Operational";
        badgeEl.className = "badge bg-success-subtle text-success border border-success-subtle ms-2";
      } else {
        badgeEl.textContent = `${totalIncidents} Incident(s)`;
        badgeEl.className = "badge bg-danger-subtle text-danger border border-danger-subtle ms-2";
      }
      badgeEl.classList.remove("d-none");
    }

    if (emptyEl) {
      if (totalIncidents === 0) {
        emptyEl.innerHTML = `<span class="text-success fw-bold me-1">✓</span> 0 incidents recorded in the last 30 days · All systems operational`;
        emptyEl.classList.remove("d-none");
      } else {
        emptyEl.classList.add("d-none");
      }
    }

    const labels = series.map((s) => formatDateLabel(s?.date));
    const dataPoints = series.map((s) => (s && s.count ? s.count : 0));
    const baselinePoints = series.map(() => 0.15);
    const barColors = series.map((s) => (s && s.count > 0 ? THEME.red : "transparent"));

    if (incidentChart) {
      incidentChart.data.labels = labels;
      incidentChart.data.datasets[0].data = baselinePoints;
      incidentChart.data.datasets[1].data = dataPoints;
      incidentChart.data.datasets[1].backgroundColor = barColors;
      incidentChart.update();
      return;
    }

    incidentChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Baseline",
            data: baselinePoints,
            backgroundColor: THEME.slotBg,
            borderRadius: 2,
            maxBarThickness: 14,
            grouped: false,
            order: 2,
          },
          {
            label: "Incidents",
            data: dataPoints,
            backgroundColor: barColors,
            borderRadius: 3,
            maxBarThickness: 16,
            grouped: false,
            order: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => {
                const idx = items[0]?.dataIndex;
                const s = series[idx];
                return s?.date || items[0]?.label;
              },
              label: (ctx) => {
                if (ctx.datasetIndex === 0) return null;
                const count = ctx.parsed.y || 0;
                return count === 0 ? "0 incidents (Normal operations)" : `${count} incident(s) recorded`;
              },
            },
            filter: (item) => item.datasetIndex === 1,
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: THEME.tickColor,
              maxTicksLimit: 15,
              font: { family: THEME.fontFamily },
            },
          },
          y: {
            beginAtZero: true,
            suggestedMax: 3,
            ticks: {
              stepSize: 1,
              precision: 0,
              color: THEME.tickColor,
              font: { family: THEME.fontFamily },
            },
            grid: { color: THEME.gridColor },
          },
        },
      },
    });
  }

  const moduleInstance = {
    renderCharts,
  };

  // Expose to window for browser script compatibility
  if (typeof window !== "undefined") {
    window.StatusCharts = moduleInstance;
  }

  return moduleInstance;
})();
