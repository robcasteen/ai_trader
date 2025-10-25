// Dashboard JavaScript - Dark Theme Compatible
// Place this file at: src/static/js/dashboard.js

// State management
const State = {
  time: null,
  message: null,
  next: null,
  isRunning: false,
};
async function toggleFeed(feedId) {
  try {
    const response = await fetch(`/api/feeds/${feedId}/toggle`, {
      method: "PUT",
    });

    if (response.ok) {
      await loadFeedsDetailed();
      showTab("feeds"); // Stay on feeds tab
    } else {
      alert("Failed to toggle feed");
    }
  } catch (error) {
    console.error("Error toggling feed:", error);
    alert("Error: " + error.message);
  }
}

async function deleteFeed(feedId) {
  if (!confirm("Are you sure you want to delete this feed?")) {
    return;
  }

  try {
    const response = await fetch(`/api/feeds/${feedId}`, {
      method: "DELETE",
    });

    if (response.ok) {
      await loadFeedsDetailed();
      showTab("feeds"); // Stay on feeds tab
    } else {
      alert("Failed to delete feed");
    }
  } catch (error) {
    console.error("Error deleting feed:", error);
    alert("Error: " + error.message);
  }
}
// Format price for terminal display
function formatPrice(price) {
  return (
    "$" +
    parseFloat(price).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

// Format time with date for terminal display
function formatTimeShort(timestamp) {
  const date = new Date(timestamp);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${month}/${day} ${hours}:${minutes}`;
}

// Utility: Format time with relative display
function formatTime(dateStr) {
  if (!dateStr) return "N/A";
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;

    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

// Utility: Calculate countdown to next run
function updateCountdown() {
  const countdownEl = document.getElementById("countdown");
  if (!countdownEl || !State.next) {
    if (countdownEl) countdownEl.textContent = "";
    return;
  }

  try {
    const next = new Date(State.next);
    const now = new Date();
    const diff = next - now;

    if (diff <= 0) {
      countdownEl.textContent = "Running soon...";
      return;
    }

    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    countdownEl.textContent = `in ${minutes}m ${seconds}s`;
  } catch (e) {
    countdownEl.textContent = "";
  }
}

// Render: Bot status section
function renderStatus() {
  const lastRunEl = document.getElementById("lastRun");
  const lastMessageEl = document.getElementById("lastMessage");
  const nextRunEl = document.getElementById("nextRun");
  const dotEl = document.getElementById("statusDot");

  if (lastRunEl) {
    lastRunEl.innerHTML = `
      <span class="text-gray-500">Last run:</span> 
      <span class="text-white font-semibold">${formatTime(State.time)}</span>
    `;
  }

  if (lastMessageEl) {
    lastMessageEl.textContent = State.message || "Waiting for first run...";
  }

  if (nextRunEl) {
    nextRunEl.textContent = State.next ? formatTime(State.next) : "...";
  }

  if (dotEl) {
    if (State.isRunning) {
      dotEl.className = "status-dot status-active pulse-green";
    } else if (State.time) {
      dotEl.className = "status-dot status-active";
    } else {
      dotEl.className = "status-dot status-idle";
    }
  }
}

// API: Refresh status from server
async function refreshStatus() {
  try {
    const resp = await fetch("/status");
    if (!resp.ok) throw new Error("Bad response");
    const data = await resp.json();

    const last = data.last_status || {};
    if (last.time) State.time = last.time;
    if (last.message) State.message = last.message;
    if (data.next_run) State.next = data.next_run;

    renderStatus();
  } catch (err) {
    console.warn("Failed to refresh status:", err);
  }
}

// API: Trigger manual run
async function runNow() {
  const btn = document.getElementById("runNowBtn");
  if (!btn) return;

  btn.disabled = true;
  btn.innerHTML = '<span class="animate-spin">⏳</span> Running...';
  State.isRunning = true;
  renderStatus();

  try {
    const resp = await fetch("/run-now");
    const data = await resp.json();

    if (data.last_status) {
      if (data.last_status.time) State.time = data.last_status.time;
      if (data.last_status.message) State.message = data.last_status.message;
    }
    if (data.next_run) State.next = data.next_run;

    await refreshSummary();
    refreshData();
  } catch (err) {
    console.error("[RunNow] Error:", err);
  } finally {
    State.isRunning = false;
    btn.disabled = false;
    btn.innerHTML = "<span>🚀</span><span>Run Now</span>";
    renderStatus();
  }
}

/// Chart: PnL visualization (optimized to prevent flashing)
let pnlChart = null;

function initPnLChart(labels, values) {
  const ctx = document.getElementById("pnlChart");
  if (!ctx) return;

  // Check if data actually changed
  if (
    pnlChart &&
    JSON.stringify(pnlChart.data.labels) === JSON.stringify(labels) &&
    JSON.stringify(pnlChart.data.datasets[0].data) === JSON.stringify(values)
  ) {
    return; // Don't update if data hasn't changed
  }

  if (pnlChart) {
    // Update existing chart instead of destroying
    pnlChart.data.labels = labels || [];
    pnlChart.data.datasets[0].data = values || [];
    pnlChart.data.datasets[0].backgroundColor = (values || []).map((v) =>
      v >= 0 ? "rgba(16, 185, 129, 0.7)" : "rgba(239, 68, 68, 0.7)"
    );
    pnlChart.data.datasets[0].borderColor = (values || []).map((v) =>
      v >= 0 ? "rgb(16, 185, 129)" : "rgb(239, 68, 68)"
    );
    pnlChart.update("none"); // Update without animation to prevent flash
    return;
  }

  // Create new chart only if it doesn't exist
  pnlChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels || [],
      datasets: [
        {
          label: "PnL ($)",
          data: values || [],
          backgroundColor: (values || []).map((v) =>
            v >= 0 ? "rgba(16, 185, 129, 0.7)" : "rgba(239, 68, 68, 0.7)"
          ),
          borderColor: (values || []).map((v) =>
            v >= 0 ? "rgb(16, 185, 129)" : "rgb(239, 68, 68)"
          ),
          borderWidth: 2,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false, // Disable animations to prevent flashing
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(30, 41, 59, 0.95)",
          titleColor: "#fff",
          bodyColor: "#e2e8f0",
          borderColor: "#475569",
          borderWidth: 1,
          callbacks: {
            label: (ctx) => {
              const val = ctx.parsed.y;
              return (val >= 0 ? "+" : "") + "$" + val.toFixed(2);
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: "#94a3b8", font: { size: 11 } },
        },
        y: {
          beginAtZero: true,
          grid: { color: "#334155" },
          ticks: {
            color: "#94a3b8",
            callback: (value) => "$" + value,
          },
        },
      },
    },
  });
}

// Render: Symbols performance table
function renderSymbolsTable(summary) {
  const container = document.getElementById("symbolsTable");
  if (!container) return;

  const symbols = summary?.symbols || {};
  const keys = Object.keys(symbols);

  if (!keys.length) {
    container.innerHTML =
      '<p class="text-gray-500 text-center py-8">No trading activity yet</p>';
    return;
  }

  const rows = keys
    .map((sym) => {
      const d = symbols[sym];
      const pnl = Number(d.pnl || 0);
      const pnlCls = pnl >= 0 ? "text-green-400" : "text-red-400";
      const pnlIcon = pnl >= 0 ? "↗" : "↘";
      const action = (d.last_action || "").toLowerCase();
      const badgeClass =
        action === "buy"
          ? "signal-buy"
          : action === "sell"
          ? "signal-sell"
          : "signal-hold";

      return `
      <tr class="border-b border-gray-700 hover:bg-slate-800/50 transition-colors">
        <td class="px-4 py-3 font-semibold text-white">${sym}</td>
        <td class="px-4 py-3">
          <span class="signal-badge ${badgeClass}">${(
        d.last_action || "N/A"
      ).toUpperCase()}</span>
        </td>
        <td class="px-4 py-3 text-gray-300">${
          d.last_price ? "$" + d.last_price.toLocaleString() : "-"
        }</td>
        <td class="px-4 py-3 ${pnlCls} font-bold">${pnlIcon} $${Math.abs(
        pnl
      ).toFixed(2)}</td>
      </tr>
    `;
    })
    .join("");

  container.innerHTML = `
    <table class="min-w-full">
      <thead class="bg-slate-800/50">
        <tr>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-400">Symbol</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-400">Action</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-400">Price</th>
          <th class="px-4 py-3 text-left text-xs font-semibold uppercase text-gray-400">PnL</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// Render: AI sentiment signals
function renderSentiment(sentiment) {
  const container = document.getElementById("sentimentContainer");
  if (!container) return;

  const keys = Object.keys(sentiment || {});

  if (!keys.length) {
    container.innerHTML =
      '<p class="text-gray-500 text-center py-4">No AI signals yet</p>';
    return;
  }

  const signalConfig = {
    BUY: {
      bg: "bg-green-900/30",
      border: "border-green-600",
      text: "text-green-400",
      icon: "📈",
    },
    SELL: {
      bg: "bg-red-900/30",
      border: "border-red-600",
      text: "text-red-400",
      icon: "📉",
    },
    HOLD: {
      bg: "bg-yellow-900/30",
      border: "border-yellow-600",
      text: "text-yellow-400",
      icon: "⏸️",
    },
  };

  const cards = keys
    .map((sym) => {
      const s = sentiment[sym];
      const sig = (s.signal || "HOLD").toUpperCase();
      const config = signalConfig[sig] || signalConfig["HOLD"];

      return `
      <div class="${config.bg} border-l-4 ${
        config.border
      } p-4 rounded-r-lg hover:bg-opacity-50 transition-all">
        <div class="flex items-start justify-between mb-2">
          <div class="font-bold text-white text-lg">${sym}</div>
          <div class="${config.text} text-2xl">${config.icon}</div>
        </div>
        <div class="${config.text} font-semibold text-xl mb-2">${sig}</div>
        <div class="text-gray-400 text-sm leading-relaxed">${
          s.reason || "No reason provided"
        }</div>
        ${
          s.updated_at
            ? `
          <div class="text-gray-600 text-xs mt-3 flex items-center gap-1">
            <span>🕒</span>
            <span>${formatTime(s.updated_at)}</span>
          </div>
        `
            : ""
        }
      </div>
    `;
    })
    .join("");

  container.innerHTML = cards;
}

// Render: Recent trading activity
function renderRecentTrades(trades) {
  const container = document.getElementById("recentTrades");
  if (!container) return;

  if (!trades || !trades.length) {
    container.innerHTML =
      '<p class="text-gray-500 text-center py-4">No recent activity</p>';
    return;
  }

  const actionConfig = {
    buy: { bg: "bg-green-900/20", text: "text-green-400", icon: "🟢" },
    sell: { bg: "bg-red-900/20", text: "text-red-400", icon: "🔴" },
    hold: { bg: "bg-yellow-900/20", text: "text-yellow-400", icon: "🟡" },
  };

  const items = trades
    .slice(-10)
    .reverse()
    .map((t) => {
      const action = (t.action || "").toLowerCase();
      const config = actionConfig[action] || {
        bg: "bg-gray-800",
        text: "text-gray-400",
        icon: "⚪",
      };

      return `
      <div class="${
        config.bg
      } rounded-lg p-3 hover:bg-opacity-70 transition-all border border-gray-700">
        <div class="flex items-center justify-between mb-1">
          <span class="font-semibold text-white text-sm">${
            t.symbol || "Unknown"
          }</span>
          <span class="${
            config.text
          } font-bold text-xs flex items-center gap-1">
            <span>${config.icon}</span>
            <span>${(t.action || "N/A").toUpperCase()}</span>
          </span>
        </div>
        <div class="text-xs text-gray-400 flex justify-between">
          <span>${t.amount || 0} @ $${(t.price || 0).toLocaleString()}</span>
          <span class="text-gray-600">${formatTime(t.timestamp)}</span>
        </div>
      </div>
    `;
    })
    .join("");

  container.innerHTML = items;
}

// API: Refresh all dashboard data

// API: Refresh balance data
async function refreshBalance() {
  try {
    const resp = await fetch("/api/balance");
    if (!resp.ok) throw new Error("Balance fetch failed");
    const data = await resp.json();

    // Update balance display
    const balanceEl = document.getElementById("balance");
    if (balanceEl) {
      balanceEl.textContent =
        "$" +
        (data.total || 0).toLocaleString("en-US", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
    }

    // Update P&L display
    const pnlEl = document.getElementById("pnl-today");
    if (pnlEl) {
      const pnl = data.pnl || 0;
      const pnlFormatted =
        (pnl >= 0 ? "+" : "") +
        "$" +
        Math.abs(pnl).toLocaleString("en-US", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      pnlEl.textContent = pnlFormatted;
    }
  } catch (err) {
    console.error("Failed to refresh balance:", err);
  }
}

async function refreshSummary() {
  try {
    const resp = await fetch("/partial");
    if (!resp.ok) throw new Error("Network error");
    const data = await resp.json();

    // Update metric counters
    const updates = {
      totalTrades: data.summary?.total_trades || 0,
      buyCount: data.summary?.buy_count || 0,
      sellCount: data.summary?.sell_count || 0,
      holdCount: data.summary?.hold_count || 0,
    };

    Object.entries(updates).forEach(([id, value]) => {
      const el = document.getElementById(id);
      if (el) el.textContent = value;
    });

    // Update visualizations
    if (data.labels && data.pnl_data) {
      initPnLChart(data.labels, data.pnl_data);
    }

    renderSymbolsTable(data.summary);
    renderSentiment(data.sentiment);
    renderRecentTrades(data.trades);
  } catch (err) {
    console.error("Failed to refresh summary:", err);
  }
}

// Event: Manual refresh button
function setupRefreshButton() {
  const refreshBtn = document.getElementById("refreshBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      refreshStatus();
      refreshBalance();
      refreshSummary();
      refreshData();
    });
  }
}

// Event: Run now button
function setupRunNowButton() {
  const runNowBtn = document.getElementById("runNowBtn");
  if (runNowBtn) {
    runNowBtn.addEventListener("click", runNow);
  }
}

// Initialize dashboard
function initDashboard() {
  console.log("🚀 Initializing dashboard...");

  // Setup event listeners
  setupRunNowButton();
  setupRefreshButton();

  // Initial data load
  refreshStatus();
  refreshSummary();
  refreshData();

  // Auto-refresh intervals
  setInterval(refreshSummary, 5000); // Refresh data every 5 seconds
  setInterval(refreshBalance, 5000);
  setInterval(refreshStatus, 5000); // Refresh status every 5 seconds
  setInterval(updateCountdown, 1000); // Update countdown every second

  console.log("✅ Dashboard initialized");
}

// Start when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initDashboard);
} else {
  // Don't auto-init during tests
  if (typeof process === "undefined" || process.env.NODE_ENV !== "test") {
    initDashboard();
  }
}

// Add these functions to the END of src/static/js/dashboard.js

// ============================================
// FEED MANAGEMENT FUNCTIONS
// ============================================

// Load detailed feed information
// Replace the loadFeedsDetailed function in src/static/js/dashboard.js with this version:

async function loadFeedsDetailed() {
  try {
    const response = await fetch("/api/feeds");
    const data = await response.json();

    const feeds = data.feeds || [];
    const feedCountEl = document.getElementById("feed-count");
    if (feedCountEl) {
      feedCountEl.textContent = feeds.length;
    }

    const tbody = document.getElementById("feed-list-detailed");
    if (!tbody) {
      console.warn("feed-list-detailed element not found");
      return;
    }

    if (feeds.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="7" style="text-align: center; padding: 20px; color: #ffaa00;">No feeds configured. Click + ADD FEED to get started.</td></tr>';
      return;
    }

    const feedsHtml = feeds
      .map((feed) => {
        const statusClass = feed.status === "active" ? "positive" : "negative";
        const statusText = (feed.status || "active").toUpperCase();
        const lastFetch = feed.last_fetch
          ? new Date(feed.last_fetch).toLocaleString()
          : "--";

        return `
        <tr>
          <td>${feed.name || "Unknown"}</td>
          <td style="text-align: center;">
            <span class="${statusClass}">●</span> ${statusText}
          </td>
          <td style="text-align: center;">${feed.headlines_count || 0}</td>
          <td style="text-align: center;">${feed.relevant_count || 0}</td>
          <td class="timestamp">${lastFetch}</td>
          <td style="font-size: 9px; max-width: 300px; overflow: hidden; text-overflow: ellipsis;">${
            feed.url || "--"
          }</td>
<td style="text-align: center;">
            <div style="display: flex; gap: 4px; justify-content: center; flex-wrap: wrap;">
<button class="btn" onclick="testFeed(${
          feed.id
        })" style="padding: 2px 6px; font-size: 9px;">TEST</button>
              <button class="btn" onclick="editFeed(${
                feed.id
              })" style="padding: 2px 6px; font-size: 9px;">EDIT</button>
              <button class="btn" onclick="toggleFeed(${
                feed.id
              })" style="padding: 2px 6px; font-size: 9px; border-color: ${
          feed.active === false ? "#888" : "#00ff00"
        }; color: ${feed.active === false ? "#888" : "#00ff00"};">${
          feed.active === false ? "ON" : "OFF"
        }</button>
              <button class="btn" onclick="deleteFeed(${
                feed.id
              })" style="padding: 2px 6px; font-size: 9px; border-color: #ff0000; color: #ff0000;">DEL</button>
            </div>
          </td>
        </tr>
      `;
      })
      .join("");

    tbody.innerHTML = feedsHtml;
    console.log("✅ Feeds loaded successfully:", feeds.length);
  } catch (error) {
    console.error("Error loading feeds:", error);
    const tbody = document.getElementById("feed-list-detailed");
    if (tbody) {
      tbody.innerHTML =
        '<tr><td colspan="7" style="text-align: center; padding: 20px; color: #ff0000;">Error loading feeds: ' +
        error.message +
        "</td></tr>";
    }
  }
}

// Show add feed modal
function showAddFeedModal() {
  const modal = document.getElementById("add-feed-modal");
  if (modal) {
    modal.style.display = "flex";
  }
}

// Close add feed modal
function closeAddFeedModal() {
  const modal = document.getElementById("add-feed-modal");
  if (modal) {
    modal.style.display = "none";
  }

  // Clear inputs
  const nameInput = document.getElementById("new-feed-name");
  const urlInput = document.getElementById("new-feed-url");
  if (nameInput) nameInput.value = "";
  if (urlInput) urlInput.value = "";
}

// Add new RSS feed
async function addNewFeed() {
  const nameInput = document.getElementById("new-feed-name");
  const urlInput = document.getElementById("new-feed-url");

  if (!urlInput) {
    console.error("Feed URL input not found");
    return;
  }

  const name = nameInput ? nameInput.value.trim() : "";
  const url = urlInput.value.trim();

  if (!url) {
    alert("⚠️ URL is required");
    return;
  }

  try {
    const response = await fetch("/api/feeds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name || url, url: url }),
    });

    const data = await response.json();

    if (response.ok && data.status === "success") {
      alert("✅ Feed added successfully: " + (name || url));
      closeAddFeedModal();
      loadFeedsDetailed();
    } else {
      alert("❌ Error adding feed: " + (data.error || "Unknown error"));
    }
  } catch (error) {
    console.error("Failed to add feed:", error);
    alert("❌ Network error: " + error.message);
  }
}

async function deleteFeed(feedId) {
  try {
    const feedsData = await fetch("/api/feeds").then((r) => r.json());
    const feed = feedsData.feeds.find((f) => f.id === feedId);

    if (!feed) {
      alert("Feed not found");
      return;
    }

    if (!confirm(`Delete "${feed.name}"?\n\nThis cannot be undone.`)) return;

    const response = await fetch(`/api/feeds/${feedId}`, {
      method: "DELETE",
    });

    if (response.ok) {
      await loadFeedsDetailed();
    } else {
      alert("Failed to delete feed");
    }
  } catch (error) {
    console.error("Error deleting feed:", error);
    alert("Error: " + error.message);
  }
}
async function editFeed(feedId) {
  try {
    const feedsData = await fetch("/api/feeds").then((r) => r.json());
    const feed = feedsData.feeds.find((f) => f.id === feedId);

    if (!feed) {
      alert("Feed not found");
      return;
    }

    openFeedModal(feedId, feed.name, feed.url, feed.description);
  } catch (error) {
    console.error("Error loading feed:", error);
    alert("Error: " + error.message);
  }
}

window.editFeed = editFeed;
window.toggleFeed = toggleFeed;
// Test RSS feed
async function testFeed(feedId) {
  try {
    const response = await fetch(`/api/feeds/${feedId}/test`, {
      method: "POST",
    });

    const data = await response.json();

    if (response.ok && data.status === "success") {
      alert(
        `✅ Feed test successful!\n\nTitle: ${data.title}\nEntries found: ${data.entries}`
      );
    } else {
      alert("❌ Feed test failed: " + (data.error || "Unknown error"));
    }
  } catch (error) {
    console.error("Failed to test feed:", error);
    alert("❌ Network error: " + error.message);
  }
}

window.testFeed = testFeed;

// Make functions globally accessible
window.loadFeedsDetailed = loadFeedsDetailed;
window.showAddFeedModal = showAddFeedModal;
window.closeAddFeedModal = closeAddFeedModal;
window.addNewFeed = addNewFeed;
window.deleteFeed = deleteFeed;
window.testFeed = testFeed;

console.log("✅ Feed management functions loaded");

// Load strategy signals (for terminal dashboard)
async function loadStrategies() {
  try {
    const response = await fetch("/api/strategy/current");
    const data = await response.json();

    const signals = data.signals || [];

    const signalCountEl = document.getElementById("signal-count");
    if (signalCountEl) signalCountEl.textContent = signals.length;

    const strategySignalCountEl = document.getElementById(
      "strategy-signal-count"
    );
    if (strategySignalCountEl)
      strategySignalCountEl.textContent = signals.length;

    // Recent signals (overview tab) - show final signal only
    const recentSignalsEl = document.getElementById("recent-signals");
    if (recentSignalsEl) {
      const recentHtml = signals
        .slice(0, 5)
        .map(
          (sig) => `
                <tr>
                    <td class="timestamp">${formatTimeShort(sig.timestamp)}</td>
                    <td>${sig.symbol}</td>
                    <td><span class="signal-badge signal-${sig.final_signal.toLowerCase()}">${sig.final_signal.toUpperCase()}</span></td>
                    <td class="price">$${sig.price.toLocaleString()}</td>
                </tr>
            `
        )
        .join("");
      recentSignalsEl.innerHTML =
        recentHtml || '<tr><td colspan="4">No signals yet</td></tr>';
    }

    // All signals (strategies tab) - show detailed breakdown
    const strategySignalsEl = document.getElementById("strategy-signals");
    if (strategySignalsEl) {
      const allSignalsHtml = signals
        .map((sig) => {
          const strategies = sig.strategies || {};
          const strategyNames = Object.keys(strategies);

          // Build strategy summary
          const strategySummary = strategyNames
            .map((name) => {
              const s = strategies[name];
              return `${name}:${s.signal}(${Math.round(s.confidence * 100)}%)`;
            })
            .join(", ");

          // Use final_confidence, fallback to confidence
          const confidence = sig.final_confidence || sig.confidence || 0;

          return `
                <tr>
                    <td class="timestamp">${formatTimeShort(sig.timestamp)}</td>
                    <td>${sig.symbol}</td>
                    <td style="font-size: 9px;">${strategySummary || "N/A"}</td>
                    <td><span class="signal-badge signal-${sig.final_signal.toLowerCase()}">${sig.final_signal.toUpperCase()}</span></td>
                    <td>${Math.round(confidence * 100)}%</td>
                    <td class="price">$${sig.price.toLocaleString()}</td>
                    <td style="font-size: 9px; max-width: 300px;">
                        ${strategyNames
                          .map((name) => `${name}: ${strategies[name].reason}`)
                          .join(" | ")}
                    </td>
                </tr>
            `;
        })
        .join("");
      strategySignalsEl.innerHTML =
        allSignalsHtml || '<tr><td colspan="7">No signals yet</td></tr>';
    }
  } catch (error) {
    console.error("Error loading strategies:", error);
  }
}

// Load health status (for terminal dashboard)
async function loadHealth() {
  try {
    const response = await fetch("/api/health/detailed");
    const data = await response.json();

    const services = [
      { name: "OpenAI API", key: "openai", data: data.openai },
      { name: "Kraken API", key: "exchange", data: data.exchange },
      { name: "RSS Feeds", key: "rssFeeds", data: data.rssFeeds },
      { name: "Database", key: "database", data: data.database },
    ];

    const healthGridEl = document.getElementById("health-grid");
    if (healthGridEl) {
      const healthHtml = services
        .map((svc) => {
          const statusClass =
            svc.data?.status === "operational"
              ? "positive"
              : svc.data?.status === "degraded"
              ? "warning"
              : "negative";

          const errorCount = svc.data?.errorCount || 0;
          const lastError = svc.data?.lastError;

          // Get summary message
          const summaryMsg =
            svc.data?.recentErrors?.[0]?.message ||
            lastError?.message ||
            "Unknown error";

          return `
            <div class="health-item ${svc.data?.status || ""}">
              <div class="health-label">${svc.name}</div>
              <div class="health-value ${statusClass}">●</div>
              <div class="health-status">${svc.data?.status || "--"}</div>
              <div class="health-details">
                <div>Latency: ${svc.data?.latency || "--"}ms</div>
                <div class="health-error-count">Errors (24h): ${errorCount}</div>
                ${
                  svc.data?.status !== "operational"
                    ? `
                  <div style="font-size: 8px; color: #ff0000; margin-top: 5px; line-height: 1.3;">
                    ${summaryMsg.substring(0, 60)}${
                        summaryMsg.length > 60 ? "..." : ""
                      }
                  </div>
                `
                    : ""
                }
              </div>
              <div class="health-actions">
                <button class="health-action-btn" onclick="testService('${
                  svc.key
                }')">TEST</button>
                ${
                  svc.data?.status !== "operational"
                    ? `
                  <button class="health-action-btn" onclick="showServiceDetails('${svc.key}')">DETAILS</button>
                `
                    : ""
                }
                ${
                  errorCount > 0
                    ? `
                  <button class="health-action-btn" onclick="clearServiceErrors('${svc.key}')">CLEAR</button>
                `
                    : ""
                }
              </div>
              <span id="test-indicator-${
                svc.key
              }" class="testing-indicator" style="display: none;"></span>
            </div>
          `;
        })
        .join("");
      healthGridEl.innerHTML = healthHtml;
    }

    // Store service data for details modal
    window.healthServiceData = {
      openai: data.openai,
      exchange: data.exchange,
      rssFeeds: data.rssFeeds,
      database: data.database,
    };

    // Update header status
    const allOk = services.every((s) => s.data?.status === "operational");
    const statusDotEl = document.getElementById("status-dot");
    const statusTextEl = document.getElementById("status-text");

    if (statusDotEl)
      statusDotEl.className = "status-dot " + (allOk ? "" : "red");
    if (statusTextEl) statusTextEl.textContent = allOk ? "LIVE" : "ERROR";

    // Load recent errors
    await loadRecentErrors();
  } catch (error) {
    console.error("Error loading health:", error);
  }
}

// Enhanced showServiceDetails function
async function showServiceDetails(serviceKey) {
  const response = await fetch("/api/health/detailed");
  const data = await response.json();
  const serviceData = data[serviceKey];
  if (!serviceData) {
    alert("No details available");
    return;
  }

  // Get the most recent error with full details
  const lastError = serviceData.lastError || serviceData.recentErrors?.[0];

  let detailsHtml = `
    <div style="font-family: 'Courier New', monospace; color: #00ff00; background: #000; padding: 20px; max-width: 600px;">
      <div style="border-bottom: 1px solid #00ff00; padding-bottom: 10px; margin-bottom: 15px;">
        <h3 style="margin: 0; color: #00ff00; font-size: 14px;">
          ${serviceKey.toUpperCase()} - DETAILS
        </h3>
      </div>
      
      <div style="margin-bottom: 15px;">
        <div style="font-size: 10px; color: #888; margin-bottom: 5px;">STATUS</div>
        <div style="font-size: 12px; color: ${
          serviceData.status === "operational" ? "#00ff00" : "#ff0000"
        };">
          ${serviceData.status.toUpperCase()}
        </div>
      </div>
  `;

  if (lastError) {
    detailsHtml += `
      <div style="margin-bottom: 15px;">
        <div style="font-size: 10px; color: #888; margin-bottom: 5px;">LAST ERROR</div>
        <div style="font-size: 11px; color: #ff0000; line-height: 1.4;">
          ${lastError.message}
        </div>
        ${
          lastError.details
            ? `
          <div style="font-size: 9px; color: #ffa500; margin-top: 8px; line-height: 1.4;">
            ${lastError.details}
          </div>
        `
            : ""
        }
        ${
          lastError.action
            ? `
          <div style="margin-top: 12px; padding: 10px; background: rgba(0, 255, 0, 0.1); border: 1px solid #00ff00;">
            <div style="font-size: 9px; color: #888; margin-bottom: 5px;">ACTION REQUIRED</div>
            <div style="font-size: 10px; color: #00ff00; line-height: 1.4;">
              ${lastError.action}
            </div>
          </div>
        `
            : ""
        }
        ${
          lastError.timestamp
            ? `
          <div style="font-size: 8px; color: #888; margin-top: 8px;">
            ${new Date(lastError.timestamp).toLocaleString()}
          </div>
        `
            : ""
        }
      </div>
    `;
  }

  // Special handling for RSS feeds
  if (serviceKey === "rssFeeds" && lastError?.metadata?.details) {
    const details = lastError.metadata.details;

    if (details.broken && details.broken.length > 0) {
      detailsHtml += `
        <div style="margin-bottom: 15px;">
          <div style="font-size: 10px; color: #888; margin-bottom: 5px;">BROKEN FEEDS (${
            details.broken.length
          })</div>
          ${details.broken
            .map(
              (feed) => `
            <div style="padding: 8px; margin-bottom: 5px; background: rgba(255, 0, 0, 0.1); border-left: 2px solid #ff0000;">
              <div style="font-size: 10px; color: #ff0000; font-weight: bold;">${feed.name}</div>
              <div style="font-size: 8px; color: #888; margin-top: 3px;">${feed.url}</div>
              <div style="font-size: 9px; color: #ffa500; margin-top: 3px;">${feed.error}</div>
            </div>
          `
            )
            .join("")}
        </div>
      `;
    }

    if (details.operational && details.operational.length > 0) {
      detailsHtml += `
        <div style="margin-bottom: 15px;">
          <div style="font-size: 10px; color: #888; margin-bottom: 5px;">OPERATIONAL FEEDS (${
            details.operational.length
          })</div>
          ${details.operational
            .map(
              (feed) => `
            <div style="padding: 6px; margin-bottom: 3px; background: rgba(0, 255, 0, 0.05); border-left: 2px solid #00ff00;">
              <div style="font-size: 9px; color: #00ff00;">
                ${feed.name} - ${feed.entries} entries (${feed.latency}ms)
              </div>
            </div>
          `
            )
            .join("")}
        </div>
      `;
    }
  }

  detailsHtml += `
      <div style="margin-top: 20px; display: flex; gap: 10px;">
        <button onclick="testService('${serviceKey}')" style="flex: 1; padding: 8px; background: rgba(0, 255, 0, 0.1); border: 1px solid #00ff00; color: #00ff00; cursor: pointer; font-family: 'Courier New', monospace; font-size: 10px;">
          TEST CONNECTION
        </button>
        ${
          serviceData.errorCount > 0
            ? `
          <button onclick="clearServiceErrors('${serviceKey}'); closeDetailsModal();" style="flex: 1; padding: 8px; background: rgba(255, 0, 0, 0.1); border: 1px solid #ff0000; color: #ff0000; cursor: pointer; font-family: 'Courier New', monospace; font-size: 10px;">
            CLEAR ERRORS
          </button>
        `
            : ""
        }
        <button onclick="closeDetailsModal()" style="flex: 1; padding: 8px; background: rgba(255, 255, 255, 0.1); border: 1px solid #888; color: #888; cursor: pointer; font-family: 'Courier New', monospace; font-size: 10px;">
          CLOSE
        </button>
      </div>
    </div>
  `;

  // Create modal
  const modal = document.createElement("div");
  modal.id = "details-modal";
  modal.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
  `;
  modal.innerHTML = detailsHtml;
  modal.onclick = (e) => {
    if (e.target === modal) closeDetailsModal();
  };

  document.body.appendChild(modal);
}

function closeDetailsModal() {
  const modal = document.getElementById("details-modal");
  if (modal) {
    modal.remove();
  }
}

// Make ERROR button in header jump to Health tab
function handleErrorButtonClick() {
  // Switch to health tab
  switchTab("health");

  // Scroll to error log section
  setTimeout(() => {
    const errorLog = document.querySelector(".error-log-section");
    if (errorLog) {
      errorLog.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, 100);
}

// Add this to your existing window exports
window.showServiceDetails = showServiceDetails;
window.closeDetailsModal = closeDetailsModal;
window.handleErrorButtonClick = handleErrorButtonClick;
// ADD these new functions to dashboard.js (after loadHealth function)

async function loadRecentErrors() {
  try {
    const response = await fetch("/api/errors?limit=20");
    const data = await response.json();

    const errorLogContainer = document.getElementById("error-log-container");
    if (!errorLogContainer) return;

    if (!data.errors || data.errors.length === 0) {
      errorLogContainer.innerHTML =
        '<div class="error-log-empty">No errors recorded</div>';
      return;
    }

    const errorsHtml = data.errors
      .map(
        (error, index) => `
      <div class="error-entry ${
        error.severity
      }" onclick="toggleErrorDetails(${index})">
        <div class="error-header">
          <div class="error-component">${error.component}</div>
          <div class="error-timestamp">${new Date(
            error.timestamp
          ).toLocaleString()}</div>
        </div>
        <div class="error-message">${error.message}</div>
        <div class="error-expand-hint">Click to expand details</div>
        <div class="error-details" id="error-details-${index}">
          ${
            error.exception
              ? `<div class="error-exception">Exception: ${error.exception_type} - ${error.exception}</div>`
              : ""
          }
          ${
            error.stack_trace
              ? `<div class="error-stack-trace">${error.stack_trace}</div>`
              : ""
          }
          ${
            error.metadata && Object.keys(error.metadata).length > 0
              ? `<div style="margin-top: 8px; font-size: 9px;">Metadata: ${JSON.stringify(
                  error.metadata,
                  null,
                  2
                )}</div>`
              : ""
          }
        </div>
      </div>
    `
      )
      .join("");

    errorLogContainer.innerHTML = errorsHtml;
  } catch (error) {
    console.error("Error loading errors:", error);
  }
}

function toggleErrorDetails(index) {
  const errorEntry = event.currentTarget;
  errorEntry.classList.toggle("expanded");
}

async function showServiceDetails(serviceKey, serviceData) {
  // Could show a modal with detailed service info
  console.log("Service details:", serviceKey, serviceData);
}

async function testService(serviceKey) {
  const indicator = document.getElementById(`test-indicator-${serviceKey}`);
  if (indicator) {
    indicator.style.display = "inline-block";
    indicator.textContent = "⟳";
    indicator.classList.add("spinning");
  }

  try {
    const serviceMap = {
      openai: "openai",
      exchange: "kraken",
      rssFeeds: "rss",
      database: "database",
    };

    const endpoint = serviceMap[serviceKey] || serviceKey;
    const response = await fetch(`/api/test/${endpoint}`, { method: "POST" });
    const data = await response.json();

    if (data.success) {
      alert(
        `✓ ${endpoint.toUpperCase()} test passed\nLatency: ${
          data.latency || "N/A"
        }ms`
      );
    } else {
      alert(
        `✗ ${endpoint.toUpperCase()} test failed\n${data.error || data.message}`
      );
    }

    // Reload health after test
    await loadHealth();
  } catch (error) {
    alert(`Error testing service: ${error.message}`);
  } finally {
    if (indicator) {
      indicator.style.display = "none";
      indicator.classList.remove("spinning");
    }
  }
}

async function clearServiceErrors(serviceKey) {
  if (!confirm(`Clear all errors for ${serviceKey}?`)) return;

  try {
    const response = await fetch(`/api/errors/clear?component=${serviceKey}`, {
      method: "POST",
    });
    const data = await response.json();

    if (data.success) {
      alert(`Cleared ${data.cleared} error(s)`);
      await loadHealth();
    }
  } catch (error) {
    alert(`Error clearing errors: ${error.message}`);
  }
}

async function refreshErrors() {
  await loadRecentErrors();
}

async function clearAllErrors() {
  if (!confirm("Clear ALL errors?")) return;

  try {
    const response = await fetch("/api/errors/clear", { method: "POST" });
    const data = await response.json();

    if (data.success) {
      alert(`Cleared ${data.cleared} error(s)`);
      await loadHealth();
    }
  } catch (error) {
    alert(`Error clearing errors: ${error.message}`);
  }
}

async function loadPortfolio() {
  try {
    const response = await fetch("/partial");
    const data = await response.json();

    const summary = data.summary || {};

    const totalTradesEl = document.getElementById("total-trades");
    if (totalTradesEl) totalTradesEl.textContent = summary.total_trades || 0;

    const symbols = summary.symbols || {};
    const winners = Object.values(symbols).filter(
      (s) => (s.pnl || 0) > 0
    ).length;
    const total = Object.keys(symbols).length;
    const winRate = total > 0 ? Math.round((winners / total) * 100) : 0;

    const winRateEl = document.getElementById("win-rate");
    if (winRateEl) winRateEl.textContent = winRate + "%";

    // trades from /partial already has HOLDs filtered out by backend
    const trades = data.trades || [];

    // Update all trade counts with the actual filtered count
    const tradeCountEl = document.getElementById("trade-count");
    if (tradeCountEl) tradeCountEl.textContent = trades.length;

    const totalTradeCountEl = document.getElementById("total-trade-count");
    if (totalTradeCountEl) totalTradeCountEl.textContent = trades.length;

    const allTradeCountEl = document.getElementById("all-trade-count");
    if (allTradeCountEl) allTradeCountEl.textContent = trades.length;

    // Recent trades (overview tab) - first 5, sorted
    const recentTradesEl = document.getElementById("recent-trades");
    if (recentTradesEl) {
      const sortedRecent = [...trades]
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
        .slice(0, 5);

      const tradesHtml = sortedRecent
        .map(
          (trade) => `
      <tr>
          <td class="timestamp">${formatTimeShort(trade.timestamp)}</td>
          <td>${trade.symbol}</td>
          <td><span class="signal-badge signal-${trade.action.toLowerCase()}">${trade.action.toUpperCase()}</span></td>
          <td class="price">$${trade.price.toLocaleString()}</td>
      </tr>
  `
        )
        .join("");

      recentTradesEl.innerHTML =
        tradesHtml || '<tr><td colspan="4">No trades yet</td></tr>';
    }

    // All trades (trades tab) - everything, sorted
    const allTradesEl = document.getElementById("all-trades");
    if (allTradesEl) {
      const sortedAll = [...trades].sort(
        (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
      );

      const allTradesHtml = sortedAll
        .map(
          (trade) => `
            <tr>
                <td class="timestamp">${trade.timestamp}</td>
                <td>${trade.symbol}</td>
                <td><span class="signal-badge signal-${trade.action.toLowerCase()}">${trade.action.toUpperCase()}</span></td>
                <td class="price">$${trade.price.toLocaleString()}</td>
                <td>${trade.amount || 0.01}</td>
                <td class="price">$${(trade.value || 0).toFixed(2)}</td>
                <td style="font-size: 9px;">${trade.reason || ""}</td>
            </tr>
            `
        )
        .join("");
      allTradesEl.innerHTML =
        allTradesHtml || '<tr><td colspan="7">No trades yet</td></tr>';
    }
  } catch (error) {
    console.error("Error loading portfolio:", error);
  }
}

// Also add loadStatus for the status section
async function loadStatus() {
  try {
    const response = await fetch("/status");
    const data = await response.json();
    const status = data.last_status;

    const lastRunEl = document.getElementById("last-run");
    if (lastRunEl) {
      // Display time as-is (already in local timezone from backend)
      lastRunEl.textContent = status.time || "--";
    }

    const nextRunEl = document.getElementById("next-run");
    if (nextRunEl) {
      nextRunEl.textContent = data.next_run || "--";
    }

    const statusMsgEl = document.getElementById("status-msg");
    if (statusMsgEl) statusMsgEl.textContent = status.message || "--";
  } catch (error) {
    console.error("Failed to load status:", error);
  }
}

// Load holdings/positions
async function loadHoldings() {
  try {
    const response = await fetch("/api/holdings");
    const data = await response.json();

    const holdings = data.holdings || {};
    const summary = data.summary || {};

    // Update summary metrics
    const countEl = document.getElementById("holdings-count");
    if (countEl) countEl.textContent = summary.total_positions || 0;

    const positionsEl = document.getElementById("holdings-positions");
    if (positionsEl) positionsEl.textContent = summary.total_positions || 0;

    const valueEl = document.getElementById("holdings-value");
    if (valueEl) {
      const value = summary.total_market_value || 0;
      valueEl.textContent =
        "$" +
        value.toLocaleString("en-US", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      valueEl.className =
        "metric-value price " + (value >= 0 ? "positive" : "negative");
    }

    const pnlEl = document.getElementById("holdings-pnl");
    if (pnlEl) {
      const pnl = summary.total_unrealized_pnl || 0;
      pnlEl.textContent =
        (pnl >= 0 ? "+" : "") +
        "$" +
        Math.abs(pnl).toLocaleString("en-US", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      pnlEl.className =
        "metric-value price " + (pnl >= 0 ? "positive" : "negative");
    }

    // Populate detailed table
    const tableEl = document.getElementById("holdings-table");
    if (tableEl) {
      const symbols = Object.keys(holdings);

      if (symbols.length === 0) {
        tableEl.innerHTML =
          '<tr><td colspan="8" style="text-align: center; padding: 10px; color: #666;">No positions</td></tr>';
      } else {
        const rows = symbols
          .map((symbol) => {
            const h = holdings[symbol];
            const pnl = h.unrealized_pnl || 0;
            const pnlPct =
              h.cost_basis > 0
                ? ((h.market_value - h.cost_basis) / h.cost_basis) * 100
                : 0;
            const pnlClass = pnl >= 0 ? "positive" : "negative";

            return `
            <tr>
              <td style="font-weight: bold;">${symbol}</td>
              <td>${h.amount.toFixed(6)}</td>
              <td class="price">$${h.avg_price.toLocaleString()}</td>
              <td class="price">$${h.current_price.toLocaleString()}</td>
              <td class="price">$${h.market_value.toFixed(2)}</td>
              <td class="price">$${h.cost_basis.toFixed(2)}</td>
              <td class="${pnlClass} price">${
              pnl >= 0 ? "+" : ""
            }$${pnl.toFixed(2)}</td>
              <td class="${pnlClass}">${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(
              2
            )}%</td>
            </tr>
          `;
          })
          .join("");

        tableEl.innerHTML = rows;
      }
    }
  } catch (error) {
    console.error("Error loading holdings:", error);
  }
}
// Settings Modal Functions
function openSettingsModal() {
  // Load current config
  fetch("/api/config")
    .then((r) => r.json())
    .then((data) => {
      const config = data.config;

      // Trading mode
      document.querySelector(
        `input[name="trading_mode"][value="${config.trading_mode}"]`
      ).checked = true;

      // Strategies
      document.getElementById("sentiment-enabled").checked =
        config.strategies.sentiment.enabled;
      document.getElementById("sentiment-weight").value =
        config.strategies.sentiment.weight;
      document.getElementById("technical-enabled").checked =
        config.strategies.technical.enabled;
      document.getElementById("technical-weight").value =
        config.strategies.technical.weight;
      document.getElementById("volume-enabled").checked =
        config.strategies.volume.enabled;
      document.getElementById("volume-weight").value =
        config.strategies.volume.weight;

      // Aggregation
      document.getElementById("aggregation-method").value =
        config.aggregation.method;
      document.getElementById("min-confidence").value =
        config.aggregation.min_confidence;
      document.getElementById("min-confidence-percent").textContent =
        Math.round(config.aggregation.min_confidence * 100);

      // Risk management
      document.getElementById("position-size").value =
        config.risk_management.position_size_percent;
      document.getElementById("max-daily-loss").value =
        config.risk_management.max_daily_loss_percent;
      document.getElementById("trading-fee").value = config.trading_fee_percent;
      document.getElementById("max-positions").value =
        config.risk_management.max_open_positions || "";

      document.getElementById("settingsModal").style.display = "block";
    });
}

function closeSettingsModal() {
  document.getElementById("settingsModal").style.display = "none";
}

function saveSettings() {
  const config = {
    trading_mode: document.querySelector('input[name="trading_mode"]:checked')
      .value,
    strategies: {
      sentiment: {
        enabled: document.getElementById("sentiment-enabled").checked,
        weight: parseFloat(document.getElementById("sentiment-weight").value),
      },
      technical: {
        enabled: document.getElementById("technical-enabled").checked,
        weight: parseFloat(document.getElementById("technical-weight").value),
      },
      volume: {
        enabled: document.getElementById("volume-enabled").checked,
        weight: parseFloat(document.getElementById("volume-weight").value),
      },
    },
    aggregation: {
      method: document.getElementById("aggregation-method").value,
      min_confidence: parseFloat(
        document.getElementById("min-confidence").value
      ),
    },
    risk_management: {
      position_size_percent: parseFloat(
        document.getElementById("position-size").value
      ),
      max_daily_loss_percent: parseFloat(
        document.getElementById("max-daily-loss").value
      ),
      max_open_positions: document.getElementById("max-positions").value
        ? parseInt(document.getElementById("max-positions").value)
        : null,
    },
    trading_fee_percent: parseFloat(
      document.getElementById("trading-fee").value
    ),
  };

  fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.status === "success") {
        alert("✅ Configuration saved successfully!");
        closeSettingsModal();
      } else {
        alert("❌ Error saving configuration: " + data.error);
      }
    })
    .catch((err) => alert("❌ Error: " + err));
}

// Update percentage display when min-confidence slider changes
document.addEventListener("DOMContentLoaded", () => {
  const minConfInput = document.getElementById("min-confidence");
  if (minConfInput) {
    minConfInput.addEventListener("input", (e) => {
      document.getElementById("min-confidence-percent").textContent =
        Math.round(e.target.value * 100);
    });
  }

  // Close modal when clicking outside
  window.onclick = (event) => {
    const modal = document.getElementById("settingsModal");
    if (event.target === modal) {
      closeSettingsModal();
    }
  };
});
// Update refreshData to call all the functions
function refreshData() {
  refreshBalance();
  loadPortfolio();
  loadStrategies();
  loadStatus();
  loadHealth();
  loadHoldings();
  loadAllTradesTab();
}
loadStatus();

// Poll status every 5 seconds
setInterval(loadStatus, 5000);
// All Trades Modal Functions
async function openAllTradesModal() {
  document.getElementById("allTradesModal").style.display = "block";

  try {
    // Fetch ALL trades from the trades.json file directly
    const response = await fetch("/api/trades/all");
    const data = await response.json();

    // data is already an array, no need to extract a property
    const trades = Array.isArray(data) ? data : [];

    const modalCountEl = document.getElementById("modal-trade-count");
    if (modalCountEl) modalCountEl.textContent = trades.length;

    const tableBody = document.getElementById("modal-trades-table");
    if (tableBody) {
      // Sort by timestamp descending
      const sortedTrades = [...trades].sort(
        (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
      );
      const html = sortedTrades
        .map(
          (trade) => `
                <tr style="border-bottom: 1px solid rgba(0, 255, 0, 0.2);">
                    <td style="padding: 8px; font-size: 11px;">${formatTimeShort(
                      trade.timestamp
                    )}</td>
                    <td style="padding: 8px;">${trade.symbol}</td>
                    <td style="padding: 8px;">
                        <span class="signal-badge signal-${trade.action.toLowerCase()}">${trade.action.toUpperCase()}</span>
                    </td>
                    <td style="padding: 8px;" class="price">$${trade.price.toLocaleString()}</td>
                    <td style="padding: 8px;">${(trade.amount || 0).toFixed(
                      6
                    )}</td>
                    <td style="padding: 8px;" class="price">$${(
                      trade.value || 0
                    ).toFixed(2)}</td>
                    <td style="padding: 8px; font-size: 9px; max-width: 400px; overflow: hidden; text-overflow: ellipsis;">${
                      trade.reason || ""
                    }</td>
                </tr>
            `
        )
        .join("");

      tableBody.innerHTML =
        html ||
        '<tr><td colspan="7" style="text-align: center; padding: 20px;">No trades found</td></tr>';
    }
  } catch (error) {
    console.error("Error loading all trades:", error);
    const tableBody = document.getElementById("modal-trades-table");
    if (tableBody) {
      tableBody.innerHTML =
        '<tr><td colspan="7" style="text-align: center; padding: 20px; color: #ff0000;">Error loading trades</td></tr>';
    }
  }
}

function closeAllTradesModal() {
  document.getElementById("allTradesModal").style.display = "none";
}
// Clock update - moved from inline script
function updateClock() {
  const now = new Date();
  const clockEl = document.getElementById("status-time");
  if (clockEl) {
    clockEl.textContent = now.toTimeString().split(" ")[0];
  }
}
// Load ALL trades for the Trades tab
async function loadAllTradesTab() {
  try {
    const response = await fetch("/api/trades/all");
    const trades = await response.json();

    // Update count
    const allTradeCountEl = document.getElementById("all-trade-count");
    if (allTradeCountEl) allTradeCountEl.textContent = trades.length;

    // Populate table
    const allTradesEl = document.getElementById("all-trades");
    if (allTradesEl) {
      const sortedAll = [...trades].sort(
        (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
      );

      const allTradesHtml = sortedAll
        .map(
          (trade) => `
            <tr>
                <td class="timestamp">${trade.timestamp}</td>
                <td>${trade.symbol}</td>
                <td><span class="signal-badge signal-${trade.action.toLowerCase()}">${trade.action.toUpperCase()}</span></td>
                <td class="price">$${trade.price.toLocaleString()}</td>
                <td>${trade.amount || 0.01}</td>
                <td class="price">$${(trade.value || 0).toFixed(2)}</td>
                <td style="font-size: 9px;">${trade.reason || ""}</td>
            </tr>
            `
        )
        .join("");
      allTradesEl.innerHTML =
        allTradesHtml || '<tr><td colspan="7">No trades yet</td></tr>';
    }
  } catch (error) {
    console.error("Error loading all trades:", error);
  }
}
// Start clock on load (but not during tests)
if (typeof process === "undefined" || process.env.NODE_ENV !== "test") {
  setInterval(updateClock, 1000);
  updateClock(); // Initial call
}

console.log("✅ Terminal dashboard functions loaded");

// At end of dashboard.js
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    loadAllTradesTab,
    openAllTradesModal,
    formatTimeShort,
  };
}
// Feed Edit Modal Functions
let currentEditFeedId = null;

function openFeedModal(feedId, name, url, description) {
  currentEditFeedId = feedId;
  document.getElementById("feedModalName").value = name || "";
  document.getElementById("feedModalUrl").value = url || "";
  document.getElementById("feedModalDesc").value = description || "";
  document.getElementById("feedModal").classList.add("active");
}

function closeFeedModal() {
  document.getElementById("feedModal").classList.remove("active");
  currentEditFeedId = null;
}

async function saveFeedModal() {
  const name = document.getElementById("feedModalName").value.trim();
  const url = document.getElementById("feedModalUrl").value.trim();
  const description = document.getElementById("feedModalDesc").value.trim();

  if (!name || !url) {
    alert("Name and URL are required");
    return;
  }

  try {
    const response = await fetch(`/api/feeds/${currentEditFeedId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, url, description }),
    });

    if (response.ok) {
      closeFeedModal();
      await loadFeedsDetailed();
    } else {
      alert("Failed to update feed");
    }
  } catch (error) {
    console.error("Error saving feed:", error);
    alert("Error: " + error.message);
  }
}

window.openFeedModal = openFeedModal;
window.closeFeedModal = closeFeedModal;
window.saveFeedModal = saveFeedModal;
// Expose functions to window
window.loadHealth = loadHealth;
window.testService = testService;
window.clearServiceErrors = clearServiceErrors;
window.refreshErrors = refreshErrors;
window.clearAllErrors = clearAllErrors;
window.loadRecentErrors = loadRecentErrors;
window.toggleErrorDetails = toggleErrorDetails;
window.showServiceDetails = showServiceDetails;
