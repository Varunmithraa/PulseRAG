# PulseRAG: Autonomous Agentic RAG Platform

> **System Architecture & Design Specification**  
> *Agentic Retrieval-Augmented Generation over Real-Time Temporal Data Streams and Dual-Tier Cognitive Memory*

---

## 1. Executive Summary

**PulseRAG** is an enterprise-grade, production-oriented Agentic RAG system designed for high-velocity environments (such as financial market intelligence, tech ecosystem monitoring, or live DevOps incident analysis). 

Unlike conventional static RAG architectures that simply perform vector similarity lookups over static PDF dumps, PulseRAG integrates:
1. **Adaptive & Corrective RAG (CRAG)**: Dynamic intent routing, query decomposition, document relevance grading, and self-reflection loops.
2. **Temporal Live-Stream Ingestion**: Event-driven real-time stream ingestion with **recency-decay relevance scoring** ($Score = \alpha \cdot \text{Similarity} + (1-\alpha) \cdot e^{-\lambda \Delta t}$).
3. **Dual-Tier Cognitive Memory System**:
   - **Episodic Memory**: Working memory capturing multi-turn dialogue, tool call execution traces, and agent reflection states.
   - **Semantic / Entity Long-Term Memory**: Automatic extraction of user preferences, tracked entities, and historical facts stored in SQLite with semantic vector embeddings.
4. **Full Observability & Glassmorphic Dashboard**: Real-time visualization of agent reasoning steps (Thought ➔ Action ➔ Observation ➔ Reflection), live feed event radar, and memory inspector.

---

## 2. High-Level Architecture Diagram

```
+----------------------------------------------------------------------------------------------------+
|                                    INTERACTIVE USER DASHBOARD                                      |
|  [ Real-Time Stream Radar ]   [ Grounded Chat + Citations ]   [ Agent Reasoning & Memory Inspector]|
+--------------------------------------------------+-------------------------------------------------+
                                                   |
                                                   | WebSocket / Server-Sent Events (SSE) / REST
                                                   v
+----------------------------------------------------------------------------------------------------+
|                                      FASTAPI BACKEND SERVICE                                       |
+--------------------------------------------------+-------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
|                                AUTONOMOUS COGNITIVE AGENT CONTROLLER                               |
|                                                                                                    |
|   1. Query Analyzer & Intent Router                                                                |
|      - Is retrieval needed? Which knowledge sources are relevant?                                  |
|                                                                                                    |
|   2. Multi-Step Execution Loop                                                                     |
|      - Step A: Tool Invocation (Parallel or Sequential)                                            |
|      - Step B: Document Relevance Grading & Filtering (Corrective RAG)                             |
|      - Step C: Self-Reflection & Hallucination Check                                               |
|      - Step D: Grounded Answer Generation with Explicit Citations                                  |
+----------------------+---------------------------+--------------------------+----------------------+
                       |                           |                          |
                       v                           v                          v
+-------------------------------+ +--------------------------------+ +-------------------------------+
|     LIVE STREAM ENGINE        | |   HISTORICAL VECTOR STORE      | |    DUAL-TIER MEMORY SYSTEM    |
|                               | |                                | |                               |
| - Continuous Ingestion Worker | | - ChromaDB (HNSW Index)        | | 1. Episodic Memory:           |
| - Sliding Buffer Window       | | - Semantic Knowledge Base      | |    - Session turn histories   |
| - Temporal Recency-Decay      | | - Chunk metadata preservation  | |    - Agent execution traces   |
| - Live RSS / Market Feeds     | | - Dense vector embeddings      | | 2. Semantic Memory:           |
| - Real-time WebSocket Emitter | |                                | |    - User preferences & facts |
|                               | |                                | |    - Entity knowledge store   |
|                               | |                                | |    - SQLite + Vector retrieval|
+-------------------------------+ +--------------------------------+ +-------------------------------+
```

---

## 3. Core Architectural Modules

### Module A: Autonomous Cognitive Orchestrator
- **Model**: Google Gemini (`gemini-2.5-flash` / `gemini-1.5-pro` via `google-genai` SDK).
- **Adaptive Routing**:
  - `ROUTE_LIVE`: Time-sensitive queries targeting real-time events, breaking news, or market swings.
  - `ROUTE_KNOWLEDGE_BASE`: Deep background questions, historical filings, technical whitepapers.
  - `ROUTE_MEMORY`: Queries referencing past user instructions, tracked assets, or personal preferences.
  - `ROUTE_HYBRID`: Multi-source queries requiring synthesis across live streams, historical records, and memory.
- **Corrective Evaluator (CRAG)**:
  - Evaluates retrieved candidate chunks for relevance to the original user query.
  - Flags contradictory or low-relevance documents before feeding them into the generation prompt.

### Module B: Live Stream Ingestion & Temporal Decay
- **Continuous Ingest Worker**: Asynchronously fetches and parses live data feeds (RSS, tech/market events, breaking announcements).
- **Time-Decay Scoring Algorithm**:
  $$\text{FinalScore}(doc) = w_{\text{semantic}} \cdot \text{CosineSimilarity}(q, doc) + w_{\text{recency}} \cdot \exp\left(-\frac{\Delta t}{\tau}\right)$$
  Ensures that breaking news from 5 minutes ago outranks articles from last week when answering real-time questions.

### Module C: Dual-Tier Cognitive Memory
- **Episodic Store**: In-memory ring buffer linked to session IDs, storing thought-action-observation cycles.
- **Semantic Long-Term Store**:
  - SQLite database storing structured entity profiles (e.g., `user_id`, `entity_key`, `fact_content`, `importance_score`, `timestamp`).
  - Vector embeddings computed for semantic associative recall (e.g., recalling that the user previously stated *"I am heavily watching semiconductors"*).

### Module D: Frontend UI & Observability
- **Design Style**: Modern Dark-Mode Glassmorphism (`Inter` typography, subtle glow accents, card elevations).
- **Stream Radar Panel**: Live ticker visualizing incoming news events in real time.
- **Execution Graph Panel**: Step-by-step visual display of agent thought, tool dispatch, relevance grading score, and memory lookup.
- **Memory Inspector**: Allows users to view, search, and delete learned long-term facts.

---

## 4. Planned Directory Layout

```
pulserag-agentic-rag/
├── ARCHITECTURE.md          # This architecture design document
├── README.md                # Project documentation and quickstart
├── start.py                 # Single-command launcher (FastAPI + frontend)
├── requirements.txt         # Python dependencies
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI application (REST + SSE/WebSocket)
│   │   ├── config.py        # Environment & system configurations
│   │   ├── agent/           # Agentic loop, orchestrator, tools, & evaluator
│   │   ├── memory/          # Episodic & Semantic memory managers
│   │   ├── stream/          # Live stream buffer & ingestion workers
│   │   └── storage/         # ChromaDB & SQLite persistence
└── frontend/
    ├── index.html           # Full-featured single-page application
    ├── css/styles.css       # Design tokens & glassmorphism styling
    └── js/                  # App controller, live radar, agent visualizer, memory inspector
```

---

## 5. Next Steps
Once you have reviewed this architecture, we will proceed to generate the backend modules, ingestion pipeline, memory system, and the interactive frontend dashboard.
