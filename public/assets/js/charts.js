/**
 * Chart.js visualization module for Sabily Uptime Monitor.
 * Renders Response Time (24h), Uptime History (30d), and Incident Frequency.
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
  };

  /**
   * Initialize or update all charts with real summary data
   */
  function renderCharts(chartsData) {
    if (!chartsData) return;

    renderResponseTimeChart(chartsData.response_time_24h || []);
    renderAvailabilityChart(chartsData.availability_30d || []);
    renderIncidentChart(chartsData.incident_frequency_30d || []);
  }

  function renderResponseTimeChart(series) {
    const ctx = document.getElementById("chart-response-time");
    if (!ctx) return;

    const labels = series.map((s) => s.time);
    const dataPoints = series.map((s) => s.avg_ms);

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
            pointRadius: 2,
            pointHoverRadius: 5,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.parsed.y !== null ? ctx.parsed.y : "--"} ms`,
            },
          },
        },
        scales: {
          x: {
            grid: { color: THEME.gridColor },
            ticks: { color: THEME.tickColor, maxTicksLimit: 12, font: { family: THEME.fontFamily } },
          },
          y: {
            beginAtZero: true,
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

  function renderAvailabilityChart(series) {
    const ctx = document.getElementById("chart-availability");
    if (!ctx) return;

    const labels = series.map((s) => {
      const parts = (s && s.date) ? s.date.split("-") : [];
      return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : (s?.date || "");
    });
    const dataPoints = series.map((s) => s.uptime_percentage);

    if (availabilityChart) {
      availabilityChart.data.labels = labels;
      availabilityChart.data.datasets[0].data = dataPoints;
      availabilityChart.update();
      return;
    }

    availabilityChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Uptime %",
            data: dataPoints,
            backgroundColor: THEME.green,
            borderRadius: 3,
            maxBarThickness: 18,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.parsed.y !== null ? ctx.parsed.y : "--"}% uptime`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: THEME.tickColor, maxTicksLimit: 15, font: { family: THEME.fontFamily } },
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

  function renderIncidentChart(series) {
    const ctx = document.getElementById("chart-incidents");
    if (!ctx) return;

    const labels = series.map((s) => {
      const parts = (s && s.date) ? s.date.split("-") : [];
      return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : (s?.date || "");
    });
    const dataPoints = series.map((s) => s.count);

    if (incidentChart) {
      incidentChart.data.labels = labels;
      incidentChart.data.datasets[0].data = dataPoints;
      incidentChart.update();
      return;
    }

    incidentChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Incidents",
            data: dataPoints,
            backgroundColor: THEME.amber,
            borderRadius: 3,
            maxBarThickness: 16,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.parsed.y} incident(s)`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: THEME.tickColor, maxTicksLimit: 15, font: { family: THEME.fontFamily } },
          },
          y: {
            beginAtZero: true,
            ticks: {
              stepSize: 1,
              color: THEME.tickColor,
              font: { family: THEME.fontFamily },
            },
            grid: { color: THEME.gridColor },
          },
        },
      },
    });
  }

  return {
    renderCharts,
  };
})();
