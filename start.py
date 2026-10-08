"""
Single-command launcher for PulseRAG Platform.
Run with: python start.py
"""
import os
import sys
import webbrowser
import uvicorn
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

if __name__ == "__main__":
    print("=" * 65)
    print("⚡ Starting PulseRAG: Autonomous Agentic RAG Platform")
    print("=" * 65)
    print("• Live Stream Ingestion Engine: ACTIVE")
    print("• Temporal Recency-Decay Ranking: ENABLED")
    print("• Dual-Tier Cognitive Memory (SQLite + Vector): INITIALIZED")
    print("• LangGraph State Machine & CRAG Evaluator: READY")
    print("• Local Web Dashboard: http://127.0.0.1:8000")
    print("=" * 65)
    
    # Open browser automatically after a short delay
    try:
        import threading
        import time
        def open_browser():
            time.sleep(1.5)
            webbrowser.open("http://127.0.0.1:8000")
        threading.Thread(target=open_browser, daemon=True).start()
    except Exception:
        pass

    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
