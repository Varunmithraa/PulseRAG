import asyncio
import time
import random
import logging
from typing import List, Dict, Any, Callable, Optional
import feedparser
import aiohttp
from .live_buffer import live_stream_buffer

logger = logging.getLogger(__name__)

# Pre-configured discoverable catalog of verified live sources
FEED_CATALOG = [
    {
        "id": "yahoo_finance",
        "name": "Yahoo Finance News",
        "url": "https://finance.yahoo.com/news/rssindex",
        "category": "Macro Finance",
        "description": "Wall St headlines, macroeconomic indicators, Treasury yields, and earnings reports."
    },
    {
        "id": "techcrunch_ai",
        "name": "TechCrunch AI & Enterprise",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "category": "AI / Tech",
        "description": "Foundational LLM announcements, enterprise AI deployments, and startup rounds."
    },
    {
        "id": "hacker_news",
        "name": "Hacker News Top Stories",
        "url": "https://news.ycombinator.com/rss",
        "category": "Tech Ecosystem",
        "description": "Trending open-source systems, engineering architecture discussions, and breakthroughs."
    },
    {
        "id": "coindesk",
        "name": "CoinDesk Market Wire",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "category": "Crypto & Web3",
        "description": "Cryptocurrency market swings, Bitcoin ETFs, macro liquidity, and blockchain policy."
    },
    {
        "id": "venturebeat_ai",
        "name": "VentureBeat AI Channel",
        "url": "https://venturebeat.com/category/ai/feed/",
        "category": "Enterprise AI",
        "description": "Enterprise generative AI, datacenter chip battles, and agentic workflows."
    },
    {
        "id": "mit_tech_review",
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "category": "Deep Tech",
        "description": "Quantum computing, advanced semiconductors, biotechnology, and frontier AI research."
    },
    {
        "id": "bbc_business",
        "name": "BBC Business & Global Markets",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "category": "Global Macro",
        "description": "International central bank decisions, currency shifts, and global trade dynamics."
    },
    {
        "id": "the_verge",
        "name": "The Verge Tech Hub",
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "Tech Ecosystem",
        "description": "Hardware platforms, cloud operating systems, and big tech regulatory investigations."
    },
    {
        "id": "ars_technica",
        "name": "Ars Technica Systems & Security",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "category": "Systems & Cloud",
        "description": "Datacenter server hardware, security vulnerabilities, and silicon fabrication."
    }
]

class LiveIngestionEngine:
    """Orchestrates dynamic live RSS feeds, 1-click source linking, and real-time broadcasters."""

    def __init__(self):
        self.is_running = False
        self.subscribers: List[asyncio.Queue] = []
        
        # Currently linked & polling feeds (keyed by unique name)
        self.active_feeds: Dict[str, Dict[str, Any]] = {}
        self._init_default_feeds()

    def _init_default_feeds(self):
        """Initializes default pre-linked feeds."""
        for item in FEED_CATALOG[:3]:
            self.active_feeds[item["name"]] = {
                "id": item["id"],
                "name": item["name"],
                "url": item["url"],
                "category": item["category"],
                "description": item["description"],
                "enabled": True,
                "item_count": 0,
                "last_fetched": None
            }

    def get_feeds_overview(self) -> Dict[str, Any]:
        """Returns currently active feeds and the discoverable catalog with link statuses."""
        active_list = list(self.active_feeds.values())
        active_names = {f["name"] for f in active_list if f["enabled"]}
        
        catalog_with_status = []
        for cat_item in FEED_CATALOG:
            item_copy = dict(cat_item)
            item_copy["is_linked"] = cat_item["name"] in active_names
            catalog_with_status.append(item_copy)

        return {
            "active_count": len([f for f in active_list if f["enabled"]]),
            "active_feeds": active_list,
            "catalog": catalog_with_status
        }

    def link_feed(self, name: str, url: str, category: str = "Live Web", description: str = "") -> Dict[str, Any]:
        """Dynamically links a new feed and triggers an immediate async fetch."""
        feed_obj = {
            "id": f"feed_{int(time.time())}",
            "name": name.strip(),
            "url": url.strip(),
            "category": category.strip(),
            "description": description.strip() or f"Live feed for {name}",
            "enabled": True,
            "item_count": 0,
            "last_fetched": None
        }
        self.active_feeds[name.strip()] = feed_obj
        
        # Immediately fetch from this newly linked feed in background
        asyncio.create_task(self.fetch_rss_feed(feed_obj))
        logger.info("Dynamically linked live feed: %s (%s)", name, url)
        return feed_obj

    def unlink_feed(self, name: str) -> bool:
        """Removes a feed from active polling."""
        if name in self.active_feeds:
            del self.active_feeds[name]
            logger.info("Unlinked live feed: %s", name)
            return True
        return False

    def toggle_feed(self, name: str, enabled: bool) -> bool:
        """Pauses or resumes polling for a feed without deleting it."""
        if name in self.active_feeds:
            self.active_feeds[name]["enabled"] = enabled
            if enabled:
                asyncio.create_task(self.fetch_rss_feed(self.active_feeds[name]))
            return True
        return False

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
        asyncio.create_task(self.broadcast_event(event))
        return event

    async def fetch_rss_feed(self, feed_info: Dict[str, Any]):
        """Asynchronously parses an external RSS feed and loads items into the temporal buffer."""
        feed_name = feed_info.get("name", "Unknown Feed")
        url = feed_info.get("url", "")
        if not url:
            return

        try:
            headers = {"User-Agent": "PulseRAG-LiveIntelligence/1.0"}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6), headers=headers) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        parsed = feedparser.parse(content)
                        new_items_count = 0
                        
                        recent_titles = {e["title"] for e in live_stream_buffer.get_recent(35)}
                        for entry in parsed.entries[:4]:
                            title = getattr(entry, "title", "").strip()
                            summary = getattr(entry, "summary", getattr(entry, "description", "")).strip()
                            link = getattr(entry, "link", "").strip()
                            
                            if title and title not in recent_titles:
                                event = live_stream_buffer.add_event(
                                    title=title,
                                    content=summary[:350],
                                    source=feed_name,
                                    url=link,
                                    category=feed_info.get("category", "Live Web"),
                                    timestamp=time.time()
                                )
                                new_items_count += 1
                                await self.broadcast_event(event)

                        if feed_name in self.active_feeds:
                            self.active_feeds[feed_name]["item_count"] += new_items_count
                            self.active_feeds[feed_name]["last_fetched"] = time.strftime("%H:%M:%S")
        except Exception as e:
            logger.debug("Failed RSS fetch for %s: %s", feed_name, e)

    async def start_worker(self):
        """Continuous background worker polling all active linked feeds."""
        self.is_running = True
        logger.info("Live Ingestion Engine dynamic worker started.")
        counter = 0
        while self.is_running:
            try:
                # Poll active enabled feeds every 45 seconds (or immediately on startup)
                if counter % 9 == 0:
                    current_active = [f for f in self.active_feeds.values() if f.get("enabled", True)]
                    for feed in current_active:
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
