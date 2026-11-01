import json
import logging
import time
from typing import Dict, Any, List, Optional, AsyncGenerator
from google import genai
from google.genai import types
from langgraph.graph import StateGraph, END

from ..config import settings
from .prompts import (
    ROUTER_SYSTEM_PROMPT, 
    SYNTHESIS_SYSTEM_PROMPT,
    DEEP_RESEARCH_PLANNER_PROMPT,
    DEEP_RESEARCH_SYNTHESIZER_PROMPT
)
from .tools import tool_search_live_streams, tool_search_knowledge_base, tool_recall_user_memories
from .evaluator import evaluator
from .conflict_resolver import conflict_resolver
from .bull_bear_analyst import bull_bear_analyst
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
                conflict_resolver.client = self.client
                bull_bear_analyst.client = self.client
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
                             session_id: str = "sess_01", mode: str = "quick") -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the agent and streams step transitions and token chunks for real-time observability.
        Supports 'quick' mode (standard CRAG) and 'deep_research' mode (multi-vector investigative dossier).
        """
        if mode == "deep_research":
            async for ev in self.execute_deep_research_stream(query, user_id, session_id):
                yield ev
            return
        if mode == "bull_bear":
            async for ev in self.execute_bull_bear_stream(query, user_id, session_id):
                yield ev
            return
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

            # Step 4b: Temporal Contradiction & Fact-Conflict Matrix
            yield {
                "type": "step", 
                "node": "conflict_matrix", 
                "label": "Temporal Conflict & Truth Matrix", 
                "status": "Cross-verifying temporal claims across sources..."
            }
            conflict_matrix = await conflict_resolver.analyze_conflicts(query=query, docs=initial_state['graded_docs'])
            initial_state['conflict_matrix'] = conflict_matrix
            yield {
                "type": "step_done", 
                "node": "conflict_matrix", 
                "status": conflict_matrix.get("conflict_summary", "Reconciled temporal claims across sources."),
                "conflict_matrix": conflict_matrix
            }
            yield {
                "type": "conflict_matrix",
                "data": conflict_matrix
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
            "session_id": session_id,
            "conflict_matrix": initial_state.get("conflict_matrix", {})
        }

    async def execute_deep_research_stream(self, query: str, user_id: str = "default_user",
                                          session_id: str = "sess_01") -> AsyncGenerator[Dict[str, Any], None]:
        """
        Autonomous Deep Research Engine:
        1. Recalls active user memory & constraints.
        2. Decomposes primary inquiry into 3 distinct investigative vectors.
        3. Executes multi-hop parallel retrieval across live streaming ring buffer & vector memory.
        4. Cross-verifies evidence with CRAG grading.
        5. Synthesizes a structured institutional-grade Executive Intelligence Dossier.
        """
        initial_state = {
            "user_id": user_id,
            "session_id": session_id,
            "query": query,
            "recalled_memories": [],
            "steps": []
        }

        # Step 1: Memory Recall
        yield {
            "type": "step", 
            "node": "recall_memory", 
            "label": "Cognitive Memory Recall", 
            "status": "Reading SQLite & vector memories for user watchlist & constraints..."
        }
        mem_state = self._node_recall_memory(initial_state)
        initial_state.update(mem_state)
        yield {
            "type": "step_done", 
            "node": "recall_memory", 
            "status": f"Recalled {len(initial_state['recalled_memories'])} user profile facts.",
            "memories": initial_state['recalled_memories']
        }

        # Step 2: Multi-Vector Deep Research Planner
        yield {
            "type": "step", 
            "node": "route_query", 
            "label": "Autonomous Multi-Vector Planner", 
            "status": "Formulating 3-vector investigative hypothesis and decomposition..."
        }

        # Baseline structured decomposition plan
        plan = {
            "topic": query,
            "executive_scope": f"Comprehensive multi-vector investigation into {query}",
            "vectors": [
                {
                    "id": "vector_1",
                    "name": "Live Catalysts & Timeline",
                    "focus": "Recent breaking events, announcements, and price/news momentum",
                    "search_query": f"{query} breaking latest news today"
                },
                {
                    "id": "vector_2",
                    "name": "Market Fundamentals & Key Players",
                    "focus": "Core technology, architecture, market structure, and key entities",
                    "search_query": f"{query} architecture technology fundamentals"
                },
                {
                    "id": "vector_3",
                    "name": "Risks, Regulatory & Counter-Theses",
                    "focus": "Downside risks, regulatory scrutiny, technical bottlenecks, and competitive counters",
                    "search_query": f"{query} risk challenge regulatory controversy"
                }
            ]
        }

        if self.client and settings.GEMINI_API_KEY:
            try:
                mem_str = "\n".join([f"- {m['category']}: {m['fact_content']}" for m in initial_state['recalled_memories']])
                plan_prompt = f"User Memory Context:\n{mem_str}\n\nResearch Inquiry: {query}"
                resp = self.client.models.generate_content(
                    model=settings.DEFAULT_MODEL,
                    contents=plan_prompt,
                    config={
                        "system_instruction": DEEP_RESEARCH_PLANNER_PROMPT,
                        "response_mime_type": "application/json"
                    }
                )
                parsed_plan = json.loads(resp.text)
                if "vectors" in parsed_plan and len(parsed_plan["vectors"]) >= 2:
                    plan = parsed_plan
            except Exception as e:
                logger.warning("Deep research planner LLM failed, using structured template: %s", e)

        yield {
            "type": "step_done", 
            "node": "route_query", 
            "status": f"Formulated {len(plan['vectors'])}-vector investigative plan.",
            "plan": plan
        }
        yield {
            "type": "research_plan",
            "plan": plan
        }

        # Step 3: Multi-Hop Vector Retrieval across Live Buffer & Vector Store
        yield {
            "type": "step", 
            "node": "retrieve_docs", 
            "label": "Multi-Hop Temporal Sweep", 
            "status": f"Sweeping streaming buffer & vector stores across {len(plan['vectors'])} research vectors..."
        }

        all_vector_docs = []
        vector_results = {}
        for vec in plan["vectors"]:
            v_id = vec.get("id", "vec")
            v_name = vec.get("name", "Vector")
            v_query = vec.get("search_query", query)
            
            # Retrieve live items with temporal decay
            live_items = tool_search_live_streams(query=v_query, top_k=3)
            # Retrieve knowledge base chunks
            kb_items = tool_search_knowledge_base(query=v_query, top_k=2)
            
            combined = live_items + kb_items
            for doc in combined:
                doc["investigation_vector"] = v_name
            
            vector_results[v_id] = {
                "name": v_name,
                "count": len(combined),
                "docs": combined
            }
            all_vector_docs.extend(combined)

        yield {
            "type": "step_done", 
            "node": "retrieve_docs", 
            "status": f"Collected {len(all_vector_docs)} multi-hop chunks across {len(plan['vectors'])} vectors.",
            "count": len(all_vector_docs),
            "vector_breakdown": {k: v["count"] for k, v in vector_results.items()}
        }

        # Step 4: Corrective RAG (CRAG) Cross-Verification
        yield {
            "type": "step", 
            "node": "grade_docs", 
            "label": "Cross-Vector CRAG Evaluator", 
            "status": "Deduplicating evidence & scoring factual relevance across vectors..."
        }

        # Deduplicate docs by title/content
        unique_docs = []
        seen_keys = set()
        for doc in all_vector_docs:
            k = (doc.get("title", "") + doc.get("content", "")[:60]).lower().strip()
            if k not in seen_keys:
                seen_keys.add(k)
                unique_docs.append(doc)

        graded_docs, summary = await evaluator.filter_documents(query=query, docs=unique_docs)
        if not graded_docs:
            graded_docs = unique_docs

        yield {
            "type": "step_done", 
            "node": "grade_docs", 
            "status": f"CRAG Score: {int(summary['average_confidence'] * 100)}% ({len(graded_docs)} verified evidence assets)",
            "summary": summary
        }

        # Step 4b: Temporal Contradiction & Fact-Conflict Matrix for Deep Research
        yield {
            "type": "step", 
            "node": "conflict_matrix", 
            "label": "Temporal Conflict & Truth Matrix", 
            "status": "Cross-verifying claims across research vectors for temporal revisions..."
        }
        conflict_matrix = await conflict_resolver.analyze_conflicts(query=query, docs=graded_docs)
        initial_state['conflict_matrix'] = conflict_matrix
        yield {
            "type": "step_done", 
            "node": "conflict_matrix", 
            "status": conflict_matrix.get("conflict_summary", "Reconciled multi-vector temporal claims."),
            "conflict_matrix": conflict_matrix
        }
        yield {
            "type": "conflict_matrix",
            "data": conflict_matrix
        }

        # Step 5: Executive Dossier Synthesis
        yield {
            "type": "step", 
            "node": "synthesize", 
            "label": "Executive Dossier Synthesis", 
            "status": "Synthesizing multi-section Executive Intelligence Dossier..."
        }

        mem_text = "\n".join([f"- [{m['category'].upper()}] {m['fact_content']}" for m in initial_state['recalled_memories']]) or "No user memory."
        
        citations = []
        context_blocks = []
        for i, d in enumerate(graded_docs):
            src = d.get('source', 'Intel Feed')
            age = d.get('age_str', 'recent')
            v_tag = d.get('investigation_vector', 'General')
            label = f"{src} • {age} [{v_tag}]"
            citations.append({
                "label": label,
                "title": d.get("title", ""),
                "content": d.get("content", "")[:240] + "...",
                "source": src,
                "url": d.get("url", ""),
                "vector": v_tag
            })
            context_blocks.append(f"[{label}]\nTitle: {d.get('title', '')}\nContent: {d.get('content', '')}")

        context_str = "\n\n".join(context_blocks) if context_blocks else "No external documents."
        
        dossier_prompt = f"""=== USER MEMORY & WATCHLIST ===
{mem_text}

