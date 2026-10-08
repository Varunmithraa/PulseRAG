class LiveRadarViewer {
  constructor(listId) {
    this.listEl = document.getElementById(listId);
    this.init();
  }

  async init() {
    await this.fetchEvents();
    // Poll updates every 6 seconds
    setInterval(() => this.fetchEvents(), 6000);
  }

  async fetchEvents() {
    try {
      const res = await fetch("/api/stream/events?limit=25");
      const data = await res.json();
      this.renderEvents(data.events || []);
      
      const badge = document.getElementById("radar-count-badge");
      if (badge) badge.textContent = `${(data.events || []).length} Live`;
    } catch (e) {
      console.warn("Failed to fetch live radar events:", e);
    }
  }

  renderEvents(events) {
    if (!this.listEl) return;
    if (events.length === 0) {
      this.listEl.innerHTML = `<div style="color: var(--text-dim); text-align: center; padding: 20px;">No live stream events in buffer yet.</div>`;
      return;
    }

    this.listEl.innerHTML = events.map(ev => {
      const tickers = (ev.tickers || []).map(t => `<span class="ticker-tag">${t}</span>`).join(" ");
      return `
        <div class="radar-item">
          <div class="radar-item-meta">
            <span><strong>${ev.source}</strong> • ${ev.category}</span>
            <span>${ev.age_str || "now"}</span>
          </div>
          <div class="radar-item-title">${ev.title}</div>
          <div class="radar-item-content">${ev.content}</div>
          ${tickers ? `<div style="margin-top: 6px;">${tickers}</div>` : ""}
        </div>
      `;
    }).join("");
  }

  async injectCustomEvent(title, content, source, category, tickers) {
    try {
      const res = await fetch("/api/stream/inject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          content,
          source: source || "User Radar Injection",
          category: category || "Breaking News",
          tickers: tickers ? tickers.split(",").map(t => t.trim().toUpperCase()) : []
        })
      });
      await this.fetchEvents();
      return await res.json();
    } catch (e) {
      console.error("Failed to inject event:", e);
    }
  }
}

window.liveRadar = new LiveRadarViewer("radar-list-container");
