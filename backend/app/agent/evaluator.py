import json
import logging
from typing import List, Dict, Any, Tuple
from ..config import settings
from .prompts import GRADER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class CorrectiveRAGEvaluator:
    """Evaluates candidate documents for relevance and filters hallucinated or noisy snippets."""

    def __init__(self, genai_client=None):
        self.client = genai_client

    async def grade_document(self, query: str, doc_content: str, doc_title: str = "") -> Tuple[float, bool, str]:
        """
        Grades an individual document.
        Returns: (relevance_score: float, is_relevant: bool, rationale: str)
        """
        # If Gemini client is active and configured
        if self.client and settings.GEMINI_API_KEY:
            candidate_models = [settings.DEFAULT_MODEL, "gemini-3.7-flash", "gemini-flash-latest"]
            for model_name in candidate_models:
                try:
                    prompt = f"""User Query: {query}
Document Title: {doc_title}
Document Content: {doc_content}

Evaluate relevance according to the guidelines."""
                    
                    response = await self.client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={
                            "system_instruction": GRADER_SYSTEM_PROMPT,
                            "response_mime_type": "application/json"
                        }
                    )
                    data = json.loads(response.text)
                    score = float(data.get("relevance_score", 0.5))
                    is_rel = bool(data.get("is_relevant", score >= 0.5))
                    rationale = data.get("rationale", f"Evaluated by {model_name} CRAG grader.")
                    return score, is_rel, rationale
                except Exception as e:
                    logger.debug("CRAG grader model %s temporary issue (%s), trying fallback...", model_name, e)
                    continue

        # Fallback Heuristic Grader
        query_terms = set(query.lower().split())
        content_lower = (doc_title + " " + doc_content).lower()
        matches = [w for w in query_terms if len(w) > 2 and w in content_lower]
        ratio = len(matches) / max(1, len(query_terms))
        
        # Base score on term overlap
        score = min(1.0, 0.4 + (ratio * 0.6))
        is_relevant = score >= 0.5
        rationale = f"Heuristic overlap matched {len(matches)} key terms ({round(score, 2)} confidence)."
        return score, is_relevant, rationale

    async def filter_documents(self, query: str, docs: List[Dict[str, Any]], 
                               min_threshold: float = 0.45) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Grades all candidate documents and filters out low-relevance noise.
        """
        graded_docs = []
        scores = []
        
        for doc in docs:
            content = doc.get("content", "")
            title = doc.get("title", doc.get("metadata", {}).get("title", ""))
            score, is_rel, rationale = await self.grade_document(query, content, title)
            
            doc_copy = dict(doc)
            doc_copy["crag_score"] = round(score, 3)
            doc_copy["crag_rationale"] = rationale
            doc_copy["crag_passed"] = is_rel and (score >= min_threshold)
            
            if doc_copy["crag_passed"]:
                graded_docs.append(doc_copy)
            scores.append(score)

        avg_confidence = round(sum(scores) / max(1, len(scores)), 2) if scores else 0.0
        summary = {
            "total_candidates": len(docs),
            "passed_count": len(graded_docs),
            "pruned_count": len(docs) - len(graded_docs),
            "average_confidence": avg_confidence,
            "quality_tier": "HIGH" if avg_confidence > 0.75 else "MEDIUM" if avg_confidence > 0.5 else "LOW"
        }
        return graded_docs, summary

evaluator = CorrectiveRAGEvaluator()
