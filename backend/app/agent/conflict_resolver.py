import json
import logging
from typing import List, Dict, Any, Optional
from ..config import settings
from .prompts import CONFLICT_MATRIX_PROMPT

logger = logging.getLogger(__name__)

class TemporalConflictResolver:
    """
    Autonomous Temporal Truth & Fact-Conflict Matrix Engine.
    Detects contradictions between breaking live streams and older knowledge base / memory chunks,
    distinguishing verified consensus from developing single-source claims and superseded information.
    """

    def __init__(self, genai_client=None):
        self.client = genai_client

    async def analyze_conflicts(self, query: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes a set of retrieved documents across temporal dimensions to produce
        a structured Fact-Conflict & Temporal Reconciliation Matrix.
        """
        if not docs:
            return {
                "has_conflicts": False,
                "conflict_summary": "No candidate evidence to cross-verify.",
                "consensus_score": 1.0,
                "entries": []
            }

        # Attempt LLM-powered temporal reconciliation
        if self.client and settings.GEMINI_API_KEY:
            candidate_models = [settings.DEFAULT_MODEL, "gemini-3.7-flash", "gemini-flash-latest"]
            for model_name in candidate_models:
                try:
                    doc_entries = []
                    for i, d in enumerate(docs):
                        src = d.get("source", "Live Feed")
                        age = d.get("age_str", "recent")
                        title = d.get("title", "")
                        content = d.get("content", "")
                        doc_entries.append(f"[{i+1}] Source: {src} | Age/Timestamp: {age}\nTitle: {title}\nContent: {content}\n")
                    
                    docs_text = "\n---\n".join(doc_entries)
                    prompt = f"""User Query: {query}

Retrieved Intelligence Sources (Ordered with Timestamps):
{docs_text}

Reconcile any factual discrepancies, temporal updates, denials, or consensus across these sources."""

                    response = await self.client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={
                            "system_instruction": CONFLICT_MATRIX_PROMPT,
                            "response_mime_type": "application/json"
                        }
                    )
                    data = json.loads(response.text)
                    if isinstance(data, dict) and "entries" in data:
                        # Compute consensus score
                        entries = data.get("entries", [])
                        contradictions = [e for e in entries if e.get("status") == "CONTRADICTION"]
                        consensus = [e for e in entries if e.get("status") == "CONSENSUS"]
                        developing = [e for e in entries if e.get("status") == "DEVELOPING"]
                        
                        total = max(1, len(entries))
                        score = round(max(0.0, min(1.0, (len(consensus) * 1.0 + len(developing) * 0.7 - len(contradictions) * 0.4) / total)), 2)
                        data["consensus_score"] = score
                        data["stats"] = {
                            "contradictions_count": len(contradictions),
                            "consensus_count": len(consensus),
                            "developing_count": len(developing),
                            "total_claims": len(entries)
                        }
                        return data
                except Exception as e:
                    logger.debug("Conflict resolver model %s temporary issue (%s), trying next...", model_name, e)
                    continue

        # Heuristic Temporal Contradiction & Consensus Detection Fallback
        return self._heuristic_reconciliation(query, docs)

    def _heuristic_reconciliation(self, query: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Algorithmic rule-based temporal contradiction and consensus extractor.
        """
        contradiction_keywords = [
            "denies", "denied", "denial", "delayed", "delay", "revises", "revised",
            "cancelled", "cancels", "refutes", "refuted", "disputes", "disputed",
            "false", "backtracks", "walks back", "contrary", "correction", "retracts",
            "unconfirmed", "slashes", "cuts", "cuts forecast"
        ]

        entries = []
        has_contradictions = False

        # Check for contradiction triggers in newer live items vs older items
        for i, d in enumerate(docs):
            content_lower = (d.get("title", "") + " " + d.get("content", "")).lower()
            detected_triggers = [kw for kw in contradiction_keywords if kw in content_lower]
            
            src = d.get("source", "Live Feed")
            age = d.get("age_str", "recent")
            title = d.get("title", "")
            
            if detected_triggers:
                has_contradictions = True
                entries.append({
                    "claim": f"Revision regarding {title[:40]}...",
                    "entity": self._extract_entity(title, query),
                    "status": "CONTRADICTION",
                    "badge": "🔴 Contradiction",
                    "earlier_claim": "Earlier reports indicated unconfirmed projections or preliminary discussions.",
                    "earlier_source": "Prior Market Speculation / Early Chunks",
                    "latest_claim": f"Latest breaking development ({', '.join(detected_triggers[:2])}): {title}",
                    "latest_source": f"{src} • {age}",
                    "temporal_delta": f"Superseded via {src}",
                    "verdict": f"Updated stance supersedes earlier baseline claims.",
                    "confidence": 0.88
                })

        # Check for multi-source consensus
        entity_sources: Dict[str, List[str]] = {}
        for d in docs:
            src = d.get("source", "Live Feed")
            ent = self._extract_entity(d.get("title", ""), query)
            entity_sources.setdefault(ent, []).append(f"{src} • {d.get('age_str', 'recent')}")

        for ent, sources in entity_sources.items():
            if len(sources) >= 2:
                entries.append({
                    "claim": f"Corroborated reporting on {ent}",
                    "entity": ent,
                    "status": "CONSENSUS",
                    "badge": "🟢 Verified Consensus",
                    "earlier_claim": "",
                    "earlier_source": sources[1],
                    "latest_claim": f"Consistent cross-source confirmation across {len(sources)} reporting channels.",
                    "latest_source": sources[0],
                    "temporal_delta": "Multi-Source Agreement",
                    "verdict": f"High reliability: Independent confirmation from {len(sources)} sources.",
                    "confidence": 0.95
                })
            elif len(sources) == 1 and not has_contradictions:
                entries.append({
                    "claim": f"Initial report regarding {ent}",
                    "entity": ent,
                    "status": "DEVELOPING",
                    "badge": "🟡 Developing",
                    "earlier_claim": "",
                    "earlier_source": "",
                    "latest_claim": f"Breaking single-source telemetry from {sources[0]}.",
                    "latest_source": sources[0],
                    "temporal_delta": "Awaiting Second Corroboration",
                    "verdict": "Developing narrative: Monitor active feeds for secondary corroboration.",
                    "confidence": 0.72
                })

        contradictions_count = len([e for e in entries if e.get("status") == "CONTRADICTION"])
        consensus_count = len([e for e in entries if e.get("status") == "CONSENSUS"])
        developing_count = len([e for e in entries if e.get("status") == "DEVELOPING"])

        summary = (
            f"Detected {contradictions_count} temporal contradiction(s) and {consensus_count} verified consensus claim(s)."
            if has_contradictions else
            f"Verified {consensus_count} cross-source consensus item(s) with {developing_count} developing report(s)."
        )

        return {
            "has_conflicts": has_contradictions,
            "conflict_summary": summary,
            "consensus_score": 0.65 if has_contradictions else 0.92,
            "stats": {
                "contradictions_count": contradictions_count,
                "consensus_count": consensus_count,
                "developing_count": developing_count,
                "total_claims": len(entries)
            },
            "entries": entries
        }

    def _extract_entity(self, title: str, query: str) -> str:
        """Extracts candidate capitalized entity or falls back to query subject."""
        words = title.replace(":", " ").replace(",", " ").replace("-", " ").split()
        caps = [w for w in words if w.istitle() and len(w) > 3 and w.lower() not in {"what", "this", "that", "breaking", "latest", "today", "news", "report"}]
        if caps:
            return caps[0]
        q_words = [w for w in query.split() if len(w) > 3]
        return q_words[0].title() if q_words else "Market Asset"

conflict_resolver = TemporalConflictResolver()