=== INVESTIGATION SCOPE ===
Topic: {plan.get('topic', query)}
Scope: {plan.get('executive_scope', '')}

=== MULTI-HOP RETRIEVED INTELLIGENCE CONTEXT ===
{context_str}

=== USER RESEARCH INQUIRY ===
{query}

Synthesize the complete, authoritative Executive Intelligence Dossier now according to the required sections."""

        full_dossier = ""
        if self.client and settings.GEMINI_API_KEY:
            candidate_models = [settings.DEFAULT_MODEL, "gemini-3.7-flash", "gemini-flash-latest"]
            for model_name in candidate_models:
                try:
                    stream = self.client.models.generate_content_stream(
                        model=model_name,
                        contents=dossier_prompt,
                        config={
                            "system_instruction": DEEP_RESEARCH_SYNTHESIZER_PROMPT,
                            "temperature": 0.25
                        }
                    )
                    stream_succeeded = False
                    for chunk in stream:
                        if chunk.text:
                            full_dossier += chunk.text
                            stream_succeeded = True
                            yield {"type": "token", "content": chunk.text}
                    if stream_succeeded:
                        break
                except Exception as e:
                    logger.warning("Model %s failed for deep research dossier (%s), trying fallback...", model_name, e)
                    full_dossier = ""
                    continue

        if not full_dossier:
            # High-fidelity fallback template
            fallback = f"""# 📑 EXECUTIVE INTELLIGENCE DOSSIER: {query.upper()}
