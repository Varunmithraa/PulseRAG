import asyncio
import time
import random
import logging
from typing import List, Dict, Any, Callable, Optional
import feedparser
import aiohttp
from .live_buffer import live_stream_buffer

logger = logging.getLogger(__name__)

# Real public RSS endpoints
DEFAULT_RSS_FEEDS = [
    {
        "name": "Yahoo Finance News",
        "url": "https://finance.yahoo.com/news/rssindex",
        "category": "Macro Finance"
    },
    {
        "name": "TechCrunch AI & Enterprise",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "category": "AI / Tech"
    },
    {
        "name": "Hacker News Top Stories",
        "url": "https://news.ycombinator.com/rss",
        "category": "Tech Ecosystem"
    }
]

# Realistic simulated breaking events for immediate demonstration & tests
MOCK_EVENT_TEMPLATES = [
    {
        "title": "NVIDIA Finalizes Blackwell B200 Liquid-Cooling Server Architecture",
        "content": "NVIDIA engineering teams alongside OEM partners have completed qualification of revised liquid-cooling distribution manifolds for the GB200 NVL72 rack systems. Volume shipments remain on track for hyperscaler datacenters.",
        "source": "TechWire Live",
        "category": "AI Hardware",
        "tickers": ["NVDA", "TSM", "SMCI"]
    },
    {
        "title": "TSMC Reports 3nm Wafer Yields Surpass 85% for Advanced Packaging",
        "content": "Taiwan Semiconductor Manufacturing Co. (TSMC) announced significant throughput enhancements in its CoWoS-L advanced packaging capacity in Taichung, cutting lead times for flagship AI accelerators by 3 weeks.",
        "source": "SemiAnalysis Radar",
        "category": "Semiconductors",
        "tickers": ["TSM", "ASML", "NVDA"]
    },
    {
        "title": "Federal Reserve Open Market Committee Signals Data-Dependent Policy Rate Stance",
        "content": "Federal Reserve Chair reiterated that future benchmark rate adjustments will hinge on upcoming core PCE and employment readings. Treasury yields held steady around 4.12% across the 10-year curve.",
        "source": "MacroPulse Markets",
        "category": "Macro Finance",
        "tickers": ["SPY", "QQQ"]
    },
    {
        "title": "OpenAI Releases Next-Gen Reasoning Model API with Native Tool Verification",
        "content": "OpenAI has expanded enterprise availability of its latest multimodal reasoning model featuring built-in formal verification and deterministic JSON schemas, targeting regulated industries.",
        "source": "AI Insider Daily",
        "category": "AI / Tech",
        "tickers": ["MSFT", "GOOGL"]
    },
    {
        "title": "ASML Ships Next High-NA EUV Twinscan Scanner to Leading Foundry",
        "content": "ASML confirmed successful delivery of its second commercial High-NA EUV lithography tool with 0.55 NA optics, laying ground for sub-2nm process nodes slated for 2026 volume production.",
        "source": "Semiconductor World",
        "category": "Semiconductors",
        "tickers": ["ASML", "INTC", "TSM"]
    },
    {
        "title": "AMD Expands ROCm 6.3 Open-Source AI Software Stack with vLLM Acceleration",
        "content": "AMD announced deep integration of its ROCm 6.3 acceleration libraries with vLLM and TensorRT-LLM runtimes, narrowing the software gap with CUDA for Instinct MI300X enterprise clusters.",
        "source": "HPC Wire",
        "category": "AI Hardware",
        "tickers": ["AMD", "NVDA"]
    }
]

class LiveIngestionEngine:
    """Orchestrates live RSS fetching, simulated event emissions, and broadcaster pipelines."""

    def __init__(self):
        self.is_running = False
        self.subscribers: List[asyncio.Queue] = []
        self._seed_initial_events()

    def _seed_initial_events(self):
        """Populates the buffer with initial temporal events spanning the last 4 hours."""
        now = time.time()
        for i, item in enumerate(MOCK_EVENT_TEMPLATES):
            # Spread timestamps from 10 minutes ago to 3.5 hours ago
            simulated_ts = now - (i * 1800 + random.randint(120, 600))
            live_stream_buffer.add_event(
                title=item["title"],
                content=item["content"],
                source=item["source"],
                category=item["category"],
                tickers=item.get("tickers", []),
                timestamp=simulated_ts
            )

    def subscribe(self) -> asyncio.Queue:
        """Subscribes an SSE or WebSocket client queue to live incoming events."""
        q = asyncio.Queue(maxsize=50)
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self.subscribers:
            self.subscribers.remove(q)

    async def broadcast_event(self, event: Dict[str, Any]):
        """Pushes an incoming event to all active UI subscribers."""
        dead_queues = []
        for q in self.subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead_queues.append(q)
        for q in dead_queues:
            self.unsubscribe(q)

    def inject_event(self, title: str, content: str, source: str = "User Injected", 
                     category: str = "Live Alert", tickers: Optional[List[str]] = None) -> Dict[str, Any]:
        """Allows instant user or external API injection of breaking news."""
        event = live_stream_buffer.add_event(
            title=title,
            content=content,
            source=source,
            category=category,
            tickers=tickers or [],
            timestamp=time.time()
        )
        # Asynchronously schedule broadcast
        asyncio.create_task(self.broadcast_event(event))
        return event

    async def fetch_rss_feed(self, feed_info: Dict[str, str]):
        """Asynchronously parses an external RSS feed."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(feed_info["url"]) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        parsed = feedparser.parse(content)
                        for entry in parsed.entries[:3]:
                            title = getattr(entry, "title", "")
                            summary = getattr(entry, "summary", getattr(entry, "description", ""))
                            link = getattr(entry, "link", "")
                            if title and not any(e["title"] == title for e in live_stream_buffer.get_recent(20)):
                                event = live_stream_buffer.add_event(
                                    title=title,
                                    content=summary[:350],
                                    source=feed_info["name"],
                                    url=link,
                                    category=feed_info["category"],
                                    timestamp=time.time()
                                )
                                await self.broadcast_event(event)
        except Exception as e:
            logger.debug("Failed RSS fetch for %s: %s", feed_info["name"], e)

    async def start_worker(self):
        """Continuous background task fetching RSS and generating periodic live events."""
        self.is_running = True
        logger.info("Live Ingestion Engine worker started.")
        counter = 0
        while self.is_running:
            try:
                # 1. Fetch RSS every 60 seconds
                if counter % 12 == 0:
                    for feed in DEFAULT_RSS_FEEDS:
                        await self.fetch_rss_feed(feed)
                        await asyncio.sleep(1)

                # 2. Every 25 seconds, emit a simulated market event if buffer is active
                if counter % 5 == 0 and random.random() > 0.4:
                    template = random.choice(MOCK_EVENT_TEMPLATES)
                    event = live_stream_buffer.add_event(
                        title=f"[UPDATE] {template['title']}",
                        content=template["content"],
                        source="Live Market Ticker",
                        category=template["category"],
                        tickers=template.get("tickers", []),
                        timestamp=time.time()
                    )
                    await self.broadcast_event(event)

                counter += 1
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Live Ingestion Engine loop error: %s", e)
                await asyncio.sleep(5)

ingestion_engine = LiveIngestionEngine()
