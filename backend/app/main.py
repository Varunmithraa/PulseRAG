import os
import json
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings, BASE_DIR
from .stream.live_buffer import live_stream_buffer
from .stream.ingestion_engine import ingestion_engine
from .storage.vector_store import vector_store
from .storage.database import db
from .memory.memory_manager import memory_manager
from .agent.orchestrator import agent_orchestrator
from .agent.intel_alert_monitor import alert_monitor
from .agent.briefing_generator import briefing_generator

# Models
class ChatRequest(BaseModel):
    query: str
    user_id: Optional[str] = "default_user"
    session_id: Optional[str] = "default_session"
    mode: Optional[str] = "quick"

class InjectEventRequest(BaseModel):
    title: str
    content: str
    source: Optional[str] = "Manual Radar Injection"
    category: Optional[str] = "Breaking News"
    tickers: Optional[List[str]] = []

class MemoryFactRequest(BaseModel):
    user_id: Optional[str] = "default_user"
    category: str
    entity_key: str
    fact_content: str
    importance_score: Optional[float] = 0.85

class LinkFeedRequest(BaseModel):
    name: str
    url: str
    category: Optional[str] = "Live Web"
    description: Optional[str] = ""

class UnlinkFeedRequest(BaseModel):
    name: str

class ToggleFeedRequest(BaseModel):
    name: str
    enabled: bool

class SimulateAlertRequest(BaseModel):
    headline: Optional[str] = None

class MarkAlertReadRequest(BaseModel):
    alert_id: Optional[str] = "all"

class ToggleAlertsRequest(BaseModel):
    enabled: bool

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Start background ingestion worker and autonomous alert monitor
    worker_task = asyncio.create_task(ingestion_engine.start_worker())
    alert_task = asyncio.create_task(alert_monitor.start_worker())
    
    print("PulseRAG Live Engine & Autonomous Alert Monitor initialized.")
    yield
    # Shutdown
    worker_task.cancel()
    alert_task.cancel()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan
)

# API Routes

