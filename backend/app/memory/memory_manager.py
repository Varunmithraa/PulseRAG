from typing import List, Dict, Any, Optional
from .episodic import episodic_memory, EpisodicMemoryManager
from .semantic import semantic_memory, SemanticMemoryManager

class UnifiedMemoryManager:
    """Unified Cognitive Controller managing both Short-Term (Episodic) and Long-Term (Semantic) memory."""

    def __init__(self):
        self.episodic: EpisodicMemoryManager = episodic_memory
        self.semantic: SemanticMemoryManager = semantic_memory

    def get_full_context(self, user_id: str, session_id: str, current_query: str) -> Dict[str, Any]:
        """Gathers conversational history, user profile memories, and active traces."""
        history = self.episodic.get_conversation_history(session_id, limit=6)
        long_term_memories = self.semantic.recall_memories(user_id=user_id, query=current_query, limit=5)
        return {
            "conversation_history": history,
            "long_term_memories": long_term_memories,
            "user_id": user_id,
            "session_id": session_id
        }

    def learn_from_turn(self, user_id: str, session_id: str, user_text: str, assistant_response: str):
        """Updates episodic session turns and extracts potential long-term facts."""
        self.episodic.add_turn(session_id, "user", user_text)
        self.episodic.add_turn(session_id, "assistant", assistant_response)
        
        # Heuristic / automatic fact extraction
        self.semantic.extract_facts_heuristic(user_id, user_text)

memory_manager = UnifiedMemoryManager()
