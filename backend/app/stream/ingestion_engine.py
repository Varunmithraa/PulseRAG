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

class LiveIngestionEngine:
    """Orchestrates live RSS fetching and real-time broadcaster pipelines."""

    def __init__(self):
        self.is_running = False
        self.subscribers: List[asyncio.Queue] = []

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
                counter += 1
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Live Ingestion Engine loop error: %s", e)
                await asyncio.sleep(5)

ingestion_engine = LiveIngestionEngine()
