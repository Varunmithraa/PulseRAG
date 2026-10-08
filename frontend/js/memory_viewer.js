class MemoryViewer {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.init();
  }

  async init() {
    await this.fetchMemories();
  }

  async fetchMemories() {
    try {
      const res = await fetch("/api/memory?user_id=default_user");
      const data = await res.json();
      this.renderMemories(data.facts || []);
      
      const badge = document.getElementById("memory-count-badge");
      if (badge) badge.textContent = `${(data.facts || []).length} Facts`;
    } catch (e) {
      console.warn("Failed to fetch memories:", e);
    }
  }

  renderMemories(facts) {
    if (!this.container) return;
    if (facts.length === 0) {
      this.container.innerHTML = `<div style="color: var(--text-dim); text-align: center; padding: 20px;">No long-term memories stored yet. Converse with the agent or add one below!</div>`;
      return;
    }

    this.container.innerHTML = facts.map(fact => `
      <div class="memory-card" id="fact-${fact.id}">
        <div class="memory-header">
          <span class="memory-category">${fact.category} • ${fact.entity_key}</span>
          <button class="memory-delete-btn" onclick="window.memoryViewer.deleteFact(${fact.id}, '${fact.entity_key}')" title="Delete Fact">✕</button>
        </div>
        <div class="memory-body">${fact.fact_content}</div>
        <div style="font-size: 0.7rem; color: var(--text-dim); margin-top: 4px;">Importance: ${(fact.importance_score * 100).toFixed(0)}%</div>
      </div>
    `).join("");
  }

  async deleteFact(factId, entityKey) {
    if (!confirm("Delete this learned memory from long-term storage?")) return;
    try {
      await fetch(`/api/memory/${factId}?user_id=default_user&entity_key=${encodeURIComponent(entityKey)}`, {
        method: "DELETE"
      });
      await this.fetchMemories();
    } catch (e) {
      console.error("Failed to delete memory fact:", e);
    }
  }

  async addFact(category, entityKey, factContent) {
    try {
      await fetch("/api/memory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "default_user",
          category,
          entity_key: entityKey,
          fact_content: factContent,
          importance_score: 0.9
        })
      });
      await this.fetchMemories();
    } catch (e) {
      console.error("Failed to add memory fact:", e);
    }
  }
}

window.memoryViewer = new MemoryViewer("memory-list-container");
