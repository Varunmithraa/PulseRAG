import asyncio
import time
import re
import random
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from google import genai
from google.genai import types

from ..config import settings
from ..storage.database import db
from ..stream.live_buffer import live_stream_buffer

logger = logging.getLogger(__name__)

# High-impact intelligence triggers
CRITICAL_TRIGGERS = {
    "breaking", "emergency", "crisis", "war", "attack", "sanctions", "military",
    "crash", "plunge", "soar", "zero-day", "exploit", "antitrust", "lawsuit",
    "rate cut", "rate hike", "bank run", "liquidity", "shutdown", "ban", "tariffs",
    "resigns", "ousted", "fired", "indicted", "hostile takeover"
}

HIGH_TRIGGERS = {
    "acquisition", "merger", "investigation", "outage", "billion", "trillion",
    "regulatory", "sec", "fed", "inflation", "gdp", "default", "cyberattack",
    "breakthrough", "frontier", "quantum", "semiconductor", "tsmc", "nvidia",
    "openai", "deepmind", "anthropic", "bitcoin", "ethereum", "etf", "patent"
}

SIMULATED_SCENARIOS = [
    {
        "headline": "BREAKING: US Federal Reserve convenes emergency liquidity session amid global sovereign yield volatility",
        "source": "Bloomberg Market Wire",
        "category": "Macro Finance",
        "content": "Federal Reserve governors have scheduled an unannounced inter-meeting consultation on cross-border dollar clearing and sovereign paper stability, citing rapid shifts in treasury yields.",
        "tickers": ["SPY", "TLT", "DXY"]
    },
    {
        "headline": "BREAKING: Anthropic & OpenAI announce joint frontier safety verification standard backed by US & UK AI Safety Institutes",
        "source": "TechCrunch AI & Enterprise",
        "category": "AI / Tech",
        "content": "Leading AI laboratories have agreed to an unprecedented unified benchmark and autonomous agent capability threshold, triggering mandatory pre-deployment audits for next-generation models.",
        "tickers": ["MSFT", "GOOGL", "NVDA"]
    },
    {
        "headline": "BREAKING: European Commission opens formal antitrust investigation into cloud AI compute bundling and exclusive silicon contracts",
        "source": "Reuters Global Business",
        "category": "Global Macro",
        "content": "EU antitrust regulators have issued formal requests for information to hyperscalers regarding GPU capacity tie-ins and proprietary model acceleration agreements.",
        "tickers": ["AMZN", "MSFT", "NVDA"]
    },
    {
        "headline": "BREAKING: Bitcoin surpasses new all-time high as major European sovereign wealth fund authorizes 2% treasury reserve allocation",
        "source": "CoinDesk Market Wire",
        "category": "Crypto & Web3",
        "content": "Government fiscal authorities in Europe confirmed an inaugural digital asset allocation to counter currency debasement, prompting institutional spot inflows.",
        "tickers": ["BTC", "ETH", "COIN"]
    },
    {
        "headline": "BREAKING: Critical zero-day vulnerability disclosed in core Linux kernel network stack affecting major global cloud providers",
        "source": "Ars Technica Systems & Security",
        "category": "Systems & Cloud",
        "content": "Security researchers have released proof-of-concept mitigation details for an unauthenticated remote execution vulnerability in widespread cloud virtualization hypervisors.",
        "tickers": ["CRWD", "PANW", "NET"]
    }
]

