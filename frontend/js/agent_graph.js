class AgentGraphVisualizer {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.nodes = [
      { id: "recall_memory", icon: "🧠", title: "Cognitive Memory Recall", desc: "Episodic & Long-Term Semantic lookup" },
      { id: "route_query", icon: "🧭", title: "Autonomous Intent Router", desc: "Temporal intent routing & query refinement" },
      { id: "retrieve_docs", icon: "📡", title: "Stream & Vector Retrieval", desc: "Temporal Recency-Decay search over live buffer" },
      { id: "grade_docs", icon: "⚖️", title: "Corrective RAG (CRAG) Grader", desc: "Document relevance & hallucination filter" },
      { id: "synthesize", icon: "⚡", title: "Grounded Answer Synthesis", desc: "Streaming generation with inline citations" }
    ];
    this.renderInitial();
  }

  renderInitial() {
    if (!this.container) return;
    this.container.innerHTML = "";
    
    this.nodes.forEach((node, idx) => {
      const card = document.createElement("div");
      card.className = "graph-node-card";
      card.id = `node-${node.id}`;
      card.innerHTML = `
        <div class="node-header">
          <div class="node-title">
            <span>${node.icon}</span>
            <span>${node.title}</span>
          </div>
          <span class="badge-tag" id="badge-${node.id}">IDLE</span>
        </div>
        <div class="node-status-text" id="desc-${node.id}">${node.desc}</div>
        <div id="metric-${node.id}"></div>
      `;
      this.container.appendChild(card);

      if (idx < this.nodes.length - 1) {
        const connector = document.createElement("div");
        connector.className = "node-connector";
        this.container.appendChild(connector);
      }
    });
  }

  reset() {
    this.nodes.forEach(node => {
      const card = document.getElementById(`node-${node.id}`);
      const badge = document.getElementById(`badge-${node.id}`);
      const metric = document.getElementById(`metric-${node.id}`);
      if (card) card.className = "graph-node-card";
      if (badge) {
        badge.textContent = "WAITING";
        badge.style.color = "var(--text-dim)";
        badge.style.borderColor = "var(--border-color)";
      }
      if (metric) metric.innerHTML = "";
    });
  }

  setNodeActive(nodeId, statusText) {
    const card = document.getElementById(`node-${nodeId}`);
    const badge = document.getElementById(`badge-${nodeId}`);
    const desc = document.getElementById(`desc-${nodeId}`);
    if (card) card.className = "graph-node-card active";
    if (badge) {
      badge.textContent = "RUNNING";
      badge.style.color = "var(--accent-cyan)";
      badge.style.borderColor = "var(--accent-cyan)";
    }
    if (desc && statusText) desc.textContent = statusText;
  }

  setNodeCompleted(nodeId, statusText, metricText = "") {
    const card = document.getElementById(`node-${nodeId}`);
    const badge = document.getElementById(`badge-${nodeId}`);
    const desc = document.getElementById(`desc-${nodeId}`);
    const metric = document.getElementById(`metric-${nodeId}`);
    if (card) card.className = "graph-node-card completed";
    if (badge) {
      badge.textContent = "COMPLETED";
      badge.style.color = "var(--accent-emerald)";
      badge.style.borderColor = "rgba(16, 185, 129, 0.4)";
    }
    if (desc && statusText) desc.textContent = statusText;
    if (metric && metricText) {
      metric.innerHTML = `<span class="metric-pill">${metricText}</span>`;
    }
  }
}

window.agentGraph = new AgentGraphVisualizer("agent-graph-container");
