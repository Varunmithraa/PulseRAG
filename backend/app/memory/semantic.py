import re
import json
import logging
from typing import List, Dict, Any, Optional
from ..storage.database import db
from ..storage.vector_store import vector_store

logger = logging.getLogger(__name__)

# Heuristic patterns for rapid zero-cost extraction
PREFERENCE_PATTERNS = [
    (r"(?:i track|i am tracking|watching|portfolio has|interested in)\s+([A-Za-z0-9,\s]+)", "watchlist"),
    (r"(?:prefer|like|want)\s+(concise|bullet points|detailed|technical|deep-dive|brief)", "format_preference"),
    (r"(?:risk tolerance is|my risk is|i am a)\s+(conservative|aggressive|moderate|risk-averse)", "risk_profile")
]

class SemanticMemoryManager:
    """Manages Long-Term Memory: persistent user profiles, entity watchlists, and semantic associative recall."""

    def __init__(self):
        self.db = db
        self.vector_store = vector_store

    def save_fact(self, user_id: str, category: str, entity_key: str, 
                  fact_content: str, importance: float = 0.85, 
                  metadata: Optional[Dict[str, Any]] = None) -> int:
        """Saves a learned fact into SQLite and indexes it in ChromaDB."""
        fact_id = self.db.upsert_fact(
            user_id=user_id,
            category=category,
            entity_key=entity_key,
            fact_content=fact_content,
            importance_score=importance,
            metadata=metadata
        )
        
        # Index in ChromaDB for vector retrieval
        chroma_id = f"fact_{user_id}_{entity_key}"
        self.vector_store.index_memory_fact(
            fact_id=chroma_id,
            fact_content=fact_content,
            metadata={"user_id": user_id, "category": category, "entity_key": entity_key, "fact_id": fact_id}
        )
        return fact_id

    def recall_memories(self, user_id: str, query: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recalls relevant long-term memories for a user.
        Combines direct SQLite lookup of high-importance facts with vector associative search if a query is given.
        """
        all_user_facts = self.db.get_facts_for_user(user_id)
        if not all_user_facts:
            return []

        if not query:
            return all_user_facts[:limit]

        # Semantic associative search via Chroma
        vector_matches = self.vector_store.search_memory(query=query, user_id=user_id, n_results=limit)
        matched_keys = {m["metadata"].get("entity_key") for m in vector_matches if m.get("metadata")}

        # Combine results: give priority to semantically matched facts, then high importance
        scored_facts = []
        for fact in all_user_facts:
            score = fact["importance_score"]
            if fact["entity_key"] in matched_keys:
                score += 0.5  # Boost semantically relevant facts
            scored_facts.append((score, fact))

        scored_facts.sort(key=lambda x: x[0], reverse=True)
        return [f[1] for f in scored_facts[:limit]]

    def delete_fact(self, fact_id: int, user_id: str, entity_key: str) -> bool:
        """Deletes a fact from both SQLite and ChromaDB."""
        chroma_id = f"fact_{user_id}_{entity_key}"
        self.vector_store.delete_memory_fact(chroma_id)
        return self.db.delete_fact(fact_id)

    def extract_facts_heuristic(self, user_id: str, text: str) -> List[Dict[str, Any]]:
        """Extracts facts from natural language using pattern heuristics."""
        extracted = []
        lower = text.lower()
        
        # Check stock tickers mentioned
        ticker_matches = re.findall(r"\b([A-Z]{2,5})\b", text)
        known_stocks = {"NVDA", "AAPL", "MSFT", "TSM", "GOOGL", "AMZN", "META", "AMD", "ASML", "INTC", "TSLA", "SPY", "QQQ"}
        found_tickers = [t for t in ticker_matches if t in known_stocks]
        if found_tickers and any(w in lower for w in ["track", "watch", "portfolio", "care about", "my stocks", "holding"]):
            tickers_str = ", ".join(sorted(set(found_tickers)))
            self.save_fact(
                user_id=user_id,
                category="watchlist",
                entity_key="tracked_tickers",
                fact_content=f"User actively tracks market tickers: {tickers_str}",
                importance=0.95
            )
            extracted.append({"category": "watchlist", "fact": f"Tracked tickers: {tickers_str}"})

        # Pattern matches
        for pattern, category in PREFERENCE_PATTERNS:
            match = re.search(pattern, lower)
            if match:
                value = match.group(1).strip()
                self.save_fact(
                    user_id=user_id,
                    category=category,
                    entity_key=f"pref_{category}",
                    fact_content=f"User {category}: {value}",
                    importance=0.85
                )
                extracted.append({"category": category, "fact": f"{category}: {value}"})

        return extracted

semantic_memory = SemanticMemoryManager()
