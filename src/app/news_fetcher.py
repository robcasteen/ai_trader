"""
Updated news_scanner.py - Integrates with Dashboard Feed Manager

Replace your existing news_scanner.py with this version.
"""

import feedparser
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # /src/app
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

NEWS_FILE = LOGS_DIR / "seen_news.json"
RSS_FEEDS_FILE = LOGS_DIR / "rss_feeds.json"


def get_rss_feeds():
    """
    Load RSS feeds from dashboard configuration.
    Falls back to hardcoded feeds if none configured.
    """
    feeds = load_dashboard_feeds()
    
    if feeds:
        logging.info(f"[RSS] Loaded {len(feeds)} feeds from dashboard")
        return feeds
    
    # Fallback to hardcoded feeds
    logging.warning("[RSS] No dashboard feeds found, using defaults")
    default_feeds = [
        {
            "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "name": "CoinDesk",
            "id": None
        },
        {
            "url": "https://cointelegraph.com/rss",
            "name": "CoinTelegraph",
            "id": None
        },
        {
            "url": "https://cryptopotato.com/feed/",
            "name": "CryptoPotato",
            "id": None
        },
    ]
    
    # Save defaults to dashboard if file doesn't exist
    if not RSS_FEEDS_FILE.exists():
        save_default_feeds(default_feeds)
    
    return default_feeds


def load_dashboard_feeds() -> List[Dict]:
    """Load active RSS feeds from dashboard configuration."""
    try:
        if not RSS_FEEDS_FILE.exists():
            return []
        
        with RSS_FEEDS_FILE.open("r") as f:
            feeds = json.load(f)
        
        if not isinstance(feeds, list):
            return []
        
        # Only return active feeds with URLs
        active_feeds = [
            f for f in feeds 
            if f.get("status") == "active" and f.get("url")
        ]
        
        return active_feeds
        
    except Exception as e:
        logging.error(f"[RSS] Failed to load dashboard feeds: {e}")
        return []


def save_default_feeds(feeds: List[Dict]):
    """Save default feeds to dashboard on first run."""
    try:
        dashboard_feeds = []
        for i, feed in enumerate(feeds, start=1):
            dashboard_feeds.append({
                "id": i,
                "name": feed.get("name", "Unknown"),
                "url": feed["url"],
                "status": "active",
                "last_fetch": None,
                "headlines_count": 0,
                "relevant_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        
        with RSS_FEEDS_FILE.open("w") as f:
            json.dump(dashboard_feeds, f, indent=2)
        
        logging.info(f"[RSS] Initialized dashboard with {len(dashboard_feeds)} default feeds")
        
    except Exception as e:
        logging.error(f"[RSS] Failed to save default feeds: {e}")


def update_feed_stats(feed_id: Optional[int], headlines_count: int, relevant_count: int, error: str = None):
    """Update feed statistics after fetching."""
    if feed_id is None:
        return  # Skip update for legacy feeds
    
    try:
        if not RSS_FEEDS_FILE.exists():
            return
        
        with RSS_FEEDS_FILE.open("r") as f:
            feeds = json.load(f)
        
        # Find and update the feed
        for feed in feeds:
            if feed.get("id") == feed_id:
                feed["last_fetch"] = datetime.now(timezone.utc).isoformat()
                feed["headlines_count"] = headlines_count
                feed["relevant_count"] = relevant_count
                
                if error:
                    feed["status"] = "error"
                    feed["error"] = error
                else:
                    feed["status"] = "active"
                    feed.pop("error", None)
                
                break
        
        with RSS_FEEDS_FILE.open("w") as f:
            json.dump(feeds, f, indent=2)
            
    except Exception as e:
        logging.error(f"[RSS] Failed to update feed stats: {e}")


def get_headline_hash(headline: str) -> str:
    return hashlib.sha256(headline.encode()).hexdigest()


def load_seen() -> dict:
    if not NEWS_FILE.exists():
        return {}
    try:
        with open(NEWS_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_seen(seen: dict):
    with open(NEWS_FILE, "w") as f:
        json.dump(seen, f, indent=2)


def extract_symbol_from_headline(headline: str) -> str | None:
    headline = headline.upper()
    for symbol in [
        "BTC",
        "ETH",
        "SOL",
        "XRP",
        "ADA",
        "DOGE",
        "AVAX",
        "MATIC",
        "LTC",
        "AAVE",
        "LINK",
        "1INCH",
        "UNI",
        "XLM",
        "ATOM",
        "DOT",
        "SHIB",
        "TRX",
    ]:
        if symbol in headline:
            return f"{symbol}USD"
    return None


def get_unseen_headlines() -> dict[str, list[str]]:
    """
    Returns dict: symbol -> [list of unseen headlines].
    """
    seen = load_seen()
    unseen: dict[str, list[str]] = {}
    
    feeds = get_rss_feeds()
    
    if not feeds:
        logging.warning("[RSS] No feeds available to fetch from")
        return unseen

    for feed_config in feeds:
        url = feed_config.get("url")
        feed_id = feed_config.get("id")
        feed_name = feed_config.get("name", "Unknown")
        
        if not url:
            continue
        
        try:
            logging.info(f"[RSS] Fetching from {feed_name}: {url}")
            feed = feedparser.parse(url)
            
            if feed.bozo:
                error_msg = str(feed.get("bozo_exception", "Parse error"))
                logging.error(f"[RSS] Error parsing {feed_name}: {error_msg}")
                update_feed_stats(feed_id, 0, 0, error_msg)
                continue
            
            total_count = len(feed.entries)
            relevant_count = 0
            
            for entry in feed.entries:
                headline = entry.title.strip()
                symbol = extract_symbol_from_headline(headline)
                
                if not symbol:
                    continue
                
                relevant_count += 1
                headline_hash = get_headline_hash(headline)
                
                if headline_hash not in seen.get(symbol, []):
                    unseen.setdefault(symbol, []).append(headline)
            
            logging.info(f"[RSS] {feed_name}: {relevant_count}/{total_count} relevant headlines")
            update_feed_stats(feed_id, total_count, relevant_count)
            
        except Exception as e:
            error_msg = str(e)
            logging.error(f"[RSS] Failed to fetch {feed_name}: {error_msg}")
            update_feed_stats(feed_id, 0, 0, error_msg)

    logging.info(f"[RSS] Found {sum(len(h) for h in unseen.values())} total unseen headlines across {len(unseen)} symbols")
    return unseen


def mark_as_seen(symbol: str, headlines: list[str]):
    """
    Mark these headlines for `symbol` as seen.
    Keeps only last 50 hashes per symbol.
    """
    seen = load_seen()
    if symbol not in seen:
        seen[symbol] = []

    for h in headlines:
        hhash = get_headline_hash(h)
        if hhash not in seen[symbol]:
            seen[symbol].append(hhash)

    # keep only last 50
    seen[symbol] = seen[symbol][-50:]
    save_seen(seen)