class IntelAlertsManager {
  constructor() {
    this.alertsBadge = document.getElementById("alerts-count-badge");
    this.alertToggleBtn = document.getElementById("alerts-toggle-btn");
    this.alertsModal = document.getElementById("alerts-modal");
    this.alertsList = document.getElementById("alerts-list-container");
    this.toastContainer = document.getElementById("alert-toast-container");
    this.closeBtn = document.getElementById("close-alerts-modal-btn");
    this.simulateBtn = document.getElementById("simulate-alert-btn");
    this.clearBtn = document.getElementById("clear-alerts-btn");
    this.toggleMonitorBtn = document.getElementById("toggle-alerts-monitor-btn");
    this.toggleSoundBtn = document.getElementById("toggle-alert-sound-btn");

    this.shownToastIds = new Set();
    this.alerts = [];
    this.unreadCount = 0;
    this.audioContext = null;
    this.monitoringEnabled = true;
    this.soundEnabled = localStorage.getItem("pulserag_alerts_sound") !== "false";

    this.init();
  }

  init() {
    this.bindEvents();
    this.updateSoundButtonUI();
    this.fetchAlerts();
    // Poll alerts every 8 seconds
    setInterval(() => this.fetchAlerts(), 8000);
  }

  bindEvents() {
    if (this.alertToggleBtn) {
      this.alertToggleBtn.addEventListener("click", () => {
        this.openModal();
      });
    }

    if (this.closeBtn) {
      this.closeBtn.addEventListener("click", () => {
        this.closeModal();
      });
    }

    if (this.alertsModal) {
      this.alertsModal.addEventListener("click", (e) => {
        if (e.target === this.alertsModal) {
          this.closeModal();
        }
      });
    }

    if (this.simulateBtn) {
      this.simulateBtn.addEventListener("click", () => this.simulateAlert());
    }

    if (this.clearBtn) {
      this.clearBtn.addEventListener("click", () => this.clearAlerts());
    }

    if (this.toggleMonitorBtn) {
      this.toggleMonitorBtn.addEventListener("click", () => this.toggleMonitoring());
    }

    if (this.toggleSoundBtn) {
      this.toggleSoundBtn.addEventListener("click", () => this.toggleSound());
    }
  }

  toggleSound() {
    this.soundEnabled = !this.soundEnabled;
    localStorage.setItem("pulserag_alerts_sound", this.soundEnabled ? "true" : "false");
    this.updateSoundButtonUI();
  }

  updateSoundButtonUI() {
    if (!this.toggleSoundBtn) return;
    if (this.soundEnabled) {
      this.toggleSoundBtn.textContent = "🔊 Sound On";
      this.toggleSoundBtn.style.color = "var(--text-main)";
    } else {
      this.toggleSoundBtn.textContent = "🔇 Muted";
      this.toggleSoundBtn.style.color = "var(--text-dim)";
    }
  }

