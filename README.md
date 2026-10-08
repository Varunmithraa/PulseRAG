# ⚡ ChronosRAG: Autonomous Agentic RAG Platform

> **Real-Time Temporal Stream Ingestion & Dual-Tier Cognitive Memory**  
> Built with **LangGraph**, **FastAPI**, **Google GenAI SDK (Gemini)**, **ChromaDB**, and **SQLite**.

---

## 🌟 Overview

**ChronosRAG** is an enterprise-grade Agentic Retrieval-Augmented Generation (RAG) platform designed for high-velocity intelligence environments (such as financial markets and real-time technology ecosystems).

Traditional RAG systems fail when dealing with real-time events because static vector indexes have no concept of time, retrieve blindly without relevance verification, and suffer from session amnesia. ChronosRAG solves all three issues:

1. **Temporal Live-Stream Ingestion**: Background workers continuously ingest RSS, breaking news, and market events into an in-memory sliding buffer with **mathematical recency-decay scoring** ($Score = \alpha \cdot \text{Similarity} + (1-\alpha) \cdot e^{-\lambda \Delta t}$).
2. **Corrective RAG (CRAG) & Autonomous Routing**: An autonomous LangGraph state machine evaluates query intent, retrieves candidate chunks, grades chunk relevance, and prunes noisy or hallucinated snippets before synthesis.
3. **Dual-Tier Cognitive Memory**:
   - **Episodic Working Memory**: Multi-turn dialogue history and agent execution trace checkpoints.
   - **Semantic Long-Term Memory**: Persistent user profile facts, watchlists, and constraints stored in SQLite with vector associative recall.
4. **Full Observability & Interactive Dashboard**: Dark-mode glassmorphic single-page app displaying real-time LangGraph node execution transitions, live stream ticker radar, and interactive memory inspection.

---

## 🏗️ System Architecture

```
                                  ┌───────────────────────────────┐
                                  │   User Query + Interaction    │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                     ┌────────────────────────────────────────────────────────┐
                     │          Autonomous Cognitive Orchestrator             │
                     │  - Query Decomposition & Intent Routing                │
                     │  - Corrective RAG (CRAG) Relevance Grading             │
                     └───────┬────────────────────┬────────────────────┬──────┘
                             │                    │                    │
              ┌──────────────┴─────────┐ ┌────────┴────────┐ ┌─────────┴──────────────┐
              │   Live Stream Engine   │ │ Semantic KB DB  │ │ Dual-Tier Memory System│
              │  - Real-Time RSS/Feeds │ │ - Historical KB │ │ - Episodic Working Mem │
              │  - Recency-Decay Math  │ │ - ChromaDB HNSW │ │ - Long-Term Entity Mem │
              │  - Sliding Ring Buffer │ │ - Vector Search │ │ - SQLite + Embeddings  │
              └────────────────────────┘ └─────────────────┘ └────────────────────────┘
```

---

## 📁 Repository Structure

```
pulserag-agentic-rag/
├── ARCHITECTURE.md              # In-depth architectural & design specification
├── README.md                    # Project documentation & resume guide
├── requirements.txt             # Python dependencies
├── start.py                     # Single-command application launcher
├── .env.example                 # Environment variable template
├── backend/
│   └── app/
│       ├── main.py              # FastAPI server (REST, SSE streaming endpoints)
│       ├── config.py            # System configuration & environment settings
│       ├── agent/
│       │   ├── orchestrator.py  # LangGraph state machine & streaming generator
│       │   ├── evaluator.py     # Corrective RAG (CRAG) document relevance grader
│       │   ├── tools.py         # Retrieval & memory tools
│       │   └── prompts.py       # System instructions & JSON schemas
│       ├── memory/
│       │   ├── memory_manager.py# Unified memory controller
│       │   ├── episodic.py      # Session working memory & traces
│       │   └── semantic.py      # Long-term SQLite & vector fact store
│       ├── stream/
│       │   ├── live_buffer.py   # In-memory sliding buffer with Time-Decay Math
│       │   └── ingestion_engine.py # RSS fetcher & live stream emitter
│       └── storage/
│           ├── database.py      # SQLite relational persistence
│           └── vector_store.py  # ChromaDB persistent vector collections
├── frontend/
│   ├── index.html               # Glassmorphic single-page dashboard
│   ├── css/styles.css           # Modern dark-mode styling tokens
│   └── js/
│       ├── app.js               # SSE chat coordinator & modal controls
│       ├── agent_graph.js       # Real-time visual LangGraph state visualizer
│       ├── live_radar.js        # Live stream radar & event injector
│       └── memory_viewer.js     # SQLite memory inspector & manager
└── sample_data/
    └── seed_knowledge.json      # Foundational semiconductor & macro documents
```

---

## 🚀 Quickstart Guide

### 1. Activate the Virtual Environment
```bash
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
```

### 2. Configure Your API Key (Optional but Recommended)
Copy `.env.example` to `.env` and insert your free Gemini API Key:
```bash
copy .env.example .env
```
*(Get a free key from [Google AI Studio](https://aistudio.google.com/)). If no key is set, the system automatically falls back to offline heuristic routing and intelligence synthesis!*

### 3. Launch the Application
```bash
python start.py
```
Open **`http://127.0.0.1:8000`** in your browser.

---

## 💼 Resume Feature Bullet Points

You can feature this project on your resume as follows:

> **ChronosRAG — Autonomous Agentic RAG Platform over Live Streams & Cognitive Memory**
> - Architected a production-grade Agentic RAG system using **Python (FastAPI, Google GenAI SDK)**, **LangGraph**, **ChromaDB**, and **SQLite** implementing Corrective RAG (CRAG) with autonomous document relevance grading.
> - Engineered an event-driven **Live Stream Ingestion Engine** with a mathematical **recency-decay ranking algorithm**, enabling temporal retrieval where breaking news dynamically prioritizes over stale vector embeddings.
> - Developed a **Dual-Tier Cognitive Memory System** (Episodic session buffer + Semantic Long-Term SQLite store with vector embeddings) providing personalized, entity-aware recall across sessions.
> - Built a real-time glassmorphic dashboard utilizing **Server-Sent Events (SSE)** for token streaming, live LangGraph state machine visualization, live feed radar, and memory inspection.