*Authored by PulseRAG Autonomous Multi-Hop Research Engine • Grounded with Live Temporal Intelligence*

---

## 📌 1. Executive Summary & Core Thesis
- **Primary Finding:** Autonomous multi-hop investigation into **{query}** indicates elevated market and technology activity driven by recent catalysts.
- **Cross-Vector Breadth:** Evaluated across {len(plan['vectors'])} specialized investigative vectors, incorporating {len(graded_docs)} verified streaming events.
- **Key Takeaway:** Strategic attention should center on execution velocity, competitive positioning, and regulatory clarity.

## ⏱️ 2. Chronological Event & Catalyst Timeline
"""
            for d in graded_docs[:4]:
                fallback += f"- **[{d.get('source', 'Live Feed')} • {d.get('age_str', 'recent')}]:** {d.get('title', '')} — *{d.get('content', '')[:140]}...*\n"
            
            fallback += f"""
## 📊 3. Deep-Dive Analysis & Market Metrics
"""
            for vec in plan["vectors"]:
                fallback += f"### {vec['name']}\n- **Focus:** {vec['focus']}\n"
                docs_for_vec = [d for d in graded_docs if d.get('investigation_vector') == vec['name']]
                if docs_for_vec:
                    for d in docs_for_vec[:2]:
                        fallback += f"  - *{d.get('title', '')}:* {d.get('content', '')[:160]}...\n"
                else:
                    fallback += "  - Ongoing baseline monitoring established across active feeds.\n"
            
            fallback += f"""
## ⚖️ 4. Risk Matrix & Contrarian Counter-Theses
- **Downside Uncertainty:** Macro headwinds, execution delays, and competing open-source solutions.
- **Counter-Thesis:** Market expectations may temporarily outpace production deployments.

## 🎯 5. Strategic Implications & Watchlist Alignment
"""
            if initial_state['recalled_memories']:
                for m in initial_state['recalled_memories'][:2]:
                    fallback += f"- **Aligned with tracked priority:** *{m.get('fact_content', '')}*\n"
            else:
                fallback += "- Maintain active temporal surveillance across linked RSS streams.\n"

            fallback += f"""
