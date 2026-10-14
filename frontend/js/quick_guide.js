class QuickGuideManager {
  constructor() {
    this.openBtn = document.getElementById("open-guide-btn");
    this.modal = document.getElementById("guide-modal");
    this.closeBtn = document.getElementById("close-guide-modal-btn");
    this.promptPills = document.querySelectorAll(".guide-prompt-pill");

    this.init();
  }

  init() {
    this.bindEvents();
    this.checkFirstTimeVisit();
  }

  bindEvents() {
    if (this.openBtn) {
      this.openBtn.addEventListener("click", () => this.openModal());
    }

    if (this.closeBtn) {
      this.closeBtn.addEventListener("click", () => this.closeModal());
    }

    if (this.modal) {
      this.modal.addEventListener("click", (e) => {
        if (e.target === this.modal) this.closeModal();
      });
    }

    // 1-Click Starter Prompts
    this.promptPills.forEach(pill => {
      pill.addEventListener("click", () => {
        const promptText = pill.getAttribute("data-prompt");
        const mode = pill.getAttribute("data-mode") || "quick";
        if (promptText) {
          this.runStarterPrompt(promptText, mode);
        }
      });
    });

    const footerCloseBtn = document.getElementById("footer-close-guide-btn");
    if (footerCloseBtn) {
      footerCloseBtn.addEventListener("click", () => this.closeModal());
    }

    // Keyboard shortcut: Press '?' to toggle guide, 'Escape' to close
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.modal && this.modal.classList.contains("open")) {
        this.closeModal();
      } else if (e.key === "?" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
        if (this.modal && this.modal.classList.contains("open")) {
          this.closeModal();
        } else {
          this.openModal();
        }
      }
    });
  }

  openModal() {
    if (!this.modal) return;
    this.modal.classList.add("open");
    localStorage.setItem("pulserag_guide_viewed", "true");
    if (this.openBtn) {
      this.openBtn.classList.remove("has-glow");
    }
  }

  closeModal() {
    if (!this.modal) return;
    this.modal.classList.remove("open");
  }

  checkFirstTimeVisit() {
    const viewed = localStorage.getItem("pulserag_guide_viewed");
    if (!viewed && this.openBtn) {
      // Add subtle glow to Guide button on first visit to help new users discover it
      this.openBtn.classList.add("has-glow");
    }
  }

  runStarterPrompt(promptText, mode = "quick") {
    this.closeModal();

    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    const appContainer = document.getElementById("app-container");
    const modeDeepBtn = document.getElementById("mode-deep-btn");
    const modeQuickBtn = document.getElementById("mode-quick-btn");

    if (mode === "deep_research" && modeDeepBtn) {
      modeDeepBtn.click();
    } else if (modeQuickBtn) {
      modeQuickBtn.click();
    }

    // Auto-expand sidebar if collapsed
    if (appContainer && appContainer.classList.contains("sidebar-collapsed")) {
      appContainer.classList.remove("sidebar-collapsed");
    }

    // Switch right panel to Graph tab to observe real-time LangGraph execution
    const graphTabBtn = document.querySelector('.tab-btn[data-tab="tab-graph"]');
    if (graphTabBtn) graphTabBtn.click();

    if (chatInput && sendBtn) {
      chatInput.value = promptText;
      chatInput.focus();
      sendBtn.click();
    }
  }
}

window.quickGuide = new QuickGuideManager();
