/**
 * API client module for Sabily Uptime Monitor.
 * Handles fetching JSON datasets with cache-busting, fallback handling,
 * and stale data detection.
 */

const API = (() => {
  // Configurable raw repo URL for live updates without requiring GitHub Pages redeployment
  const GITHUB_RAW_URL = "https://raw.githubusercontent.com/maui2023/git-uptime/main/public/data";
  const LOCAL_DATA_URL = "./data";

  // Determine active base URL: prefer local relative path if served locally or if pages path works,
  // otherwise fallback to raw GitHub user content.
  let activeBaseUrl = LOCAL_DATA_URL;

  // Cached state to preserve display if a network failure occurs
  let cachedData = {
    latest: null,
    summary: null,
    incidents: null,
    lastFetchedAt: null,
    isStale: false,
    fetchError: null,
  };

  /**
   * Set custom data source URL (e.g. from UI or settings)
   */
  function setBaseUrl(url) {
    activeBaseUrl = url.replace(/\/+$/, "");
  }

  /**
   * Fetch a single JSON endpoint with cache busting
   */
  async function fetchEndpoint(endpoint) {
    const timestamp = Date.now();
    const primaryUrl = `${activeBaseUrl}/${endpoint}?_t=${timestamp}`;

    try {
      const response = await fetch(primaryUrl, { cache: "no-cache" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} fetching ${primaryUrl}`);
      }
      return await response.json();
    } catch (primaryErr) {
      // If primary failed and was local, try GitHub raw URL fallback
      if (activeBaseUrl !== GITHUB_RAW_URL) {
        try {
          const fallbackUrl = `${GITHUB_RAW_URL}/${endpoint}?_t=${timestamp}`;
          const fallbackResp = await fetch(fallbackUrl, { cache: "no-cache" });
          if (fallbackResp.ok) {
            return await fallbackResp.json();
          }
        } catch (_) {
          // Ignore fallback error and throw primary error
        }
      }
      throw primaryErr;
    }
  }

  /**
   * Check if monitoring data timestamp is older than 15 minutes
   */
  function checkIsStale(isoTimestamp, maxMinutes = 15) {
    if (!isoTimestamp) return true;
    try {
      const generatedTime = new Date(isoTimestamp).getTime();
      const now = Date.now();
      const diffMinutes = (now - generatedTime) / (1000 * 60);
      return diffMinutes > maxMinutes;
    } catch (e) {
      return true;
    }
  }

  /**
   * Fetch all monitoring datasets concurrently
   */
  async function fetchAllStatus() {
    try {
      const [latest, summary, incidents] = await Promise.all([
        fetchEndpoint("latest.json"),
        fetchEndpoint("uptime-summary.json"),
        fetchEndpoint("incidents.json"),
      ]);

      const isStale = checkIsStale(latest.generated_at, 15);

      cachedData = {
        latest,
        summary,
        incidents,
        lastFetchedAt: new Date(),
        isStale,
        fetchError: null,
      };

      return {
        success: true,
        data: cachedData,
      };
    } catch (err) {
      // Retain last valid data if available
      cachedData.fetchError = err.message || "Failed to fetch status data";
      return {
        success: false,
        error: err.message,
        data: cachedData,
      };
    }
  }

  return {
    fetchAllStatus,
    setBaseUrl,
    getCachedData: () => cachedData,
    checkIsStale,
  };
})();