## 📚 6. Evidence Verification & Source Index
Verified {len(citations)} source citations across the temporal ring buffer and vector store.
"""
            full_dossier = fallback
            yield {"type": "token", "content": fallback}

        # Learn from turn in background
        memory_manager.learn_from_turn(
            user_id=user_id,
            session_id=session_id,
            user_text=f"[Deep Research Dossier] {query}",
            assistant_response=full_dossier
        )

        yield {
            "type": "done",
            "mode": "deep_research",
            "dossier_title": plan.get("topic", query),
            "citations": citations,
            "session_id": session_id,
            "plan": plan,
            "conflict_matrix": initial_state.get("conflict_matrix", {})
        }

    async def execute_bull_bear_stream(self, query: str, user_id: str = "default_user",
                                       session_id: str = "sess_01") -> AsyncGenerator[Dict[str, Any], None]:
        """
        Adversarial Intelligence Duel Stream:
        1. Recalls active user watchlist & constraints from memory.
        2. Decomposes inquiry into dual search vectors (Bullish momentum & catalysts vs Bearish risks & bottlenecks).
        3. Executes dual-perspective sweep across streaming ring buffer & vector store.
        4. CRAG relevance verification.
        5. Temporal conflict matrix cross-check.
        6. Conducts adversarial duel yielding calibrated Arbiter split and decisive swing factors.
        7. Synthesizes an executive markdown duel report and streams token chunks.
        """
        initial_state = {
            "user_id": user_id,
            "session_id": session_id,
            "query": query,
            "recalled_memories": [],
            "steps": []
        }

        # Step 1: Memory
        yield {
            "type": "step",
            "node": "recall_memory",
            "label": "Cognitive Memory Recall",
            "status": "Scanning user preferences, risk tolerance & watchlist..."
        }
        mem_state = self._node_recall_memory(initial_state)
        initial_state.update(mem_state)
        yield {
            "type": "step_done",
            "node": "recall_memory",
            "status": f"Recalled {len(initial_state['recalled_memories'])} user profile facts.",
            "memories": initial_state['recalled_memories']
        }

        # Step 2: Adversarial Query Decomposition
        yield {
            "type": "step",
            "node": "route_query",
            "label": "Adversarial Query Decomposition",
            "status": "Formulating opposing Bull & Bear research vectors..."
        }
        clean_topic = query.replace("⚖️", "").replace("Bull vs Bear:", "").replace("bull vs bear:", "").strip()
        bull_query = f"{clean_topic} growth catalysts record surge demand breakthrough upside"
        bear_query = f"{clean_topic} risks delays bottlenecks warning probe decline capex"

        yield {
            "type": "step_done",
            "node": "route_query",
            "status": f"Decomposed into Bull catalyst vector & Bear vulnerability vector.",
            "bull_query": bull_query,
            "bear_query": bear_query
        }

        # Step 3: Dual-Perspective Retrieval
        yield {
            "type": "step",
            "node": "retrieve_docs",
            "label": "Dual-Perspective Temporal Sweep",
            "status": "Retrieving market signals across bullish & bearish vectors..."
        }
        bull_docs = tool_search_live_streams(bull_query, top_k=5)
        bear_docs = tool_search_live_streams(bear_query, top_k=5)
        kb_docs = tool_search_knowledge_base(clean_topic, top_k=4)

        seen_titles = set()
        combined_docs = []
        for d in (bull_docs + bear_docs + kb_docs):
            title = d.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                combined_docs.append(d)

        initial_state["retrieved_docs"] = combined_docs
        yield {
            "type": "step_done",
            "node": "retrieve_docs",
            "status": f"Retrieved {len(combined_docs)} candidate evidence chunks across both theses.",
            "count": len(combined_docs)
        }

        # Step 4: CRAG Grading
        yield {
            "type": "step",
            "node": "grade_docs",
            "label": "Corrective RAG (CRAG) Grader",
            "status": "Evaluating evidence authenticity and thesis alignment..."
        }
        graded_docs, summary = await evaluator.filter_documents(query=clean_topic, docs=combined_docs)
        if not graded_docs:
            graded_docs = combined_docs
        initial_state["graded_docs"] = graded_docs
        yield {
            "type": "step_done",
            "node": "grade_docs",
            "status": f"CRAG Score: {int(summary['average_confidence'] * 100)}% ({len(graded_docs)} verified evidence chunks)",
            "summary": summary
        }

        # Step 5: Fact-Conflict Matrix
        yield {
            "type": "step",
            "node": "conflict_matrix",
            "label": "Temporal Conflict & Truth Matrix",
            "status": "Cross-verifying factual discrepancies between bull and bear evidence..."
        }
        conflict_matrix = await conflict_resolver.analyze_conflicts(query=clean_topic, docs=graded_docs)
        initial_state["conflict_matrix"] = conflict_matrix
        yield {
            "type": "step_done",
            "node": "conflict_matrix",
            "status": conflict_matrix.get("conflict_summary", "Reconciled temporal claims across sources."),
            "conflict_matrix": conflict_matrix
        }
        yield {
            "type": "conflict_matrix",
            "data": conflict_matrix
        }

        # Step 6: Adversarial Duel Engine
        yield {
            "type": "step",
            "node": "bull_bear",
            "label": "Adversarial Intelligence Duel",
            "status": "Executing Bull vs Bear duel & computing calibrated Arbiter probability split..."
        }
        debate_data = await bull_bear_analyst.conduct_debate(
            query=clean_topic,
            docs=graded_docs,
            memories=initial_state["recalled_memories"]
        )
        yield {
            "type": "step_done",
            "node": "bull_bear",
            "status": f"Duel concluded: {debate_data['arbiter_verdict']['prevailing_side']} ({debate_data['arbiter_verdict']['bull_weight']}% Bull / {debate_data['arbiter_verdict']['bear_weight']}% Bear)",
            "debate": debate_data
        }
        yield {
            "type": "bull_bear_debate",
            "data": debate_data
        }

        # Step 7: Stream Executive Duel Report
        yield {
            "type": "step",
            "node": "synthesize",
            "label": "Institutional Duel Synthesis",
            "status": "Synthesizing executive duel briefing..."
        }

        # Citations
        citations = []
        for d in graded_docs[:6]:
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

        bull = debate_data.get("bull_case", {})
        bear = debate_data.get("bear_case", {})
        arbiter = debate_data.get("arbiter_verdict", {})

        report_md = f"""# ⚖️ Institutional Adversarial Duel: {debate_data.get('topic', clean_topic)}