class AutonomousAlertMonitor:
    """
    Autonomous background intelligence agent:
    Continuously monitors the temporal stream buffer, detects high-impact market/tech/geopolitical
    catalysts, cross-references user memory/watchlists, and generates proactive executive briefings.
    """

    def __init__(self):
        self.processed_ids: set = set()
        self.is_running = False
        self.subscribers: List[asyncio.Queue] = []
        self._scenario_idx = 0
        self._init_genai()

    def _init_genai(self):
        self.client = None
        if settings.GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception as e:
                logger.warning("Alert Monitor: Failed to initialize Gemini client: %s", e)

    def _calculate_impact_score(self, event: Dict[str, Any]) -> float:
        """Computes a normalized impact score (0.0 to 1.0) based on signals and user watchlists."""
        text = f"{event.get('title', '')} {event.get('content', '')}".lower()
        score = 0.25  # baseline score for live news

        # 1. Critical keyword triggers
        crit_matches = sum(1 for kw in CRITICAL_TRIGGERS if kw in text)
        if crit_matches > 0:
            score += min(0.40, crit_matches * 0.20)

        # 2. High keyword triggers
        high_matches = sum(1 for kw in HIGH_TRIGGERS if kw in text)
        if high_matches > 0:
            score += min(0.25, high_matches * 0.10)

        # 3. User Memory / Watchlist Cross-Reference Boost
        try:
            facts = db.get_facts_for_user("default_user")
            for fact in facts:
                key = fact.get("entity_key", "").lower()
                content = fact.get("fact_content", "").lower()
                if (key and key in text) or any(t.lower() in text for t in re.findall(r"\b[A-Za-z0-9]{2,}\b", content)[:10]):
                    score += 0.30
                    break
        except Exception:
            pass

        # 4. Source / Category Weighting
        cat = event.get("category", "")
        if cat in ["Macro Finance", "Global Macro", "AI / Tech", "Enterprise AI"]:
            score += 0.10

        return min(1.0, score)

    async def _generate_briefing(self, headline: str, content: str, source: str, impact_level: str) -> str:
        """Synthesizes a 2-sentence executive impact assessment via Gemini or deterministic fallback."""
        if self.client:
            models_to_try = [
                settings.DEFAULT_MODEL,
                "gemini-3.8-flash",
                "gemini-3.7-flash",
                "gemini-flash-latest"
            ]
            prompt = (
                f"You are an autonomous intelligence officer. "
                f"Analyze this breaking event in EXACTLY TWO concise, professional sentences. "
                f"Sentence 1: State the core strategic event and why it is {impact_level} impact. "
                f"Sentence 2: Explain the direct market, geopolitical, or operational consequence.\n\n"
                f"Event: {headline}\nSource: {source}\nDetails: {content[:300]}"
            )
            for m in models_to_try:
                try:
                    resp = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.2,
                            max_output_tokens=150
                        )
                    )
                    text = resp.text.strip()
                    if text:
                        return text
                except Exception:
                    continue

        # Instant deterministic fallback (zero lag, 100% reliable)
        clean_content = content.replace("\n", " ").strip()
        first_detail = clean_content[:180] if clean_content else "No additional dispatch text available."
        return (
            f"This development marks a significant catalyst from {source} that warrants immediate executive attention. "
            f"Early implications point to heightened volatility and strategic reassessment across affected sectors: {first_detail}..."
        )

    async def evaluate_and_alert(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Evaluates an event and generates an autonomous alert if impact crosses threshold."""
        if not event or event.get("id") in self.processed_ids:
            return None

        self.processed_ids.add(event.get("id"))
        score = self._calculate_impact_score(event)

        # Threshold for alerting: score >= 0.65
        if score < 0.65:
            return None

        impact_level = "CRITICAL" if score >= 0.85 else "HIGH"
        headline = event.get("title", "Breaking Intelligence Event")
        content = event.get("content", "")
        source = event.get("source", "Live Stream Radar")
        category = event.get("category", "Live Intelligence")

        briefing = await self._generate_briefing(headline, content, source, impact_level)

        suggested_query = f"Provide an in-depth impact briefing and strategic risks regarding: '{headline}'"

        alert_id = f"alt_{int(time.time() * 1000)}_{random.randint(100, 999)}"
        alert = {
            "id": alert_id,
            "event_id": event.get("id", ""),
            "headline": headline,
            "source": source,
            "category": category,
            "impact_score": round(score, 2),
            "impact_level": impact_level,
            "autonomous_briefing": briefing,
            "suggested_query": suggested_query,
            "tickers": event.get("tickers", []),
            "timestamp": time.time(),
            "datetime_iso": datetime.utcnow().isoformat(),
            "read": False
        }

        # Persist alert to SQLite
        try:
            db.save_alert(alert)
        except Exception as e:
            logger.error("Failed to persist autonomous alert: %s", e)

        # Broadcast to active subscribers
        await self._broadcast_alert(alert)
        logger.info("Autonomous Alert Triggered [%s - Score %.2f]: %s", impact_level, score, headline)
        return alert

    async def _broadcast_alert(self, alert: Dict[str, Any]):
        dead = []
        for q in self.subscribers:
            try:
                q.put_nowait(alert)
            except Exception:
                dead.append(q)
        for q in dead:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=30)
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self.subscribers:
            self.subscribers.remove(q)

    async def simulate_alert(self, custom_headline: Optional[str] = None) -> Dict[str, Any]:
        """Injects a simulated high-impact breaking event and generates a live alert immediately."""
        if custom_headline:
            scenario = {
                "headline": custom_headline,
                "source": "Simulated Live Radar",
                "category": "Breaking News",
                "content": f"Urgent dispatch: {custom_headline}. Market and geopolitical telemetry indicates heightened sensitivity.",
                "tickers": ["SPY", "NVDA", "BTC"]
            }
        else:
            scenario = SIMULATED_SCENARIOS[self._scenario_idx % len(SIMULATED_SCENARIOS)]
            self._scenario_idx += 1

        # Push into live stream buffer
        event = live_stream_buffer.add_event(
            title=scenario["headline"],
            content=scenario["content"],
            source=scenario["source"],
            category=scenario["category"],
            tickers=scenario["tickers"],
            timestamp=time.time()
        )

        # Force evaluation & alert generation
        alert = await self.evaluate_and_alert(event)
        if not alert:
            # Fallback guarantee
            alert = {
                "id": f"alt_{int(time.time() * 1000)}_sim",
                "event_id": event["id"],
                "headline": scenario["headline"],
                "source": scenario["source"],
                "category": scenario["category"],
                "impact_score": 0.94,
                "impact_level": "CRITICAL",
                "autonomous_briefing": f"Simulated autonomous trigger: {scenario['content'][:140]}. Immediate monitoring recommended.",
                "suggested_query": f"Analyze the strategic impact of: {scenario['headline']}",
                "tickers": scenario["tickers"],
                "timestamp": time.time(),
                "datetime_iso": datetime.utcnow().isoformat(),
                "read": False
            }
            db.save_alert(alert)
            await self._broadcast_alert(alert)

        return alert

    def get_alerts_overview(self, limit: int = 50) -> Dict[str, Any]:
        """Returns alerts with unread counter and critical tally."""
        alerts = db.get_alerts(limit=limit)
        unread = len([a for a in alerts if not a.get("read")])
        critical = len([a for a in alerts if a.get("impact_level") == "CRITICAL"])
        return {
            "alerts": alerts,
            "total_count": len(alerts),
            "unread_count": unread,
            "critical_count": critical
        }

    async def start_worker(self):
        """Background continuous monitor loop."""
        self.is_running = True
        logger.info("Autonomous Intel Alert Monitor worker started.")
        while self.is_running:
            try:
                # Inspect recent events in temporal buffer
                recent_events = live_stream_buffer.get_recent(20)
                for evt in reversed(recent_events):
                    if evt.get("id") not in self.processed_ids:
                        await self.evaluate_and_alert(evt)
                        await asyncio.sleep(0.5)

                await asyncio.sleep(8)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Alert Monitor worker error: %s", e)
                await asyncio.sleep(8)

alert_monitor = AutonomousAlertMonitor()
