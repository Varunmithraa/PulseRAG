import time
import math
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import deque
import logging
from ..config import settings

logger = logging.getLogger(__name__)

class LiveStreamBuffer:
    """High-performance in-memory ring-buffer for live stream events with Temporal Recency-Decay scoring."""

    def __init__(self, max_size: int = settings.LIVE_BUFFER_MAX_SIZE):
        self.max_size = max_size
        self.buffer: deque = deque(maxlen=max_size)
        self.alpha = settings.SEMANTIC_WEIGHT
        self.recency_weight = settings.RECENCY_WEIGHT
        self.decay_lambda = settings.TIME_DECAY_LAMBDA

    def add_event(self, title: str, content: str, source: str, 
                  url: str = "", category: str = "Market/Tech", 
                  tickers: Optional[List[str]] = None,
                  timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Pushes a new live stream event into the sliding window buffer."""
        ts = timestamp or time.time()
        event_id = f"evt_{int(ts * 1000)}_{len(self.buffer)}"
        event = {
            "id": event_id,
            "title": title.strip(),
            "content": content.strip(),
            "source": source.strip(),
            "url": url.strip(),
            "category": category,
            "tickers": [t.upper() for t in (tickers or [])],
            "timestamp": ts,
            "datetime_iso": datetime.fromtimestamp(ts).isoformat(),
            "source_type": "LIVE_STREAM"
        }
        self.buffer.appendleft(event)
        return event

    def get_recent(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Returns the most recent events from the live stream radar."""
        return list(self.buffer)[:limit]

    def _compute_lexical_similarity(self, query: str, text: str) -> float:
        """Computes normalized keyword and n-gram overlap between query and document text."""
        query_words = set(re.findall(r"\w+", query.lower()))
        if not query_words:
            return 0.0
        doc_words = set(re.findall(r"\w+", text.lower()))
        if not doc_words:
            return 0.0
            
        intersection = query_words.intersection(doc_words)
        jaccard = len(intersection) / len(query_words.union(doc_words))
        recall = len(intersection) / len(query_words)
        
        # Weighted blend favoring query term recall
        return min(1.0, 0.7 * recall + 0.3 * jaccard)

    def search_with_temporal_decay(self, query: str, top_k: int = 5, 
                                   min_score: float = 0.15,
                                   target_tickers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Executes Temporal Recency-Decay Ranking:
        FinalScore = alpha * Sim(query, doc) + (1 - alpha) * exp(-lambda * delta_hours)
        """
        current_time = time.time()
        scored_events = []
        
        query_tickers = set(re.findall(r"\b[A-Z]{2,5}\b", query.upper()))
        if target_tickers:
            query_tickers.update([t.upper() for t in target_tickers])

        for event in self.buffer:
            # 1. Calculate age in hours
            delta_seconds = max(0.0, current_time - event["timestamp"])
            delta_hours = delta_seconds / 3600.0
            
            # 2. Exponential recency factor: e^(-lambda * delta_hours)
            recency_factor = math.exp(-self.decay_lambda * delta_hours)
            
            # 3. Text relevance (matching both title and content)
            combined_text = f"{event['title']} {event['content']}"
            sim_score = self._compute_lexical_similarity(query, combined_text)
            
            # Ticker boost: if user query specifically matches the event's tickers
            ticker_match = False
            if query_tickers and any(t in event.get("tickers", []) for t in query_tickers):
                sim_score = min(1.0, sim_score + 0.35)
                ticker_match = True

            # 4. Composite Score with temporal decay
            final_score = (self.alpha * sim_score) + (self.recency_weight * recency_factor)
            
            # Age description for readable citations
            if delta_hours < 0.1:
                age_str = f"{int(delta_seconds / 60)}m ago (breaking)"
            elif delta_hours < 1.0:
                age_str = f"{int(delta_seconds / 60)}m ago"
            elif delta_hours < 24.0:
                age_str = f"{int(delta_hours)}h ago"
            else:
                age_str = f"{int(delta_hours / 24)}d ago"

            if final_score >= min_score or ticker_match:
                scored_events.append({
                    "id": event["id"],
                    "title": event["title"],
                    "content": event["content"],
                    "source": event["source"],
                    "url": event["url"],
                    "tickers": event.get("tickers", []),
                    "timestamp": event["timestamp"],
                    "datetime_iso": event["datetime_iso"],
                    "age_str": age_str,
                    "similarity": round(sim_score, 4),
                    "recency_factor": round(recency_factor, 4),
                    "final_score": round(final_score, 4),
                    "source_type": "LIVE_STREAM"
                })

        # Sort by final score descending
        scored_events.sort(key=lambda x: x["final_score"], reverse=True)
        return scored_events[:top_k]

live_stream_buffer = LiveStreamBuffer()
