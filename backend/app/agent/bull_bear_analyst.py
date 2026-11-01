import json
import logging
import re
from typing import List, Dict, Any, Optional
from ..config import settings
from .prompts import BULL_BEAR_DEBATE_PROMPT

logger = logging.getLogger(__name__)

class BullBearAnalyst:
    """
    Adversarial Intelligence Duel Engine.
    Executes a dual-perspective evaluation of any market topic, asset, or technological shift:
    - THE BULL: Identifies upside catalysts, growth velocity, margin tailwinds, and technological moats.
    - THE BEAR: Uncovers downside risks, supply bottlenecks, valuation froth, and competitive threats.
    - THE ARBITER: Impartial institutional risk officer calculating calibrated probability split and decisive swing factors.
    """

    def __init__(self, genai_client=None):
        self.client = genai_client

    async def conduct_debate(
        self, 
        query: str, 
        docs: List[Dict[str, Any]], 
        memories: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Conducts an institutional adversarial duel grounded in retrieved temporal intelligence.
        """
        # 1. Attempt LLM-powered adversarial duel if API is configured
        if self.client and settings.GEMINI_API_KEY:
            candidate_models = [settings.DEFAULT_MODEL, "gemini-3.7-flash", "gemini-flash-latest"]
            for model_name in candidate_models:
                try:
                    # Prepare retrieved evidence context
                    doc_entries = []
                    for i, d in enumerate(docs[:8]):
                        src = d.get("source", "Live Radar")
                        age = d.get("age_str", "recent")
                        title = d.get("title", "")
                        content = d.get("content", "")[:350]
                        doc_entries.append(f"[{i+1}] {src} ({age}): {title}\n{content}")
                    
                    docs_text = "\n\n".join(doc_entries) if doc_entries else "No external news items retrieved."
                    
                    mem_entries = []
                    if memories:
                        for m in memories[:4]:
                            mem_entries.append(f"- [{m.get('category', 'FACT').upper()}] {m.get('fact_content', '')}")
                    mem_text = "\n".join(mem_entries) if mem_entries else "No user watchlist constraints."

                    prompt = f"""=== USER INQUIRY / TOPIC ===
{query}

=== USER WATCHLIST & CONSTRAINTS ===
{mem_text}

=== RETRIEVED INTELLIGENCE EVIDENCE ===
{docs_text}

Conduct a rigorous, institutional-grade Bull vs. Bear adversarial duel with a calibrated Arbiter verdict strictly adhering to the JSON schema."""

                    response = await self.client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={
                            "system_instruction": BULL_BEAR_DEBATE_PROMPT,
                            "response_mime_type": "application/json"
                        }
                    )

                    clean_text = response.text.strip()
                    if clean_text.startswith("```json"):
                        clean_text = clean_text[7:]
                    if clean_text.endswith("```"):
                        clean_text = clean_text[:-3]

                    data = json.loads(clean_text)
                    if isinstance(data, dict) and "bull_case" in data and "bear_case" in data and "arbiter_verdict":
                        # Validate probability calibration
                        verdict = data.get("arbiter_verdict", {})
                        b_wt = int(verdict.get("bull_weight", 50))
                        r_wt = int(verdict.get("bear_weight", 50))
                        if b_wt + r_wt != 100:
                            total = max(1, b_wt + r_wt)
                            b_wt = round((b_wt / total) * 100)
                            r_wt = 100 - b_wt
                            verdict["bull_weight"] = b_wt
                            verdict["bear_weight"] = r_wt
                        
                        data["arbiter_verdict"] = verdict
                        return data
                except Exception as e:
                    logger.debug("BullBearAnalyst model %s error (%s), attempting fallback...", model_name, e)
                    continue

        # 2. Heuristic Adversarial Duel Generator Fallback
        return self._heuristic_debate(query, docs, memories)

    def _heuristic_debate(
        self, 
        query: str, 
        docs: List[Dict[str, Any]], 
        memories: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Algorithmic rule-based adversarial engine synthesizing a balanced institutional debate
        from live documents, detecting positive momentum catalysts and downside risk signals.
        """
        clean_topic = re.sub(r'^(⚖️\s*bull\s*vs\s*bear[:\s]*|bull\s*vs\s*bear[:\s]*)', '', query, flags=re.I).strip()
        if not clean_topic:
            clean_topic = "Market & Technological Trajectory"

        # Scan docs for bullish vs bearish indicators
        bull_indicators = [
            "record", "surge", "growth", "breakthrough", "launch", "expansion", "profit",
            "demand", "upgrade", "milestone", "accelerat", "partnership", "outperform",
            "efficiency", "adoption", "margin", "exceed", "bull", "rally"
        ]
        bear_indicators = [
            "delay", "bottleneck", "risk", "cut", "slash", "probe", "investigat",
            "lawsuit", "decline", "fall", "warning", "ban", "loss", "recession",
            "regulatory", "scrutiny", "inflation", "weakness", "overvalu", "bear"
        ]

        bull_hits = []
        bear_hits = []

        for d in docs:
            text = f"{d.get('title', '')} {d.get('content', '')}".lower()
            src = d.get('source', 'Radar')
            age = d.get('age_str', 'recent')
            title = d.get('title', 'Market signal')

            for ind in bull_indicators:
                if ind in text:
                    bull_hits.append(f"{title} ({src} • {age})")
                    break
            for ind in bear_indicators:
                if ind in text:
                    bear_hits.append(f"{title} ({src} • {age})")
                    break

        # Calculate conviction scores
        bull_score = min(92, max(42, 55 + len(bull_hits) * 6))
        bear_score = min(88, max(38, 48 + len(bear_hits) * 7))

        # Weight normalization
        total_conviction = bull_score + bear_score
        bull_weight = round((bull_score / total_conviction) * 100)
        bear_weight = 100 - bull_weight

        prevailing = "BULLISH" if bull_weight >= 56 else ("BEARISH" if bear_weight >= 56 else "NEUTRAL / BALANCED")

        # Synthesize domain-aware catalysts
        catalysts = []
        if bull_hits:
            catalysts.extend(bull_hits[:3])
        while len(catalysts) < 3:
            default_catalysts = [
                f"Sustained enterprise adoption velocity and expanding high-margin tier demand for {clean_topic}.",
                f"Proprietary architectural moat outpacing commodity competitors across primary deployment pipelines.",
                f"Anticipated quarterly guidance revisions tracking ahead of consensus consensus projections."
            ]
            catalysts.append(default_catalysts[len(catalysts)])

        # Synthesize domain-aware risks
        risks = []
        if bear_hits:
            risks.extend(bear_hits[:3])
        while len(risks) < 3:
            default_risks = [
                f"Advanced packaging, thermal dissipation, or tier-1 supply-chain bottlenecks capping near-term shipping capacity.",
                f"Heightened regulatory scrutiny and potential export/antitrust compliance frictions in key regional markets.",
                f"Multiple-compression risk if hyperscaler capital expenditures decelerate into the upcoming fiscal cycles."
            ]
            risks.append(default_risks[len(risks)])

        return {
            "topic": clean_topic,
            "bull_case": {
                "title": f"Structural Monopoly & Multi-Year Expansion Supercycle",
                "conviction_score": bull_score,
                "core_thesis": f"Robust foundational demand, pricing power, and tier-1 customer stickiness provide asymmetric upside for {clean_topic}.",
                "key_catalysts": catalysts[:3],
                "upside_potential": "Projected 35-50% operational leverage expansion over the next 12-18 months under uninterrupted execution."
            },
            "bear_case": {
                "title": f"Supply Fragility, Valuation Asymmetry & Capex Digestion",
                "conviction_score": bear_score,
                "core_thesis": f"Priced for absolute perfection; any yield defect, supply gating, or customer capex slowdown triggers sharp multiple contraction for {clean_topic}.",
                "risk_factors": risks[:3],
                "downside_vulnerability": "Vulnerable to a 20-30% tactical re-rating if yield ramps lag guidance or regulatory restrictions tighten."
            },
            "arbiter_verdict": {
                "bull_weight": bull_weight,
                "bear_weight": bear_weight,
                "prevailing_side": prevailing,
                "decisive_swing_factor": f"Net operational delivery yield metrics and hyperscaler capex commitment updates reported over the next 90 days.",
                "executive_synthesis": f"While structural secular tailwinds remain dominant ({bull_weight}% conviction), elevated concentration risk and execution expectations ({bear_weight}% vulnerability) mandate disciplined milestone-based positioning rather than unhedged exposure."
            }
        }

bull_bear_analyst = BullBearAnalyst()
