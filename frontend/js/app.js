document.addEventListener("DOMContentLoaded", () => {
  const chatMessages = document.getElementById("chat-messages");
  const chatInput = document.getElementById("chat-input");
  const sendBtn = document.getElementById("send-btn");
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");
  const appContainer = document.getElementById("app-container");
  const toggleSidebarBtn = document.getElementById("toggle-sidebar-btn");
  const floatingSidebarBtn = document.getElementById("floating-sidebar-btn");

  // Sidebar Toggle Logic
  function setSidebarState(collapsed) {
    if (!appContainer) return;
    if (collapsed) {
      appContainer.classList.add("sidebar-collapsed");
      if (toggleSidebarBtn) {
        toggleSidebarBtn.classList.add("collapsed");
        toggleSidebarBtn.title = "Show Intelligence Sidebar (Ctrl+B)";
      }
    } else {
      appContainer.classList.remove("sidebar-collapsed");
      if (toggleSidebarBtn) {
        toggleSidebarBtn.classList.remove("collapsed");
        toggleSidebarBtn.title = "Hide Intelligence Sidebar (Ctrl+B)";
      }
    }
    localStorage.setItem("pulserag_sidebar_collapsed", collapsed ? "true" : "false");
  }

  function toggleSidebar() {
    const isCurrentlyCollapsed = appContainer.classList.contains("sidebar-collapsed");
    setSidebarState(!isCurrentlyCollapsed);
  }

  // Restore saved state (default is open)
  const savedState = localStorage.getItem("pulserag_sidebar_collapsed");
  if (savedState === "true") {
    setSidebarState(true);
  } else {
    setSidebarState(false);
  }

  if (toggleSidebarBtn) {
    toggleSidebarBtn.addEventListener("click", toggleSidebar);
  }
  if (floatingSidebarBtn) {
    floatingSidebarBtn.addEventListener("click", () => setSidebarState(false));
  }

  // Keyboard shortcut: Ctrl+B or Cmd+B
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
      e.preventDefault();
      toggleSidebar();
    }
  });
  
  // Tab Switching
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      // Auto-open sidebar if collapsed when clicking a tab
      if (appContainer && appContainer.classList.contains("sidebar-collapsed")) {
        setSidebarState(false);
      }
      tabBtns.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add("active");
    });
  });

  // Check system status
  async function checkStatus() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      const dot = document.getElementById("status-dot");
      const text = document.getElementById("status-text");
      if (data.gemini_api_configured) {
        if (dot) dot.style.background = "var(--accent-emerald)";
        if (text) text.textContent = `Online • ${data.model}`;
      } else {
        if (dot) dot.style.background = "var(--accent-amber)";
        if (text) text.textContent = `Local Fallback • Set GEMINI_API_KEY in .env`;
      }
    } catch (e) {
      console.warn("Could not fetch status:", e);
    }
  }
  checkStatus();

  // Suggestion Pills
  document.querySelectorAll(".suggestion-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      chatInput.value = pill.textContent.trim();
      chatInput.focus();
    });
  });

  // Send Message & Handle Streaming
  async function handleSend() {
    const query = chatInput.value.trim();
    if (!query) return;

    chatInput.value = "";
    sendBtn.disabled = true;

    // Append User Message
    appendMessage("user", query);

    // Reset Agent Graph and switch to graph tab
    if (window.agentGraph) window.agentGraph.reset();
    const graphTabBtn = document.querySelector('[data-tab="tab-graph"]');
    if (graphTabBtn) graphTabBtn.click();

    // Create Assistant Message Placeholder
    const assistantBubble = appendMessage("assistant", "");
    let fullResponseText = "";

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          user_id: "default_user",
          session_id: "session_01"
        })
      });

      if (!response.body) {
        assistantBubble.textContent = "Error: No response stream received.";
        sendBtn.disabled = false;
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop(); // keep last unfinished line

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.replace("data: ", "").trim();
          if (!jsonStr) continue;

          try {
            const ev = JSON.parse(jsonStr);

            if (ev.type === "step") {
              if (window.agentGraph) {
                window.agentGraph.setNodeActive(ev.node, ev.status);
              }
            } else if (ev.type === "step_done") {
              if (window.agentGraph) {
                const metric = ev.summary ? `${ev.summary.passed_count} Verified` : (ev.count ? `${ev.count} Chunks` : "");
                window.agentGraph.setNodeCompleted(ev.node, ev.status, metric);
              }
            } else if (ev.type === "token") {
              fullResponseText += ev.content;
              assistantBubble.innerHTML = formatMarkdown(fullResponseText);
              chatMessages.scrollTop = chatMessages.scrollHeight;
            } else if (ev.type === "done") {
              // Append citations
              if (ev.citations && ev.citations.length > 0) {
                const citationsEl = document.createElement("div");
                citationsEl.className = "citations-wrapper";
                ev.citations.forEach(c => {
                  const chip = document.createElement("span");
                  chip.className = "citation-chip";
                  chip.textContent = `🔗 ${c.label}`;
                  chip.title = `${c.title}\n${c.content}`;
                  chip.onclick = () => alert(`[Source Evidence]\n\nSource: ${c.label}\nTitle: ${c.title}\n\nContent:\n${c.content}`);
                  citationsEl.appendChild(chip);
                });
                assistantBubble.appendChild(citationsEl);
              }
              // Refresh memory viewer in case facts were learned
              if (window.memoryViewer) window.memoryViewer.fetchMemories();
            } else if (ev.type === "error") {
              assistantBubble.innerHTML += `<div style="color: var(--accent-rose); margin-top: 8px;">Error: ${ev.message}</div>`;
            }
          } catch (err) {
            console.error("Error parsing event:", err, jsonStr);
          }
        }
      }
    } catch (err) {
      assistantBubble.textContent = `Network / Execution Error: ${err}`;
    } finally {
      sendBtn.disabled = false;
      chatInput.focus();
    }
  }

  function appendMessage(role, text) {
    const wrapper = document.createElement("div");
    wrapper.className = `message-wrapper ${role}`;
    
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.innerHTML = formatMarkdown(text);
    
    wrapper.appendChild(bubble);
    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return bubble;
  }

  function formatMarkdown(text) {
    if (!text) return "";
    let html = text
      .replace(/### (.*?)\n/g, "<h3>$1</h3>")
      .replace(/## (.*?)\n/g, "<h2>$1</h2>")
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\n\n/g, "<br><br>")
      .replace(/\n- (.*?)/g, "<br>• $1");
    return html;
  }

  sendBtn.addEventListener("click", handleSend);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Inject Modal Handling
  const injectModal = document.getElementById("inject-modal");
  const openInjectBtn = document.getElementById("open-inject-btn");
  const closeInjectBtn = document.getElementById("close-inject-btn");
  const submitInjectBtn = document.getElementById("submit-inject-btn");

  if (openInjectBtn) openInjectBtn.addEventListener("click", () => injectModal.classList.add("open"));
  if (closeInjectBtn) closeInjectBtn.addEventListener("click", () => injectModal.classList.remove("open"));

  if (submitInjectBtn) {
    submitInjectBtn.addEventListener("click", async () => {
      const title = document.getElementById("inject-title").value.trim();
      const content = document.getElementById("inject-content").value.trim();
      const tickers = document.getElementById("inject-tickers").value.trim();
      if (!title || !content) {
        alert("Please provide both title and content!");
        return;
      }
      await window.liveRadar.injectCustomEvent(title, content, "Live Radar Manual", "Breaking News", tickers);
      injectModal.classList.remove("open");
      document.getElementById("inject-title").value = "";
      document.getElementById("inject-content").value = "";
      document.getElementById("inject-tickers").value = "";
    });
  }

  // Add Memory Modal Handling
  const addMemoryModal = document.getElementById("add-memory-modal");
  const openMemoryBtn = document.getElementById("open-memory-btn");
  const closeMemoryBtn = document.getElementById("close-memory-btn");
  const submitMemoryBtn = document.getElementById("submit-memory-btn");

  if (openMemoryBtn) openMemoryBtn.addEventListener("click", () => addMemoryModal.classList.add("open"));
  if (closeMemoryBtn) closeMemoryBtn.addEventListener("click", () => addMemoryModal.classList.remove("open"));

  if (submitMemoryBtn) {
    submitMemoryBtn.addEventListener("click", async () => {
      const cat = document.getElementById("memory-category").value.trim();
      const key = document.getElementById("memory-key").value.trim();
      const fact = document.getElementById("memory-fact").value.trim();
      if (!key || !fact) {
        alert("Please provide both Entity Key and Fact Content!");
        return;
      }
      await window.memoryViewer.addFact(cat, key, fact);
      addMemoryModal.classList.remove("open");
      document.getElementById("memory-key").value = "";
      document.getElementById("memory-fact").value = "";
    });
  }
});
