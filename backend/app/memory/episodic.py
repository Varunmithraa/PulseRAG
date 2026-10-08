from typing import List, Dict, Any, Optional
from collections import defaultdict
import time

class EpisodicMemoryManager:
    """Manages short-term working memory: conversation turns and execution trace histories."""

    def __init__(self, max_turns_per_session: int = 15):
        self.max_turns = max_turns_per_session
        # session_id -> list of turn dicts
        self.sessions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # session_id -> list of trace dicts
        self.execution_traces: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def add_turn(self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Appends a conversation message to the session's working memory."""
        turn = {
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": time.time()
        }
        self.sessions[session_id].append(turn)
        if len(self.sessions[session_id]) > self.max_turns * 2:
            # Keep recent turns
            self.sessions[session_id] = self.sessions[session_id][-self.max_turns * 2:]

    def get_conversation_history(self, session_id: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Returns recent turns for LLM prompt context."""
        return self.sessions[session_id][-limit:]

    def log_trace(self, session_id: str, step_name: str, details: Dict[str, Any]):
        """Logs an agent reasoning or execution step."""
        self.execution_traces[session_id].append({
            "step": step_name,
            "details": details,
            "timestamp": time.time()
        })

    def get_traces(self, session_id: str) -> List[Dict[str, Any]]:
        return self.execution_traces[session_id]

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.execution_traces:
            del self.execution_traces[session_id]

episodic_memory = EpisodicMemoryManager()