@app.get("/api/status")
async def get_status():
    """Returns runtime telemetry for the agent dashboard."""
    recent_events = live_stream_buffer.get_recent(50)
    all_facts = db.list_all_facts(limit=50)
    active_feeds_count = len([f for f in ingestion_engine.active_feeds.values() if f.get("enabled", True)])
    alerts_overview = alert_monitor.get_alerts_overview(limit=10)
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "gemini_api_configured": bool(settings.GEMINI_API_KEY),
        "model": settings.DEFAULT_MODEL,
        "live_buffer_count": len(recent_events),
        "memory_facts_count": len(all_facts),
        "active_feeds_count": active_feeds_count,
        "unread_alerts_count": alerts_overview.get("unread_count", 0),
        "critical_alerts_count": alerts_overview.get("critical_count", 0),
        "decay_lambda": settings.TIME_DECAY_LAMBDA,
        "semantic_weight": settings.SEMANTIC_WEIGHT,
        "recency_weight": settings.RECENCY_WEIGHT
    }

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Server-Sent Events (SSE) streaming endpoint:
    Yields real-time LangGraph execution steps, CRAG scores, and token streams.
    """
    async def event_generator():
        try:
            async for event in agent_orchestrator.execute_stream(
                query=req.query,
                user_id=req.user_id or "default_user",
                session_id=req.session_id or "default_session",
                mode=req.mode or "quick"
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_payload = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/stream/events")
async def get_stream_events(limit: int = 25):
    """Returns current live items in the temporal buffer."""
    return {"events": live_stream_buffer.get_recent(limit)}

@app.post("/api/stream/inject")
async def inject_event(req: InjectEventRequest):
    """Injects a custom event into the live stream buffer."""
    event = ingestion_engine.inject_event(
        title=req.title,
        content=req.content,
        source=req.source or "Manual Radar Injection",
        category=req.category or "Breaking News",
        tickers=req.tickers
    )
    return {"status": "success", "event": event}

@app.get("/api/memory")
async def get_memories(user_id: str = "default_user"):
    """Returns all long-term facts for a user."""
    facts = db.get_facts_for_user(user_id)
    return {"user_id": user_id, "facts": facts}

@app.post("/api/memory")
async def add_memory(req: MemoryFactRequest):
    """Manually adds or edits a user fact."""
    fact_id = memory_manager.semantic.save_fact(
        user_id=req.user_id or "default_user",
        category=req.category,
        entity_key=req.entity_key,
        fact_content=req.fact_content,
        importance=req.importance_score or 0.85
    )
    return {"status": "success", "fact_id": fact_id}

@app.delete("/api/memory/{fact_id}")
async def delete_memory(fact_id: int, user_id: str = "default_user", entity_key: str = ""):
    """Deletes a learned fact."""
    success = memory_manager.semantic.delete_fact(fact_id=fact_id, user_id=user_id, entity_key=entity_key)
    return {"status": "deleted" if success else "not_found"}

# --- Dynamic Feed & Source Hub Routes ---

@app.get("/api/feeds")
async def get_feeds():
    """Returns active feeds and discoverable catalog with link statuses."""
    return ingestion_engine.get_feeds_overview()

@app.post("/api/feeds/link")
async def link_feed(req: LinkFeedRequest):
    """Dynamically links an RSS source and starts polling it."""
    feed = ingestion_engine.link_feed(
        name=req.name,
        url=req.url,
        category=req.category or "Live Web",
        description=req.description or ""
    )
    return {"status": "success", "feed": feed}

@app.post("/api/feeds/unlink")
async def unlink_feed(req: UnlinkFeedRequest):
    """Unlinks a feed."""
    success = ingestion_engine.unlink_feed(req.name)
    return {"status": "unlinked" if success else "not_found"}

@app.post("/api/feeds/toggle")
async def toggle_feed(req: ToggleFeedRequest):
    """Enables or pauses a linked feed."""
    success = ingestion_engine.toggle_feed(req.name, req.enabled)
    return {"status": "toggled" if success else "not_found", "enabled": req.enabled}

# --- Autonomous Intelligence Alerts Routes ---

@app.get("/api/alerts")
async def get_alerts(limit: int = 50):
    """Returns recent proactive intelligence alerts generated by the autonomous agent."""
    return alert_monitor.get_alerts_overview(limit=limit)

@app.post("/api/alerts/simulate")
async def simulate_alert(req: Optional[SimulateAlertRequest] = None):
    """Simulates a breaking market/geopolitical catalyst and triggers an instant autonomous alert."""
    custom_headline = req.headline if req else None
    alert = await alert_monitor.simulate_alert(custom_headline)
    return {"status": "success", "alert": alert}

@app.post("/api/alerts/read")
async def mark_alerts_read(req: MarkAlertReadRequest):
    """Marks an alert or all alerts as read."""
    db.mark_alerts_read(req.alert_id)
    return {"status": "success", "alert_id": req.alert_id}

@app.post("/api/alerts/clear")
async def clear_alerts():
    """Clears all stored alerts."""
    db.clear_alerts()
    return {"status": "cleared"}

@app.post("/api/alerts/toggle")
async def toggle_alerts(req: ToggleAlertsRequest):
    """Enables or pauses autonomous live alert monitoring."""
    state = alert_monitor.toggle_monitoring(req.enabled)
    return {"status": "success", "enabled": state}

# --- Executive Voice Intelligence Briefing Routes ---

@app.get("/api/briefing/latest")
async def get_latest_briefing():
    """Returns the most recent executive voice briefing digest."""
    return await briefing_generator.generate_briefing(force_refresh=False)

@app.post("/api/briefing/generate")
async def generate_briefing():
    """Forces real-time synthesis of all live streams into a fresh voice briefing."""
    return await briefing_generator.generate_briefing(force_refresh=True)

# Mount frontend static directory
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
