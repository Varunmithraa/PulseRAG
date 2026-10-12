import asyncio
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from google import genai
from google.genai import types

from ..config import settings
from ..storage.database import db
from ..stream.live_buffer import live_stream_buffer

logger = logging.getLogger(__name__)

class ExecutiveBriefingGenerator:
    """
    Synthesizes real-time temporal stream events and long-term user watchlists into a 
    cohesive 60-second oral intelligence dispatch for audio playback and executive reading.
    """

    def __init__(self):
        self.last_briefing: Optional[Dict[str, Any]] = None
        self._init_genai()

    def _init_genai(self):
        self.client = None
        if settings.GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                logger.warning("Briefing Generator: Failed to initialize Gemini client: %s", e)

    def _categorize_events(self, events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Buckets live stream events into thematic intelligence pillars."""
        buckets = {
            "macro_world": [],
            "ai_tech": [],
            "crypto_markets": [],
            "other": []
        }

        for ev in events:
            text = f"{ev.get('title', '')} {ev.get('category', '')} {ev.get('source', '')}".lower()
            if any(k in text for k in ["bitcoin", "crypto", "ethereum", "coindesk", "token", "web3"]):
                buckets["crypto_markets"].append(ev)
            elif any(k in text for k in ["ai", "techcrunch", "model", "llm", "semiconductor", "hacker news", "venturebeat", "mit", "verge", "ars", "chip"]):
                buckets["ai_tech"].append(ev)
            elif any(k in text for k in ["bbc", "yahoo", "finance", "fed", "treasury", "president", "war", "market", "economy", "trade"]):
                buckets["macro_world"].append(ev)
            else:
                buckets["other"].append(ev)

        return buckets

    async def _generate_llm_script(self, events: List[Dict[str, Any]], facts: List[Dict[str, Any]]) -> Optional[str]:
        """Prompts Gemini to synthesize a natural spoken radio-style executive dispatch."""
        if not self.client:
            return None

        # Build concise context block
        event_lines = []
        for e in events[:10]:
            event_lines.append(f"- [{e.get('source', 'Web')}] {e.get('title', '')}: {e.get('content', '')[:120]}")
        events_context = "\n".join(event_lines)

        user_context = ""
        if facts:
            fact_lines = [f"- {f.get('entity_key')}: {f.get('fact_content')}" for f in facts[:4]]
            user_context = "User Focus & Preferences:\n" + "\n".join(fact_lines)

        prompt = (
            "You are an executive intelligence anchor broadcasting a 60-second live spoken briefing "
            "called 'PulseRAG Intelligence Dispatch'.\n"
            "Synthesize the following live stream news items into a single, cohesive, engaging spoken script.\n"
            "CRITICAL INSTRUCTIONS FOR AUDIO DELIVERY:\n"
            "1. Write clear, conversational sentences designed for spoken voice. Do NOT include markdown, asterisks, bullet points, headers, or quotes.\n"
            "2. Structure smoothly: Start with an energetic greeting and the leading global macro story, move into technology and AI breakthroughs, touch upon market/digital asset sentiment, and conclude with a crisp strategic takeaway.\n"
            "3. Keep the total length between 140 and 190 words (approximately 60 to 75 seconds when spoken).\n\n"
            f"Live Web Data:\n{events_context}\n\n{user_context}"
        )

        models_to_try = [
            settings.DEFAULT_MODEL,
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-flash-latest"
        ]

        for m in models_to_try:
            try:
                resp = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=300
                    )
                )
                text = resp.text.strip()
                # Clean up any lingering markdown asterisks or hashes
                clean = text.replace("**", "").replace("*", "").replace("##", "").replace("#", "").strip()
                if clean and len(clean.split()) > 40:
                    return clean
            except Exception as e:
                logger.debug("Briefing LLM model %s failed: %s", m, e)
                continue

        return None

    def _generate_fallback_script(self, events: List[Dict[str, Any]], buckets: Dict[str, List[Dict[str, Any]]]) -> str:
        """Deterministic high-quality spoken synthesis if LLM is offline or unconfigured."""
        lead_macro = buckets["macro_world"][0]["title"] if buckets["macro_world"] else (events[0]["title"] if events else "Global markets and news streams remain active")
        lead_tech = buckets["ai_tech"][0]["title"] if buckets["ai_tech"] else "Leading tech hubs report continuous development in cloud systems and intelligence tooling"
        lead_crypto = buckets["crypto_markets"][0]["title"] if buckets["crypto_markets"] else "Digital asset volumes demonstrate steady liquidity across primary exchanges"

        return (
            f"Good day, and welcome to your PulseRAG live executive briefing. "
            f"In global developments and macro news, our live radar tracks that {lead_macro}. "
            f"Turning to technology and enterprise innovation, key headlines highlight that {lead_tech}. "
            f"Meanwhile in market sentiment and digital assets, {lead_crypto}. "
            f"Our autonomous temporal engine continues to monitor incoming feeds in real time. "
            f"Stay tuned as new dispatches flow into the live buffer."
        )

    async def generate_briefing(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Produces a complete executive voice briefing package with transcript, summary, and citations."""
        # Return recent cache if generated within the last 60 seconds unless force_refresh is requested
        now = time.time()
        if not force_refresh and self.last_briefing and (now - self.last_briefing.get("timestamp", 0) < 60):
            return self.last_briefing

        events = live_stream_buffer.get_recent(30)
        facts = db.get_facts_for_user("default_user")
        buckets = self._categorize_events(events)

        # 1. Attempt LLM voice script generation
        transcript = await self._generate_llm_script(events, facts)
        
        # 2. Fallback to deterministic template if needed
        if not transcript:
            transcript = self._generate_fallback_script(events, buckets)

        # 3. Assemble executive summary bullet points for reading
        summary_points = []
        for cat_name, label in [("macro_world", "Global & Macro"), ("ai_tech", "AI & Technology"), ("crypto_markets", "Markets & Crypto")]:
            if buckets[cat_name]:
                item = buckets[cat_name][0]
                summary_points.append({
                    "pillar": label,
                    "headline": item.get("title", ""),
                    "source": item.get("source", ""),
                    "url": item.get("url", "")
                })
            elif events:
                # fill with first unused
                item = events[min(len(summary_points), len(events) - 1)]
                summary_points.append({
                    "pillar": label,
                    "headline": item.get("title", ""),
                    "source": item.get("source", ""),
                    "url": item.get("url", "")
                })

        # 4. Sources cited
        sources_cited = list({e.get("source") for e in events if e.get("source")})[:6]
        word_count = len(transcript.split())
        est_seconds = max(30, round(word_count / 2.3))  # average speaking rate ~140 wpm

        dt = datetime.now()
        date_str = dt.strftime("%B %d, %Y • %H:%M")

        briefing_pkg = {
            "status": "success",
            "title": "PulseRAG Live Executive Briefing",
            "date_formatted": date_str,
            "timestamp": now,
            "datetime_iso": dt.isoformat(),
            "transcript": transcript,
            "word_count": word_count,
            "estimated_duration_seconds": est_seconds,
            "summary_points": summary_points,
            "sources_cited": sources_cited,
            "total_events_analyzed": len(events)
        }

        self.last_briefing = briefing_pkg
        logger.info("Generated Executive Voice Briefing (%d words, ~%ds duration)", word_count, est_seconds)
        return briefing_pkg

briefing_generator = ExecutiveBriefingGenerator()
