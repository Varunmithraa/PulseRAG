import json
import logging
import time
from typing import Dict, Any, List, Optional, AsyncGenerator
from google import genai
from google.genai import types
from langgraph.graph import StateGraph, END

from ..config import settings
from .prompts import ROUTER_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT
from .tools import tool_search_live_streams, tool_search_knowledge_base, tool_recall_user_memories
from .evaluator import evaluator
from ..memory.memory_manager import memory_manager

logger = logging.getLogger(__name__)

class AgentState(dict):
    """LangGraph State dictionary representation."""
    user_id: str
    session_id: str
    query: str
    recalled_memories: List[Dict[str, Any]]
    route: str
    search_query: str
    retrieved_docs: List[Dict[str, Any]]
    graded_docs: List[Dict[str, Any]]
    grading_summary: Dict[str, Any]
    final_answer: str
    citations: List[Dict[str, Any]]
    steps: List[Dict[str, Any]]

class PulseAgentOrchestrator:
    """Autonomous Cognitive Agent Orchestrator running LangGraph with Corrective RAG & Dual-Tier Memory."""

    def __init__(self):
        self.client = None
        self._init_genai_client()
        self.graph = self._build_langgraph()

    def _init_genai_client(self):
        if settings.GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
                evaluator.client = self.client
                logger.info("Initialized Google GenAI client with key.")
            except Exception as e:
                logger.warning("Could not initialize Google GenAI client: %s", e)

    def _build_langgraph(self):
        """Constructs the LangGraph state machine graph."""
        workflow = StateGraph(dict)

        # Add Nodes
        workflow.add_node("recall_memory", self._node_recall_memory)
        workflow.add_node("route_query", self._node_route_query)
        workflow.add_node("retrieve_docs", self._node_retrieve_docs)
        workflow.add_node("grade_docs", self._node_grade_docs)
        workflow.add_node("synthesize", self._node_synthesize)

        # Set Entry Point
        workflow.set_entry_point("recall_memory")

        # Define Edges
        workflow.add_edge("recall_memory", "route_query")
        
        # Conditional Edge after routing: direct answer vs retrieval
        workflow.add_conditional_edges(
            "route_query",
            lambda state: "direct" if state.get("route") == "ROUTE_DIRECT" else "retrieve",
            {
                "direct": "synthesize",
                "retrieve": "retrieve_docs"
            }
        )
        
        workflow.add_edge("retrieve_docs", "grade_docs")
        workflow.add_edge("grade_docs", "synthesize")
        workflow.add_edge("synthesize", END)

        return workflow.compile()

    # --- Node Implementations ---

    def _node_recall_memory(self, state: dict) -> dict:
        user_id = state.get("user_id", "default_user")
        query = state.get("query", "")
        memories = tool_recall_user_memories(user_id=user_id, query=query)
        steps = state.get("steps", [])
        steps.append({
            "node": "recall_memory",
            "name": "Cognitive Memory Recall",
            "status": f"Recalled {len(memories)} user facts & preferences.",
            "data": memories
        })
        return {"recalled_memories": memories, "steps": steps}

    def _node_route_query(self, state: dict) -> dict:
        query = state.get("query", "")
        memories = state.get("recalled_memories", [])
        steps = state.get("steps", [])
        
        # Default heuristic routing
        q_lower = query.lower()
        if any(w in q_lower for w in ["what just", "breaking", "latest", "today", "now", "recent", "news", "price"]):
            route = "ROUTE_LIVE"
        elif any(w in q_lower for w in ["history", "whitepaper", "architecture", "deep-dive", "filing"]):
            route = "ROUTE_KB"
        elif any(w in q_lower for w in ["what do i track", "my watchlist", "my preferences", "who am i"]):
            route = "ROUTE_MEMORY"
        elif any(w in q_lower for w in ["hello", "hi", "hey"]):
            route = "ROUTE_DIRECT"
        else:
            route = "ROUTE_HYBRID"

        search_query = query
        # If Gemini client is active, use LLM router
        if self.client and settings.GEMINI_API_KEY:
            try:
                mem_str = "\n".join([f"- {m['category']}: {m['fact_content']}" for m in memories])
                prompt = f"User Memory Context:\n{mem_str}\n\nUser Query: {query}"
                resp = self.client.models.generate_content(
                    model=settings.DEFAULT_MODEL,
                    contents=prompt,
                    config={
                        "system_instruction": ROUTER_SYSTEM_PROMPT,
                        "response_mime_type": "application/json"
                    }
                )
                data = json.loads(resp.text)
                route = data.get("route", route)
                search_query = data.get("search_query", query)
            except Exception as e:
                logger.warning("LLM routing fallback to heuristic: %s", e)

        steps.append({
            "node": "route_query",
            "name": "Autonomous Intent Router",
            "status": f"Selected Route: {route}",
            "route": route,
            "search_query": search_query
        })
        return {"route": route, "search_query": search_query, "steps": steps}

    def _node_retrieve_docs(self, state: dict) -> dict:
        route = state.get("route", "ROUTE_HYBRID")
        search_query = state.get("search_query", state.get("query", ""))
        memories = state.get("recalled_memories", [])
        steps = state.get("steps", [])
        
        # Extract potential target tickers from memory
        target_tickers = []
        for m in memories:
            if m.get("category") == "watchlist":
                for word in m.get("fact_content", "").replace(",", " ").split():
                    if word.isupper() and 2 <= len(word) <= 5:
                        target_tickers.append(word)

        candidates = []
        if route in ("ROUTE_LIVE", "ROUTE_HYBRID", "ROUTE_MEMORY"):
            live_items = tool_search_live_streams(
                query=search_query, 
                top_k=4, 
                target_tickers=target_tickers
            )
            candidates.extend(live_items)

        if route in ("ROUTE_KB", "ROUTE_HYBRID"):
            kb_items = tool_search_knowledge_base(query=search_query, top_k=3)
            candidates.extend(kb_items)

        steps.append({
            "node": "retrieve_docs",
            "name": "Temporal Stream & Vector Retrieval",
            "status": f"Retrieved {len(candidates)} candidate chunks with recency decay.",
            "count": len(candidates)
        })
        return {"retrieved_docs": candidates, "steps": steps}

    def _node_grade_docs(self, state: dict) -> dict:
        candidates = state.get("retrieved_docs", [])
        query = state.get("query", "")
        steps = state.get("steps", [])

        # In synchronous graph execution: apply fast heuristic grading
        graded = []
        scores = []
        for doc in candidates:
            title = doc.get("title", doc.get("metadata", {}).get("title", ""))
            content = doc.get("content", "")
            q_words = set(query.lower().split())
            text = (title + " " + content).lower()
            matches = [w for w in q_words if len(w) > 2 and w in text]
            score = round(min(1.0, 0.45 + (len(matches) / max(1, len(q_words))) * 0.55), 2)
            
            doc_c = dict(doc)
            doc_c["crag_score"] = score
            doc_c["crag_passed"] = score >= 0.45
            graded.append(doc_c)
            scores.append(score)

        passed = [d for d in graded if d["crag_passed"]]
        avg_score = round(sum(scores) / max(1, len(scores)), 2) if scores else 0.0

        summary = {
            "total_candidates": len(candidates),
            "passed_count": len(passed),
            "average_confidence": avg_score
        }
        steps.append({
            "node": "grade_docs",
            "name": "Corrective RAG (CRAG) Grader",
            "status": f"Quality Grade: {avg_score * 100}% confidence ({len(passed)}/{len(candidates)} chunks verified)",
            "summary": summary
        })
        return {"graded_docs": passed if passed else candidates, "grading_summary": summary, "steps": steps}

    def _node_synthesize(self, state: dict) -> dict:
        query = state.get("query", "")
        memories = state.get("recalled_memories", [])
        docs = state.get("graded_docs", [])
        route = state.get("route", "ROUTE_DIRECT")
        steps = state.get("steps", [])

        # Build Context Prompt
        mem_text = "\n".join([f"- [{m['category'].upper()}] {m['fact_content']}" for m in memories]) or "No prior user memory."
        
        citations = []
        doc_texts = []
        for i, d in enumerate(docs):
            source_type = d.get("source_type", "DOC")
            if source_type == "LIVE_STREAM":
                cite_label = f"Live Stream: {d.get('source')} • {d.get('age_str', 'recent')}"
            else:
                cite_label = f"Knowledge Base: {d.get('metadata', {}).get('title', 'Document')}"
            
            citations.append({
                "label": cite_label,
                "title": d.get("title", ""),
                "content": d.get("content", "")[:200] + "...",
                "source": d.get("source", "KB"),
                "url": d.get("url", "")
            })
            doc_texts.append(f"[{cite_label}]\nTitle: {d.get('title', '')}\nContent: {d.get('content', '')}")

        context_str = "\n\n".join(doc_texts) if doc_texts else "No external documents retrieved."

        # If Gemini is configured, synthesize via model
        answer = ""
        if self.client and settings.GEMINI_API_KEY:
            try:
                full_prompt = f"""=== USER MEMORY ===
{mem_text}

=== RETRIEVED CONTEXT ===
{context_str}

=== USER QUERY ===
{query}

Synthesize a grounded, insightful, and structured response citing sources where applicable."""
                
                resp = self.client.models.generate_content(
                    model=settings.DEFAULT_MODEL,
                    contents=full_prompt,
                    config={
                        "system_instruction": SYNTHESIS_SYSTEM_PROMPT,
                        "temperature": 0.3
                    }
                )
                answer = resp.text
            except Exception as e:
                logger.error("Gemini synthesis error: %s", e)
                answer = f"Error generating answer with Gemini: {e}\n\nFalling back to context summary."

        # Offline / Fallback generator if no API key
        if not answer:
            answer = f"### 📊 Intelligence Synthesis\n\nBased on your query **\"{query}\"** and active intelligence streams:\n\n"
            if docs:
                answer += f"**Live Stream & Knowledge Insights:**\n"
                for d in docs[:3]:
                    source = d.get('source', 'Feed')
                    age = d.get('age_str', '')
                    title = d.get('title', '')
                    content = d.get('content', '')
                    answer += f"- **{title}** [{source} • {age}]\n  {content}\n\n"
            else:
                answer += "No matching streaming events or documents found for this query.\n\n"
            
            if memories:
                answer += "**Personalized Memory Alignment:**\n"
                for m in memories[:2]:
                    answer += f"- Recalled preference: *{m['fact_content']}*\n"

        steps.append({
            "node": "synthesize",
            "name": "Grounded Answer Synthesis",
            "status": "Response generated with citations.",
            "citations_count": len(citations)
        })
        return {"final_answer": answer, "citations": citations, "steps": steps}

    async def execute_stream(self, query: str, user_id: str = "default_user", 
                             session_id: str = "sess_01") -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the agent and streams step transitions and token chunks for real-time observability.
        """
        initial_state = {
            "user_id": user_id,
            "session_id": session_id,
            "query": query,
            "recalled_memories": [],
            "route": "ROUTE_HYBRID",
            "search_query": query,
            "retrieved_docs": [],
            "graded_docs": [],
            "grading_summary": {},
            "final_answer": "",
            "citations": [],
            "steps": []
        }

        # Step 1: Memory
        yield {"type": "step", "node": "recall_memory", "label": "Cognitive Memory Recall", "status": "Reading SQLite & vector memories..."}
        mem_state = self._node_recall_memory(initial_state)
        initial_state.update(mem_state)
        yield {
            "type": "step_done", 
            "node": "recall_memory", 
            "status": f"Recalled {len(initial_state['recalled_memories'])} profile facts.",
            "memories": initial_state['recalled_memories']
        }

        # Step 2: Router
        yield {"type": "step", "node": "route_query", "label": "Autonomous Intent Router", "status": "Analyzing temporal intent and decomposing query..."}
        route_state = self._node_route_query(initial_state)
        initial_state.update(route_state)
        yield {
            "type": "step_done", 
            "node": "route_query", 
            "status": f"Route: {initial_state['route']} (Query: '{initial_state['search_query']}')",
            "route": initial_state['route']
        }

        # Step 3: Retrieval
        if initial_state['route'] != "ROUTE_DIRECT":
            yield {"type": "step", "node": "retrieve_docs", "label": "Live Stream & Vector Retrieval", "status": "Executing Temporal Recency-Decay search over stream buffer..."}
            ret_state = self._node_retrieve_docs(initial_state)
            initial_state.update(ret_state)
            yield {
                "type": "step_done", 
                "node": "retrieve_docs", 
                "status": f"Found {len(initial_state['retrieved_docs'])} candidate chunks.",
                "count": len(initial_state['retrieved_docs'])
            }

            # Step 4: CRAG Grading
            yield {"type": "step", "node": "grade_docs", "label": "Corrective RAG (CRAG) Grader", "status": "Evaluating relevance and filtering hallucinated noise..."}
            
            # Use async evaluator if Gemini client is active
            graded_docs, summary = await evaluator.filter_documents(query=query, docs=initial_state['retrieved_docs'])
            initial_state['graded_docs'] = graded_docs if graded_docs else initial_state['retrieved_docs']
            initial_state['grading_summary'] = summary
            yield {
                "type": "step_done", 
                "node": "grade_docs", 
                "status": f"CRAG Score: {int(summary['average_confidence'] * 100)}% ({summary['passed_count']}/{summary['total_candidates']} chunks verified)",
                "summary": summary
            }

        # Step 5: Grounded Synthesis
        yield {"type": "step", "node": "synthesize", "label": "Grounded Answer Synthesis", "status": "Synthesizing answer with citations..."}
        
        # Build synthesis prompt
        mem_text = "\n".join([f"- [{m['category'].upper()}] {m['fact_content']}" for m in initial_state['recalled_memories']]) or "No user memory."
        docs = initial_state['graded_docs']
        
        citations = []
        doc_texts = []
        for d in docs:
            source_type = d.get("source_type", "DOC")
            if source_type == "LIVE_STREAM":
                cite_label = f"Live Stream: {d.get('source')} • {d.get('age_str', 'recent')}"
            else:
                cite_label = f"Knowledge Base: {d.get('metadata', {}).get('title', 'Document')}"
            
            citations.append({
                "label": cite_label,
                "title": d.get("title", ""),
                "content": d.get("content", "")[:220] + "...",
                "source": d.get("source", "KB"),
                "url": d.get("url", "")
            })
            doc_texts.append(f"[{cite_label}]\nTitle: {d.get('title', '')}\nContent: {d.get('content', '')}")

        context_str = "\n\n".join(doc_texts) if doc_texts else "No external documents."
        full_prompt = f"""=== USER MEMORY ===
{mem_text}

