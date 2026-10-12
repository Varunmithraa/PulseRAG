class VoiceBriefingManager {
  constructor() {
    this.openBtn = document.getElementById("open-briefing-btn");
    this.modal = document.getElementById("briefing-modal");
    this.closeBtn = document.getElementById("close-briefing-modal-btn");
    this.playBtn = document.getElementById("briefing-play-btn");
    this.playIcon = document.getElementById("play-icon");
    this.stopBtn = document.getElementById("briefing-stop-btn");
    this.refreshBtn = document.getElementById("refresh-briefing-btn");
    this.followupBtn = document.getElementById("briefing-followup-btn");
    this.voiceSelect = document.getElementById("briefing-voice-select");
    this.equalizer = document.getElementById("briefing-equalizer");
    this.progressBar = document.getElementById("briefing-progress-bar");
    this.timeDisplay = document.getElementById("briefing-time-display");
    this.transcriptContainer = document.getElementById("briefing-transcript-container");
    this.pillarsContainer = document.getElementById("briefing-pillars-container");
    this.sourcesContainer = document.getElementById("briefing-sources-container");
    this.dateLabel = document.getElementById("briefing-date-label");
    this.wordCountLabel = document.getElementById("briefing-word-count");

    this.briefingData = null;
    this.isPlaying = false;
    this.isPaused = false;
    this.playbackRate = 1.0;
    this.selectedVoice = null;
    this.voices = [];
    this.currentUtterance = null;
    this.sentences = [];
    this.currentSentenceIdx = -1;
    this.progressInterval = null;
    this.startTime = 0;
    this.estimatedDuration = 60;

    this.init();
  }

  init() {
    this.bindEvents();
    this.initVoices();
  }

  initVoices() {
    const updateVoiceList = () => {
      if (!window.speechSynthesis) return;
      this.voices = window.speechSynthesis.getVoices();
      if (!this.voiceSelect) return;

      this.voiceSelect.innerHTML = "";
      
      // Filter for English voices first, then others
      const englishVoices = this.voices.filter(v => v.lang.startsWith("en"));
      const displayVoices = englishVoices.length > 0 ? englishVoices : this.voices;

      displayVoices.forEach((voice) => {
        const opt = document.createElement("option");
        opt.value = voice.name;
        opt.textContent = `${voice.name} (${voice.lang})`;
        if (voice.name.includes("Google") || voice.name.includes("Natural") || voice.default) {
          opt.selected = true;
          this.selectedVoice = voice;
        }
        this.voiceSelect.appendChild(opt);
      });

      if (!this.selectedVoice && displayVoices.length > 0) {
        this.selectedVoice = displayVoices[0];
      }
    };

    if (window.speechSynthesis) {
      updateVoiceList();
      window.speechSynthesis.onvoiceschanged = updateVoiceList;
    }
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

    if (this.playBtn) {
      this.playBtn.addEventListener("click", () => this.togglePlay());
    }

    if (this.stopBtn) {
      this.stopBtn.addEventListener("click", () => this.stopAudio());
    }

    if (this.refreshBtn) {
      this.refreshBtn.addEventListener("click", () => this.loadBriefing(true));
    }

    if (this.voiceSelect) {
      this.voiceSelect.addEventListener("change", (e) => {
        const found = this.voices.find(v => v.name === e.target.value);
        if (found) this.selectedVoice = found;
        if (this.isPlaying) {
          this.stopAudio();
          this.playAudio();
        }
      });
    }

    // Speed toggles
    document.querySelectorAll(".speed-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".speed-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.playbackRate = parseFloat(btn.getAttribute("data-speed")) || 1.0;
        if (this.isPlaying) {
          this.stopAudio();
          this.playAudio();
        }
      });
    });

    if (this.followupBtn) {
      this.followupBtn.addEventListener("click", () => this.discussWithAgent());
    }
  }

  async openModal() {
    if (!this.modal) return;
    this.modal.classList.add("open");
    if (!this.briefingData) {
      await this.loadBriefing(false);
    }
  }

  closeModal() {
    if (!this.modal) return;
    this.modal.classList.remove("open");
    // Pause audio when modal is closed
    if (this.isPlaying) {
      this.stopAudio();
    }
  }

  async loadBriefing(forceRefresh = false) {
    if (this.transcriptContainer) {
      this.transcriptContainer.innerHTML = `
        <div class="briefing-loading-state">
          <div class="spinner"></div>
          <span>Synthesizing live stream data into executive audio briefing...</span>
        </div>
      `;
    }

    try {
      const endpoint = forceRefresh ? "/api/briefing/generate" : "/api/briefing/latest";
      const method = forceRefresh ? "POST" : "GET";
      const res = await fetch(endpoint, { method });
      const data = await res.json();
      this.briefingData = data;
      this.renderBriefing(data);
    } catch (e) {
      console.error("Failed to load voice briefing:", e);
      if (this.transcriptContainer) {
        this.transcriptContainer.innerHTML = `
          <div style="color: var(--accent-rose); font-size: 0.82rem;">
            Failed to synthesize live briefing. Please ensure live feeds are active.
          </div>
        `;
      }
    }
  }

  renderBriefing(data) {
    if (!data) return;

    if (this.dateLabel) {
      this.dateLabel.textContent = `${data.date_formatted} • ~${data.estimated_duration_seconds}s Audio Duration`;
    }

    if (this.wordCountLabel) {
      this.wordCountLabel.textContent = `${data.word_count} Words`;
    }

    this.estimatedDuration = data.estimated_duration_seconds || 60;
    if (this.timeDisplay) {
      this.timeDisplay.textContent = `0:00 / ~${this.formatTime(this.estimatedDuration)}`;
    }

    // Process transcript into sentences for live highlighting
    const text = data.transcript || "";
    // Split into sentences using punctuation boundaries
    const rawSentences = text.match(/[^.!?]+[.!?]+(\s+|$)/g) || [text];
    this.sentences = rawSentences.map(s => s.trim()).filter(Boolean);

    if (this.transcriptContainer) {
      this.transcriptContainer.innerHTML = this.sentences.map((sent, idx) => `
        <span class="transcript-sentence" id="sentence-${idx}">${sent} </span>
      `).join("");
    }

    // Render Key Pillars Summary
    if (this.pillarsContainer && data.summary_points) {
      this.pillarsContainer.innerHTML = data.summary_points.map(p => `
        <div class="pillar-card">
          <span class="pillar-tag">${p.pillar}</span>
          <div class="pillar-headline">${p.headline}</div>
          <span class="pillar-source">Source: <strong>${p.source}</strong></span>
        </div>
      `).join("");
    }

    // Render Sources Cited
    if (this.sourcesContainer && data.sources_cited) {
      this.sourcesContainer.innerHTML = `
        <span style="font-size: 0.7rem; color: var(--text-dim); margin-right: 4px;">Verified Sources:</span>
        ${data.sources_cited.map(s => `<span class="briefing-source-tag">🔗 ${s}</span>`).join("")}
      `;
    }
  }

  togglePlay() {
    if (!window.speechSynthesis) {
      alert("Your browser does not support the Web Speech API.");
      return;
    }

    if (this.isPlaying) {
      if (this.isPaused) {
        window.speechSynthesis.resume();
        this.isPaused = false;
        this.updatePlayState(true);
      } else {
        window.speechSynthesis.pause();
        this.isPaused = true;
        this.updatePlayState(false, true);
      }
    } else {
      this.playAudio();
    }
  }

  playAudio() {
    if (!this.briefingData || !this.briefingData.transcript) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(this.briefingData.transcript);
    this.currentUtterance = utterance;

    if (this.selectedVoice) {
      utterance.voice = this.selectedVoice;
    }
    utterance.rate = this.playbackRate;
    utterance.pitch = 1.0;

    this.startTime = Date.now();
    this.isPlaying = true;
    this.isPaused = false;
    this.updatePlayState(true);

    if (this.stopBtn) this.stopBtn.disabled = false;

    // Sentence tracking simulation based on spoken characters & speech rate
    let totalChars = this.briefingData.transcript.length;
    let charOffsets = [];
    let cum = 0;
    this.sentences.forEach(s => {
      charOffsets.push({ start: cum, end: cum + s.length });
      cum += s.length + 1;
    });

    utterance.onboundary = (event) => {
      if (event.name === "sentence" || event.charIndex !== undefined) {
        const charIdx = event.charIndex;
        const sIndex = charOffsets.findIndex(o => charIdx >= o.start && charIdx <= o.end);
        if (sIndex !== -1 && sIndex !== this.currentSentenceIdx) {
          this.highlightSentence(sIndex);
        }
      }
    };

    // Fallback timer for highlighting and progress tracking
    const actualSeconds = this.estimatedDuration / this.playbackRate;
    const intervalMs = 150;
    let elapsed = 0;

    clearInterval(this.progressInterval);
    this.progressInterval = setInterval(() => {
      if (!this.isPlaying || this.isPaused) return;

      elapsed += intervalMs / 1000;
      const progress = Math.min(100, (elapsed / actualSeconds) * 100);
      if (this.progressBar) this.progressBar.style.width = `${progress}%`;
      if (this.timeDisplay) {
        this.timeDisplay.textContent = `${this.formatTime(elapsed)} / ${this.formatTime(actualSeconds)}`;
      }

      // Approximate sentence highlighting if boundary events are not fired by the browser engine
      if (this.currentSentenceIdx === -1 || (elapsed / actualSeconds) > (this.currentSentenceIdx + 1) / this.sentences.length) {
        const approxIdx = Math.min(this.sentences.length - 1, Math.floor((elapsed / actualSeconds) * this.sentences.length));
        this.highlightSentence(approxIdx);
      }
    }, intervalMs);

    utterance.onend = () => {
      this.stopAudio();
      if (this.progressBar) this.progressBar.style.width = "100%";
      this.clearHighlight();
    };

    utterance.onerror = (e) => {
      console.warn("Speech error:", e);
      this.stopAudio();
    };

    window.speechSynthesis.speak(utterance);
  }

  stopAudio() {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    clearInterval(this.progressInterval);
    this.isPlaying = false;
    this.isPaused = false;
    this.updatePlayState(false);
    if (this.stopBtn) this.stopBtn.disabled = true;
    if (this.progressBar) this.progressBar.style.width = "0%";
    if (this.timeDisplay) {
      this.timeDisplay.textContent = `0:00 / ~${this.formatTime(this.estimatedDuration / this.playbackRate)}`;
    }
    this.clearHighlight();
  }

  updatePlayState(active, paused = false) {
    if (this.playIcon) {
      this.playIcon.textContent = active ? "⏸" : "▶";
    }

    if (this.equalizer) {
      if (active) {
        this.equalizer.classList.add("is-playing");
      } else {
        this.equalizer.classList.remove("is-playing");
      }
    }

    if (this.openBtn) {
      if (active) {
        this.openBtn.classList.add("is-playing");
      } else {
        this.openBtn.classList.remove("is-playing");
      }
    }
  }

  highlightSentence(idx) {
    this.currentSentenceIdx = idx;
    this.clearHighlight();
    const el = document.getElementById(`sentence-${idx}`);
    if (el) {
      el.classList.add("active-sentence");
      // Auto-scroll transcript to active sentence
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  clearHighlight() {
    document.querySelectorAll(".transcript-sentence").forEach(el => {
      el.classList.remove("active-sentence");
    });
  }

  formatTime(secs) {
    const s = Math.round(secs);
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${m}:${rem < 10 ? "0" : ""}${rem}`;
  }

  discussWithAgent() {
    this.closeModal();

    const query = "Provide an in-depth strategic analysis and risk assessment based on the latest executive live briefing.";
    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    const appContainer = document.getElementById("app-container");

    if (appContainer && appContainer.classList.contains("sidebar-collapsed")) {
      appContainer.classList.remove("sidebar-collapsed");
    }

    const graphTabBtn = document.querySelector('.tab-btn[data-tab="tab-graph"]');
    if (graphTabBtn) graphTabBtn.click();

    if (chatInput && sendBtn) {
      chatInput.value = query;
      chatInput.focus();
      sendBtn.click();
    }
  }
}

window.voiceBriefing = new VoiceBriefingManager();
