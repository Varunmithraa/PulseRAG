class FeedsViewer {
  constructor() {
    this.activeContainer = document.getElementById("active-feeds-container");
    this.catalogContainer = document.getElementById("catalog-feeds-container");
    this.searchInput = document.getElementById("feed-search-input");
    this.activeCountBadge = document.getElementById("active-feeds-count");
    this.headerBadge = document.getElementById("feeds-count-badge");
    
    this.allCatalog = [];
    this.activeFeeds = [];
    this.init();
  }

  async init() {
    await this.fetchFeeds();

    // Instant Search / Filter
    if (this.searchInput) {
      this.searchInput.addEventListener("input", () => this.filterCatalog());
    }

    // Modal Events
    const customFeedModal = document.getElementById("custom-feed-modal");
    const openBtn = document.getElementById("open-custom-feed-btn");
    const closeBtn = document.getElementById("close-custom-feed-btn");
    const submitBtn = document.getElementById("submit-custom-feed-btn");

    if (openBtn) openBtn.addEventListener("click", () => customFeedModal.classList.add("open"));
    if (closeBtn) closeBtn.addEventListener("click", () => customFeedModal.classList.remove("open"));

    if (submitBtn) {
      submitBtn.addEventListener("click", async () => {
        const name = document.getElementById("custom-feed-name").value.trim();
        const url = document.getElementById("custom-feed-url").value.trim();
        const category = document.getElementById("custom-feed-category").value.trim() || "Live Web";

        if (!name || !url) {
          alert("Please provide both Feed Name and a valid RSS URL!");
          return;
        }

        await this.linkCustomFeed(name, url, category);
        customFeedModal.classList.remove("open");
        document.getElementById("custom-feed-name").value = "";
        document.getElementById("custom-feed-url").value = "";
      });
    }
  }

  async fetchFeeds() {
    try {
      const res = await fetch("/api/feeds");
      const data = await res.json();
      this.activeFeeds = data.active_feeds || [];
      this.allCatalog = data.catalog || [];

      this.renderActiveFeeds();
      this.renderCatalog(this.allCatalog);

      const activeCount = data.active_count || this.activeFeeds.length;
      if (this.activeCountBadge) this.activeCountBadge.textContent = activeCount;
      if (this.headerBadge) this.headerBadge.textContent = `${activeCount} Feeds`;
    } catch (e) {
      console.warn("Could not fetch feeds overview:", e);
    }
  }

  renderActiveFeeds() {
    if (!this.activeContainer) return;
    if (this.activeFeeds.length === 0) {
      this.activeContainer.innerHTML = `
        <div style="color: var(--text-dim); font-size: 0.8rem; text-align: center; padding: 14px; background: var(--bg-card); border-radius: var(--radius-sm);">
          No feeds currently linked. Browse the catalog below to connect live streams!
        </div>`;
      return;
    }

    this.activeContainer.innerHTML = this.activeFeeds.map(feed => {
      const isEnabled = feed.enabled !== false;
      const statusColor = isEnabled ? "var(--accent-emerald)" : "var(--accent-amber)";
      const statusText = isEnabled ? "Polling Live" : "Paused";

      return `
        <div class="feed-card active-card" id="feed-${feed.name}">
          <div class="feed-card-header">
            <div class="feed-title-box">
              <span class="feed-status-dot" style="background: ${statusColor}; box-shadow: 0 0 8px ${statusColor};"></span>
              <strong style="font-size: 0.88rem; color: var(--text-main);">${feed.name}</strong>
            </div>
            <span class="badge-tag" style="font-size: 0.65rem; text-transform: uppercase;">${feed.category}</span>
          </div>
          
          <div class="feed-meta-row">
            <span>Status: <strong style="color: ${statusColor};">${statusText}</strong></span>
            <span>Items Received: <strong style="color: var(--text-main);">${feed.item_count || 0}</strong></span>
          </div>

          <div class="feed-actions-row">
            <button class="feed-action-btn toggle-btn-sm" onclick="window.feedsViewer.toggleFeed('${feed.name}', ${!isEnabled})">
              ${isEnabled ? "⏸ Pause" : "▶ Resume"}
            </button>
            <button class="feed-action-btn unlink-btn-sm" onclick="window.feedsViewer.unlinkFeed('${feed.name}')">
              ✕ Unlink
            </button>
          </div>
        </div>
      `;
    }).join("");
  }

  renderCatalog(catalogItems) {
    if (!this.catalogContainer) return;
    if (catalogItems.length === 0) {
      this.catalogContainer.innerHTML = `
        <div style="color: var(--text-dim); font-size: 0.8rem; text-align: center; padding: 16px; background: var(--bg-card); border-radius: var(--radius-sm); border: 1px dashed var(--border-color);">
          No matching sources found in catalog.
        </div>`;
      return;
    }

    this.catalogContainer.innerHTML = catalogItems.map(item => {
      const isLinked = item.is_linked;
      return `
        <div class="feed-card catalog-card">
          <div class="feed-card-header">
            <strong style="font-size: 0.88rem; color: var(--text-main);">${item.name}</strong>
            <span class="badge-tag" style="font-size: 0.65rem; text-transform: uppercase;">${item.category}</span>
          </div>
          <p class="feed-desc">${item.description}</p>
          <div class="feed-card-footer">
            <span class="feed-url-hint" title="${item.url}">🔗 RSS Endpoint</span>
            ${isLinked ? `
              <button class="feed-action-btn linked-badge" disabled>
                ✓ Connected
              </button>
            ` : `
              <button class="feed-action-btn link-btn" onclick="window.feedsViewer.linkCatalogFeed('${item.name}', '${item.url}', '${item.category}', '${item.description.replace(/'/g, "\\'")}')">
                + Link Source
              </button>
            `}
          </div>
        </div>
      `;
    }).join("");
  }

  filterCatalog() {
    const query = (this.searchInput.value || "").toLowerCase().trim();
    if (!query) {
      this.renderCatalog(this.allCatalog);
      return;
    }

    const filtered = this.allCatalog.filter(item => 
      item.name.toLowerCase().includes(query) ||
      item.category.toLowerCase().includes(query) ||
      (item.description && item.description.toLowerCase().includes(query))
    );
    this.renderCatalog(filtered);
  }

  async linkCatalogFeed(name, url, category, description) {
    try {
      const res = await fetch("/api/feeds/link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, url, category, description })
      });
      await this.fetchFeeds();
      if (window.liveRadar) window.liveRadar.fetchEvents();
    } catch (e) {
      console.error("Failed to link catalog feed:", e);
    }
  }

  async linkCustomFeed(name, url, category) {
    try {
      const res = await fetch("/api/feeds/link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, url, category, description: "Custom User Feed" })
      });
      await this.fetchFeeds();
      if (window.liveRadar) window.liveRadar.fetchEvents();
    } catch (e) {
      console.error("Failed to link custom feed:", e);
    }
  }

  async unlinkFeed(name) {
    if (!confirm(`Unlink and disconnect "${name}"?`)) return;
    try {
      await fetch("/api/feeds/unlink", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });
      await this.fetchFeeds();
    } catch (e) {
      console.error("Failed to unlink feed:", e);
    }
  }

  async toggleFeed(name, enabled) {
    try {
      await fetch("/api/feeds/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, enabled })
      });
      await this.fetchFeeds();
    } catch (e) {
      console.error("Failed to toggle feed:", e);
    }
  }
}

window.feedsViewer = new FeedsViewer();