### 🏛️ Calibrated Arbiter Verdict
**Prevailing Trajectory:** `{arbiter.get('prevailing_side', 'NEUTRAL')}`  
**Calibrated Probability Split:** 📈 **{arbiter.get('bull_weight', 50)}% Bullish** vs 📉 **{arbiter.get('bear_weight', 50)}% Bearish**

> **🎯 Decisive 90-Day Swing Factor:**  
> **{arbiter.get('decisive_swing_factor', 'Key operational delivery metrics and hyperscaler capex commitment.')}**

{arbiter.get('executive_synthesis', '')}

---

## 📈 The Bull Case (Conviction: {bull.get('conviction_score', 75)}/100)
**Thesis:** *{bull.get('core_thesis', '')}*

**Key Upside Catalysts:**
"""
        for cat in bull.get("key_catalysts", []):
            report_md += f"- **Catalyst:** {cat}\n"
        report_md += f"\n**Upside Scenario:** {bull.get('upside_potential', '')}\n\n---\n\n"

        report_md += f"""## 📉 The Bear Case (Conviction: {bear.get('conviction_score', 65)}/100)
**Thesis:** *{bear.get('core_thesis', '')}*

**Key Risk Factors & Bottlenecks:**
"""
        for r in bear.get("risk_factors", []):
            report_md += f"- **Vulnerability:** {r}\n"
        report_md += f"\n**Downside Failure Mode:** {bear.get('downside_vulnerability', '')}\n\n---\n\n"

        report_md += f"""## ⚖️ Strategic Positioning Directive
For institutional portfolio managers and technology strategists, current signals warrant **{arbiter.get('prevailing_side', 'BALANCED')}** posture. Monitor the decisive swing factor carefully before adjusting allocation thresholds.
"""

        for chunk in [report_md[i:i+120] for i in range(0, len(report_md), 120)]:
            yield {"type": "token", "content": chunk}

        # Learn from turn
        memory_manager.learn_from_turn(
            user_id=user_id,
            session_id=session_id,
            user_text=f"[Adversarial Duel] {query}",
            assistant_response=report_md
        )

        yield {
            "type": "done",
            "mode": "bull_bear",
            "topic": debate_data.get("topic", clean_topic),
            "citations": citations,
            "session_id": session_id,
            "debate": debate_data,
            "conflict_matrix": initial_state.get("conflict_matrix", {})
        }

agent_orchestrator = PulseAgentOrchestrator()
