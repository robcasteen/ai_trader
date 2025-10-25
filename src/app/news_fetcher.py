"""
RSS news fetcher for crypto headlines.
Fetches from multiple sources, deduplicates, extracts symbols.
"""

import feedparser
import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from app.utils.symbol_normalizer import normalize_symbol

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"
NEWS_FILE = LOGS_DIR / "seen_news.json"


# RSS FEEDS
def get_rss_feeds():
    """
    Return list of RSS feed objects from rss_feeds.json.
    Only returns active feeds.
    """
    import json
    from pathlib import Path
    
    feeds_file = Path(__file__).parent / "logs" / "rss_feeds.json"
    
    try:
        if not feeds_file.exists():
            logging.warning(f"[RSS] Feed file not found: {feeds_file}")
            # Fallback to hardcoded feeds
            return [
                {"url": "https://cointelegraph.com/rss", "name": "CoinTelegraph", "active": True},
                {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "name": "CoinDesk", "active": True},
                {"url": "https://decrypt.co/feed", "name": "Decrypt", "active": True},
            ]
        
        with open(feeds_file) as f:
            all_feeds = json.load(f)
        
        # Filter to only active feeds
        active_feeds = [feed for feed in all_feeds if feed.get("active") == True]
        
        logging.info(f"[RSS] Loaded {len(active_feeds)} active feeds from {len(all_feeds)} total")
        
        return active_feeds
        
    except Exception as e:
        logging.error(f"[RSS] Error loading feeds: {e}")
        # Fallback to hardcoded feeds
        return [
            {"url": "https://cointelegraph.com/rss", "name": "CoinTelegraph", "active": True},
            {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "name": "CoinDesk", "active": True},
            {"url": "https://decrypt.co/feed", "name": "Decrypt", "active": True},
        ]




# SYMBOL EXTRACTION
def extract_symbol_from_headline(headline: str) -> Optional[str]:
    """
    Extract crypto symbol from headline text.
    Returns canonical normalized symbol (e.g., BTCUSD, ETHUSD).
    """
    headline_lower = headline.lower()
    
    # Keywords to search for in headlines
    keywords = [
        "bitcoin", "btc",
        "ethereum", "eth",
        "solana", "sol",
        "xrp", "ripple",
        "cardano", "ada",
        "dogecoin", "doge",
        "polkadot", "dot",
        "chainlink", "link",
        "uniswap", "uni",
        "stellar", "xlm",
        "litecoin", "ltc",
        "cosmos", "atom",
        "avalanche", "avax",
        "polygon", "matic",
        "aave",
        "shiba", "shib",
    ]
    
    for keyword in keywords:
        if keyword in headline_lower:
            try:
                return normalize_symbol(keyword)
            except ValueError:
                # Symbol not recognized by normalizer, skip
                continue
    
    return None


# HEADLINE HASHING
def get_headline_hash(headline: str) -> str:
    """Generate SHA256 hash of headline for deduplication."""
    return hashlib.sha256(headline.encode()).hexdigest()


# PERSISTENCE
def load_seen() -> Dict[str, List[str]]:
    """Load seen headline hashes from file."""
    if not NEWS_FILE.exists():
        return {}
    
    try:
        with open(NEWS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_seen(seen_data: Dict[str, List[str]]):
    """Save seen headlines to file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(NEWS_FILE, 'w') as f:
        json.dump(seen_data, f, indent=2)


def mark_as_seen(symbol: str, headlines: List[str]):
    """Mark headlines as seen for a symbol."""
    seen = load_seen()
    
    if symbol not in seen:
        seen[symbol] = []
    
    for headline in headlines:
        h = get_headline_hash(headline)
        if h not in seen[symbol]:
            seen[symbol].append(h)
    
    # Keep only last 50 hashes per symbol
    seen[symbol] = seen[symbol][-50:]
    
    save_seen(seen)


# MAIN FETCH FUNCTION
def get_unseen_headlines() -> Dict[str, List[str]]:
    """
    Fetch unseen headlines from RSS feeds.
    
    Returns:
        Dict mapping symbol -> list of unseen headlines
    """
    seen = load_seen()
    unseen = {}
    
    feeds = get_rss_feeds()
    
    for feed in feeds:
        # Handle both dict feeds (new) and string URLs (backward compatibility)
        if isinstance(feed, dict):
            feed_url = feed.get("url")
            feed_name = feed.get("name", "Unknown")
        else:
            # Backward compatibility with old string-based feeds
            feed_url = feed
            feed_name = feed_url
        
        try:
            parsed_feed = feedparser.parse(feed_url)
            
            for entry in parsed_feed.entries:
                headline = entry.title
                symbol = extract_symbol_from_headline(headline)
                
                if not symbol:
                    continue
                
                # Check if seen
                h = get_headline_hash(headline)
                if symbol in seen and h in seen[symbol]:
                    continue
                
                # Add to unseen
                if symbol not in unseen:
                    unseen[symbol] = []
                unseen[symbol].append(headline)
            
            logging.info(f"[NewsFetcher] Processed {feed_name} ({feed_url})")
        
        except Exception as e:
            logging.error(f"[NewsFetcher] Error fetching {feed_name}: {e}")
    
    logging.info(f"[NewsFetcher] Found unseen headlines for {len(unseen)} symbols")
    return unseen

    """
    Fetch unseen headlines from RSS feeds.
    
    Returns:
        Dict mapping symbol -> list of unseen headlines
    """
    seen = load_seen()
    unseen = {}
    
    for feed_url in get_rss_feeds():
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                headline = entry.title
                symbol = extract_symbol_from_headline(headline)
                
                if not symbol:
                    continue
                
                # Check if seen
                h = get_headline_hash(headline)
                if symbol in seen and h in seen[symbol]:
                    continue
                
                # Add to unseen
                if symbol not in unseen:
                    unseen[symbol] = []
                unseen[symbol].append(headline)
            
            logging.info(f"[NewsFetcher] Processed {feed_url}")
        
        except Exception as e:
            logging.error(f"[NewsFetcher] Error fetching {feed_url}: {e}")
    
    logging.info(f"[NewsFetcher] Found unseen headlines for {len(unseen)} symbols")
    return unseen