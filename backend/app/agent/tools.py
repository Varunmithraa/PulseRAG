from typing import List, Dict, Any, Optional
from ..stream.live_buffer import live_stream_buffer
from ..storage.vector_store import vector_store
from ..memory.memory_manager import memory_manager

def tool_search_live_streams(query: str, top_k: int = 4, 
                             target_tickers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Retrieves candidate articles from the live in-memory sliding buffer
    using the Temporal Recency-Decay formula:
    FinalScore = alpha * Sim(q, d) + (1 - alpha) * exp(-lambda * delta_hours).
    """
    return live_stream_buffer.search_with_temporal_decay(
        query=query,
        top_k=top_k,
        target_tickers=target_tickers
    )

def tool_search_knowledge_base(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Retrieves foundational documents, filings, and architectural whitepapers
    from the persistent ChromaDB collection.
    """
    return vector_store.search_kb(query=query, n_results=top_k)

def tool_recall_user_memories(user_id: str, query: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recalls user profile, tracked assets, and conversational constraints
    from the Dual-Tier Memory System (SQLite + Vector).
    """
    return memory_manager.semantic.recall_memories(user_id=user_id, query=query, limit=5)

def tool_save_user_memory(user_id: str, category: str, entity_key: str, 
                          fact_content: str, importance: float = 0.85) -> int:
    """
    Persists a learned fact into the user's permanent memory store.
    """
    return memory_manager.semantic.save_fact(
        user_id=user_id,
        category=category,
        entity_key=entity_key,
        fact_content=fact_content,
        importance=importance
    )