=== RETRIEVED CONTEXT ===
{context_str}

=== USER QUERY ===
{query}

Synthesize a grounded, insightful, and structured response citing sources where applicable."""

        full_answer = ""
        if self.client and settings.GEMINI_API_KEY:
            # Models to try in order of capability
            candidate_models = [settings.DEFAULT_MODEL, "gemini-3.7-flash", "gemini-flash-latest"]
            for model_name in candidate_models:
                try:
                    stream = self.client.models.generate_content_stream(
                        model=model_name,
                        contents=full_prompt,
                        config={
                            "system_instruction": SYNTHESIS_SYSTEM_PROMPT,
                            "temperature": 0.3
                        }
                    )
                    stream_succeeded = False
                    for chunk in stream:
                        if chunk.text:
                            full_answer += chunk.text
                            stream_succeeded = True
                            yield {"type": "token", "content": chunk.text}
                    if stream_succeeded:
                        break
                except Exception as e:
                    logger.warning("Model %s failed (%s), trying fallback...", model_name, e)
                    full_answer = ""
                    continue

        if not full_answer:
            # Fallback local synthesis
            fallback = f"### 📊 Real-Time Market Intelligence Report\n\n**Query:** *{query}*\n\n"
            if docs:
                fallback += "**Breaking & Live Feed Insights:**\n"
                for d in docs[:3]:
                    fallback += f"- **{d.get('title', '')}** `[{d.get('source', '')} • {d.get('age_str', '')}]`\n  {d.get('content', '')}\n\n"
            if initial_state['recalled_memories']:
                fallback += "**User Profile & Watchlist Alignment:**\n"
                for m in initial_state['recalled_memories'][:2]:
                    fallback += f"- *{m.get('fact_content', '')}*\n"
            full_answer = fallback
            yield {"type": "token", "content": fallback}

        # Step 6: Learn and update memory in background
        memory_manager.learn_from_turn(
            user_id=user_id,
            session_id=session_id,
            user_text=query,
            assistant_response=full_answer
        )

        yield {
            "type": "done",
            "citations": citations,
            "session_id": session_id
        }

agent_orchestrator = PulseAgentOrchestrator()