  async toggleMonitoring() {
    try {
      const newState = !this.monitoringEnabled;
      const res = await fetch("/api/alerts/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: newState })
      });
      const data = await res.json();
      this.monitoringEnabled = data.enabled !== false;
      this.updateMonitoringButtonUI();
    } catch (e) {
      console.error("Failed to toggle alerts monitoring:", e);
    }
  }

  updateMonitoringButtonUI() {
    if (!this.toggleMonitorBtn) return;
    if (this.monitoringEnabled) {
      this.toggleMonitorBtn.textContent = "🟢 Active";
      this.toggleMonitorBtn.style.borderColor = "var(--accent-emerald)";
      this.toggleMonitorBtn.style.color = "var(--accent-emerald)";
      this.toggleMonitorBtn.title = "Live Alerts Monitoring is Active (Click to Pause)";
    } else {
      this.toggleMonitorBtn.textContent = "⏸ Paused";
      this.toggleMonitorBtn.style.borderColor = "var(--accent-amber)";
      this.toggleMonitorBtn.style.color = "var(--accent-amber)";
      this.toggleMonitorBtn.title = "Live Alerts Monitoring is Paused (Click to Resume)";
    }
  }

  openModal() {
    if (!this.alertsModal) return;
    this.alertsModal.classList.add("open");
    this.markAllAsRead();
  }

  closeModal() {
    if (!this.alertsModal) return;
    this.alertsModal.classList.remove("open");
  }

  playAlertChime() {
    if (!this.soundEnabled) return;
    try {
      if (!this.audioContext) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) this.audioContext = new AudioCtx();
      }
      if (this.audioContext && this.audioContext.state === "suspended") {
        this.audioContext.resume();
      }
      if (this.audioContext) {
        const now = this.audioContext.currentTime;
        const osc = this.audioContext.createOscillator();
        const gain = this.audioContext.createGain();

        osc.type = "sine";
        osc.frequency.setValueAtTime(587.33, now); // D5
        osc.frequency.exponentialRampToValueAtTime(880.0, now + 0.12); // A5

        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

        osc.connect(gain);
        gain.connect(this.audioContext.destination);

        osc.start(now);
        osc.stop(now + 0.45);
      }
    } catch (e) {
      // Audio playback silently suppressed if blocked by browser policy
    }
  }

  async fetchAlerts() {
    try {
      const res = await fetch("/api/alerts");
      const data = await res.json();
      this.alerts = data.alerts || [];
      this.unreadCount = data.unread_count || 0;
      if (data.monitoring_enabled !== undefined) {
        this.monitoringEnabled = data.monitoring_enabled;
        this.updateMonitoringButtonUI();
      }

      this.updateHeaderBadge();
      this.renderAlertsList();

      // Check for newly arriving unread alerts to trigger floating toasts
      this.alerts.forEach((alert) => {
        if (!alert.read && !this.shownToastIds.has(alert.id)) {
          this.shownToastIds.add(alert.id);
          this.showToast(alert);
        }
      });
    } catch (e) {
      console.warn("Could not fetch autonomous alerts:", e);
    }
  }

  updateHeaderBadge() {
    if (this.alertsBadge) {
      this.alertsBadge.textContent = `${this.unreadCount} Alerts`;
    }

    if (this.alertToggleBtn) {
      if (this.unreadCount > 0) {
        this.alertToggleBtn.classList.add("has-unread");
      } else {
        this.alertToggleBtn.classList.remove("has-unread");
      }
    }
  }

  renderAlertsList() {
    if (!this.alertsList) return;

    if (this.alerts.length === 0) {
      this.alertsList.innerHTML = `
        <div style="text-align: center; padding: 40px 20px; color: var(--text-dim); background: var(--bg-card); border-radius: var(--radius-sm); border: 1px dashed var(--border-color);">
          <div style="font-size: 1.8rem; margin-bottom: 8px;">🛰️</div>
          <strong style="color: var(--text-main); font-size: 0.95rem;">No Active Breaking Alerts</strong>
          <p style="font-size: 0.78rem; margin-top: 4px; max-width: 380px; margin-left: auto; margin-right: auto;">
            The autonomous intelligence monitor continuously evaluates incoming streams. Click <strong>"⚡ Simulate Catalyst"</strong> to test an instant high-impact event!
          </p>
        </div>
      `;
      return;
    }

    this.alertsList.innerHTML = this.alerts.map((alert) => {
      const isCritical = alert.impact_level === "CRITICAL";
      const cardClass = isCritical ? "critical-card" : "high-card";
      const badgeColor = isCritical ? "var(--accent-rose)" : "var(--accent-amber)";
      const badgeBg = isCritical ? "rgba(244, 63, 94, 0.15)" : "rgba(245, 158, 11, 0.15)";
      const formattedTime = new Date(alert.timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

      const safeQuery = (alert.suggested_query || alert.headline).replace(/'/g, "\\'").replace(/"/g, '&quot;');

      return `
        <div class="alert-card-item ${cardClass}">
          <div class="alert-card-header">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 0.68rem; font-weight: 700; color: ${badgeColor}; background: ${badgeBg}; padding: 2px 8px; border-radius: 12px; border: 1px solid ${badgeColor};">
                🚨 ${alert.impact_level} • SCORE ${alert.impact_score}
              </span>
              <span style="font-size: 0.72rem; color: var(--text-dim);">${alert.source} • ${formattedTime}</span>
            </div>
            <span class="badge-tag" style="font-size: 0.65rem;">${alert.category}</span>
          </div>

          <div class="alert-card-headline">
            ${alert.headline}
          </div>

          <div class="alert-card-briefing">
            <div style="font-size: 0.7rem; font-weight: 700; color: var(--accent-cyan); margin-bottom: 3px; display: flex; align-items: center; gap: 4px;">
              ✨ Autonomous Agent Assessment:
            </div>
            ${alert.autonomous_briefing}
          </div>

          <div class="alert-card-footer">
            <span style="font-size: 0.7rem; color: var(--text-dim);">
              ${alert.tickers && alert.tickers.length > 0 ? `Tickers: <strong>${alert.tickers.join(", ")}</strong>` : "Monitored Stream"}
            </span>
            <button class="toast-analyze-btn" onclick="window.intelAlerts.analyzeWithAgent('${safeQuery}')">
              ⚡ Analyze with Agent
            </button>
          </div>
        </div>
      `;
    }).join("");
  }

  showToast(alert) {
    if (!this.toastContainer) return;

    this.playAlertChime();

    const isCritical = alert.impact_level === "CRITICAL";
    const toast = document.createElement("div");
    toast.className = `alert-toast ${isCritical ? "is-critical" : "is-high"}`;

    const badgeClass = isCritical ? "critical" : "high";
    const formattedTime = new Date(alert.timestamp * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const safeQuery = (alert.suggested_query || alert.headline).replace(/'/g, "\\'").replace(/"/g, '&quot;');

    toast.innerHTML = `
      <div class="toast-header">
        <span class="toast-badge ${badgeClass}">
          🚨 ${alert.impact_level} INTEL ALERT • ${alert.impact_score}
        </span>
        <button class="toast-close-btn" title="Dismiss Alert">✕</button>
      </div>

      <div class="toast-headline">
        ${alert.headline}
      </div>

      <div class="toast-briefing">
        ${alert.autonomous_briefing}
      </div>

      <div class="toast-actions">
        <span class="toast-meta">${alert.source} • ${formattedTime}</span>
        <button class="toast-analyze-btn" id="btn-deepdive-${alert.id}">
          ⚡ Ask Agent Deep-Dive
        </button>
      </div>
    `;

    // Bind action
    const analyzeBtn = toast.querySelector(`#btn-deepdive-${alert.id}`);
    if (analyzeBtn) {
      analyzeBtn.addEventListener("click", () => {
        this.analyzeWithAgent(alert.suggested_query || alert.headline);
        toast.remove();
      });
    }

    // Bind close
    const closeBtn = toast.querySelector(".toast-close-btn");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(() => toast.remove(), 250);
      });
    }

    this.toastContainer.appendChild(toast);

    // Auto-remove after 12 seconds
    setTimeout(() => {
      if (toast.parentElement) {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(() => toast.remove(), 250);
      }
    }, 12000);
  }

  analyzeWithAgent(queryText) {
    this.closeModal();

    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    const appContainer = document.getElementById("app-container");

    // Auto-expand sidebar if collapsed
    if (appContainer && appContainer.classList.contains("sidebar-collapsed")) {
      appContainer.classList.remove("sidebar-collapsed");
    }

    // Switch right panel to Graph tab to watch reasoning live
    const graphTabBtn = document.querySelector('.tab-btn[data-tab="tab-graph"]');
    if (graphTabBtn) graphTabBtn.click();

    if (chatInput && sendBtn) {
      chatInput.value = queryText;
      chatInput.focus();
      sendBtn.click();
    }
  }

  async simulateAlert() {
    try {
      const res = await fetch("/api/alerts/simulate", { method: "POST" });
      const data = await res.json();
      if (data.alert) {
        this.fetchAlerts();
        this.showToast(data.alert);
      }
    } catch (e) {
      console.error("Failed to simulate catalyst alert:", e);
    }
  }

  async markAllAsRead() {
    try {
      await fetch("/api/alerts/read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert_id: "all" })
      });
      this.unreadCount = 0;
      this.updateHeaderBadge();
    } catch (e) {
      console.warn("Could not mark alerts read:", e);
    }
  }

  async clearAlerts() {
    if (!confirm("Clear all autonomous intelligence alerts?")) return;
    try {
      await fetch("/api/alerts/clear", { method: "POST" });
      this.alerts = [];
      this.unreadCount = 0;
      this.updateHeaderBadge();
      this.renderAlertsList();
    } catch (e) {
      console.error("Failed to clear alerts:", e);
    }
  }
}

window.intelAlerts = new IntelAlertsManager();
