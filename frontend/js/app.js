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

  // Draggable Sidebar Resizer & Expand Toggle
  const sidebarPanel = document.getElementById("sidebar-panel");
  const sidebarResizer = document.getElementById("sidebar-resizer");
  const panelExpandBtn = document.getElementById("panel-expand-btn");
  const panelExpandIcon = document.getElementById("panel-expand-icon");

  // Restore saved width
  const savedWidth = localStorage.getItem("pulserag_sidebar_width");
  if (savedWidth && sidebarPanel) {
    sidebarPanel.style.setProperty("--sidebar-width", `${savedWidth}px`);
    sidebarPanel.style.width = `${savedWidth}px`;
    if (parseInt(savedWidth, 10) > 520) {
      sidebarPanel.classList.add("is-expanded");
      if (panelExpandIcon) panelExpandIcon.textContent = "⤡";
    }
  }

  // Dragging to resize
  if (sidebarResizer && sidebarPanel) {
    let isDragging = false;
    let startX = 0;
    let startWidth = 0;

    sidebarResizer.addEventListener("mousedown", (e) => {
      isDragging = true;
      sidebarResizer.classList.add("is-dragging");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      startX = e.clientX;
      startWidth = sidebarPanel.getBoundingClientRect().width;
    });

    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      const dx = startX - e.clientX;
      const newWidth = Math.max(320, Math.min(window.innerWidth * 0.8, startWidth + dx));
      sidebarPanel.style.setProperty("--sidebar-width", `${newWidth}px`);
      sidebarPanel.style.width = `${newWidth}px`;
      if (newWidth > 520) {
        sidebarPanel.classList.add("is-expanded");
        if (panelExpandIcon) panelExpandIcon.textContent = "⤡";
      } else {
        sidebarPanel.classList.remove("is-expanded");
        if (panelExpandIcon) panelExpandIcon.textContent = "⤢";
      }
      localStorage.setItem("pulserag_sidebar_width", Math.round(newWidth));
    });

    document.addEventListener("mouseup", () => {
      if (isDragging) {
        isDragging = false;
        sidebarResizer.classList.remove("is-dragging");
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    });
  }

  // 1-Click Expand / Maximize Toggle
  if (panelExpandBtn && sidebarPanel) {
    panelExpandBtn.addEventListener("click", () => {
      const currentWidth = sidebarPanel.getBoundingClientRect().width;
      if (currentWidth < 520) {
        // Expand to wide 640px
        sidebarPanel.style.setProperty("--sidebar-width", "640px");
        sidebarPanel.style.width = "640px";
        sidebarPanel.classList.add("is-expanded");
        if (panelExpandIcon) panelExpandIcon.textContent = "⤡";
        panelExpandBtn.title = "Collapse to Standard Width";
        localStorage.setItem("pulserag_sidebar_width", "640");
      } else {
        // Collapse back to standard 390px
        sidebarPanel.style.setProperty("--sidebar-width", "390px");
        sidebarPanel.style.width = "390px";
        sidebarPanel.classList.remove("is-expanded");
        if (panelExpandIcon) panelExpandIcon.textContent = "⤢";
        panelExpandBtn.title = "Expand / Maximize Panel Width";
        localStorage.setItem("pulserag_sidebar_width", "390");
      }
    });
  }

  // Keyboard shortcut: Ctrl+B or Cmd+B
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
      e.preventDefault();
      toggleSidebar();
    }
  });

  // Light / Dark Theme Switcher Logic
  const themeToggleBtn = document.getElementById("theme-toggle-btn");
  const themeIcon = document.getElementById("theme-icon");

  function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    if (themeIcon) {
      themeIcon.textContent = theme === "light" ? "☀️" : "🌙";
    }
    if (themeToggleBtn) {
      themeToggleBtn.title = theme === "light" ? "Switch to Dark Mode" : "Switch to Light Mode";
    }
    localStorage.setItem("pulserag_theme", theme);
  }

  function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
    setTheme(currentTheme === "light" ? "dark" : "light");
  }

  // Restore saved theme (default is dark)
  const savedTheme = localStorage.getItem("pulserag_theme") || "dark";
  setTheme(savedTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", toggleTheme);
  }
  
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
      const feedsBadge = document.getElementById("feeds-count-badge");
      if (feedsBadge && data.active_feeds_count !== undefined) {
        feedsBadge.textContent = `${data.active_feeds_count} Feeds`;
      }
      const alertsBadge = document.getElementById("alerts-count-badge");
      if (alertsBadge && data.unread_alerts_count !== undefined) {
        alertsBadge.textContent = `${data.unread_alerts_count} Alerts`;
      }
    } catch (e) {
      console.warn("Could not fetch status:", e);
    }
  }
  checkStatus();

  // Chat Mode Management: Quick Answer vs Deep Research
  let currentChatMode = "quick";
  const modeQuickBtn = document.getElementById("mode-quick-btn");
  const modeDeepBtn = document.getElementById("mode-deep-btn");
  const modeHintText = document.getElementById("mode-hint-text");
  const mainInputBox = document.getElementById("main-input-box");

  function setChatMode(mode) {
    currentChatMode = mode;
    if (mode === "deep_research") {
      if (modeQuickBtn) modeQuickBtn.classList.remove("active");
      if (modeDeepBtn) modeDeepBtn.classList.add("active");
      if (modeHintText) modeHintText.textContent = "Autonomous 3-vector multi-hop decomposition + structured intelligence dossier";
      if (mainInputBox) mainInputBox.classList.add("mode-deep-active");
      if (chatInput) chatInput.placeholder = "Enter research topic or market question for deep multi-hop dossier...";
    } else {
      if (modeDeepBtn) modeDeepBtn.classList.remove("active");
      if (modeQuickBtn) modeQuickBtn.classList.add("active");
      if (modeHintText) modeHintText.textContent = "Standard CRAG routing & temporal recency search";
      if (mainInputBox) mainInputBox.classList.remove("mode-deep-active");
      if (chatInput) chatInput.placeholder = "Ask a real-time question or update your tracked interests...";
    }
  }

  if (modeQuickBtn) modeQuickBtn.addEventListener("click", () => setChatMode("quick"));
  if (modeDeepBtn) modeDeepBtn.addEventListener("click", () => setChatMode("deep_research"));

  // Suggestion Pills
  document.querySelectorAll(".suggestion-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      const mode = pill.getAttribute("data-mode");
      if (mode === "deep_research") {
        setChatMode("deep_research");
        chatInput.value = pill.textContent.replace("🔬 Deep Research: ", "").trim();
      } else {
        chatInput.value = pill.textContent.trim();
      }
      chatInput.focus();
    });
  });

  // Send Message & Handle Streaming
  async function handleSend() {
    const query = chatInput.value.trim();
    if (!query) return;

    const requestMode = currentChatMode;
    chatInput.value = "";
    sendBtn.disabled = true;

    // Append User Message with Mode Indicator
    appendMessage("user", query, requestMode);

    // Reset Agent Graph and switch to graph tab
    if (window.agentGraph) window.agentGraph.reset();
    const graphTabBtn = document.querySelector('[data-tab="tab-graph"]');
    if (graphTabBtn) graphTabBtn.click();

    // Create Assistant Message Placeholder
    const assistantBubble = appendMessage("assistant", "", requestMode);
    let fullResponseText = "";
    let researchPlanRendered = false;

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          user_id: "default_user",
          session_id: "session_01",
          mode: requestMode
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
            } else if (ev.type === "research_plan" && !researchPlanRendered) {
              researchPlanRendered = true;
              const planBox = document.createElement("div");
              planBox.className = "research-plan-preview";
              const vectorsHtml = (ev.plan.vectors || []).map(v => 
                `<span class="plan-vector-pill" title="${v.focus}">🎯 ${v.name}</span>`
              ).join(" ");
              planBox.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                  <strong style="color: #c084fc; font-size: 0.78rem;">🔬 Autonomous Multi-Hop Plan</strong>
                  <span style="font-size: 0.68rem; color: var(--text-dim);">${(ev.plan.vectors || []).length} Investigative Vectors</span>
                </div>
                <div style="color: var(--text-muted); font-size: 0.74rem; margin-bottom: 6px;">${ev.plan.executive_scope || ""}</div>
                <div>${vectorsHtml}</div>
              `;
              assistantBubble.prepend(planBox);
            } else if (ev.type === "token") {
              fullResponseText += ev.content;
              const textContainer = assistantBubble.querySelector(".response-body-text") || assistantBubble;
              textContainer.innerHTML = formatMarkdown(fullResponseText);
              chatMessages.scrollTop = chatMessages.scrollHeight;
            } else if (ev.type === "done") {
              // If Deep Research, attach interactive Export & Copy toolbar
              if (ev.mode === "deep_research") {
                const dossierHeader = document.createElement("div");
                dossierHeader.className = "dossier-banner";
                dossierHeader.innerHTML = `
                  <div class="dossier-badge">📑 Executive Deep Research Dossier</div>
                  <div class="dossier-actions">
                    <button class="dossier-action-btn" id="export-dossier-btn" title="Download formatted Markdown dossier">
                      <span>📄</span> Export Dossier (.md)
                    </button>
                    <button class="dossier-action-btn" id="copy-dossier-btn" title="Copy report to clipboard">
                      <span>📋</span> Copy Report
                    </button>
                  </div>
                `;
                assistantBubble.insertBefore(dossierHeader, assistantBubble.firstChild);

                const exportBtn = dossierHeader.querySelector("#export-dossier-btn");
                if (exportBtn) {
                  exportBtn.onclick = () => {
                    const blob = new Blob([fullResponseText], { type: "text/markdown;charset=utf-8" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    const safeTopic = (ev.dossier_title || "intelligence-dossier").toLowerCase().replace(/[^a-z0-9]/g, "-");
                    a.href = url;
                    a.download = `PulseRAG-Dossier-${safeTopic}.md`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                  };
                }

                const copyBtn = dossierHeader.querySelector("#copy-dossier-btn");
                if (copyBtn) {
                  copyBtn.onclick = async () => {
                    try {
                      await navigator.clipboard.writeText(fullResponseText);
                      copyBtn.innerHTML = `<span>✓</span> Copied!`;
                      setTimeout(() => { copyBtn.innerHTML = `<span>📋</span> Copy Report`; }, 2500);
                    } catch (err) {
                      alert("Could not copy: " + err);
                    }
                  };
                }
              }

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

  function appendMessage(role, text, mode = "quick") {
    const wrapper = document.createElement("div");
    wrapper.className = `message-wrapper ${role}`;
    
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    if (role === "user" && mode === "deep_research") {
      bubble.innerHTML = `<span style="font-size: 0.68rem; font-weight: 700; color: #c084fc; background: rgba(168, 85, 247, 0.15); border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 4px; padding: 2px 6px; margin-right: 6px;">🔬 DEEP RESEARCH</span> ${text}`;
    } else if (role === "assistant" && mode === "deep_research") {
      const textContainer = document.createElement("div");
      textContainer.className = "response-body-text";
      textContainer.innerHTML = formatMarkdown(text);
      bubble.appendChild(textContainer);
    } else {
      bubble.innerHTML = formatMarkdown(text);
    }
    
    wrapper.appendChild(bubble);
    chatMessages.appendChild(wrapper);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return bubble;
  }

  function formatMarkdown(text) {
    if (!text) return "";
    let html = text
      .replace(/^# (.*?)$/gm, '<h1 style="font-size: 1.25rem; color: #c084fc; margin: 12px 0 6px 0;">$1</h1>')
      .replace(/^## (.*?)$/gm, '<h2 style="font-size: 1.05rem; color: var(--text-main); margin: 14px 0 6px 0; border-bottom: 1px solid var(--border-color); padding-bottom: 4px;">$1</h2>')
      .replace(/^### (.*?)$/gm, '<h3 style="font-size: 0.92rem; color: var(--accent-cyan); margin: 10px 0 4px 0;">$1</h3>')
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/^---$/gm, "<hr>")
      .replace(/\n- (.*?)/g, "<br>• $1");

    // Markdown Table Parser
    if (html.includes("|")) {
      html = html.replace(/((?:\|[^\n]+\|\r?\n)+)/g, (match) => {
        const rows = match.trim().split("\n");
        if (rows.length < 2) return match;
        let tableHtml = '<div style="overflow-x: auto; margin: 12px 0;"><table class="dossier-table" style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">';
        rows.forEach((row, idx) => {
          if (row.includes("---")) return; // skip markdown divider
          const cells = row.split("|").filter((c, i, arr) => i > 0 && i < arr.length - 1);
          const tag = idx === 0 ? "th" : "td";
          tableHtml += "<tr>" + cells.map(c => `<${tag} style="border: 1px solid var(--border-color); padding: 6px 10px;">${c.trim()}</${tag}>`).join("") + "</tr>";
        });
        tableHtml += "</table></div>";
        return tableHtml;
      });
    }

    html = html.replace(/\n\n/g, "<br><br>");
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
