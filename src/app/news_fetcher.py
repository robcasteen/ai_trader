"""
RSS news fetcher for crypto headlines.
Fetches from multiple sources, deduplicates, extracts symbols.
ALL DATA STORED IN DATABASE.
"""

import feedparser
import hashlib
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
from app.utils.symbol_normalizer import normalize_symbol
from app.database.connection import get_db
from app.database.repositories import RSSFeedRepository, SeenNewsRepository
from app.database.models import SeenNews


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
def get_headline_hash(headline: str, url: str = "") -> str:
    """Generate SHA256 hash of headline+url for deduplication."""
    combined = f"{headline}|{url}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


# MAIN FETCH FUNCTION
def get_unseen_headlines() -> Dict[str, List[Dict[str, str]]]:
    """
    Fetch unseen headlines from RSS feeds stored in database.

    Returns:
        Dict mapping symbol -> list of unseen headline dicts
        Each headline dict contains: {title, url, feed_name, feed_id}
    """
    unseen = {}

    with get_db() as db:
        feed_repo = RSSFeedRepository(db)
        seen_repo = SeenNewsRepository(db)

        # Get all enabled feeds from database
        feeds = feed_repo.get_all(enabled_only=True)

        if not feeds:
            logging.warning("[NewsFetcher] No enabled RSS feeds found in database")
            return unseen

        logging.info(f"[NewsFetcher] Fetching from {len(feeds)} enabled feeds")

        for feed in feeds:
            try:
                logging.info(f"[NewsFetcher] Fetching {feed.name} ({feed.url})")
                parsed_feed = feedparser.parse(feed.url)

                headlines_processed = 0
                headlines_new = 0

                for entry in parsed_feed.entries:
                    headlines_processed += 1

                    headline = entry.title
                    entry_url = entry.get('link', '')

                    # Check if already seen by URL (most reliable)
                    if seen_repo.is_seen_by_url(entry_url):
                        continue

                    # Extract symbol
                    symbol = extract_symbol_from_headline(headline)

                    if not symbol:
                        continue

                    # Add to unseen
                    if symbol not in unseen:
                        unseen[symbol] = []

                    unseen[symbol].append({
                        'title': headline,
                        'url': entry_url,
                        'feed_name': feed.name,
                        'feed_id': feed.id
                    })

                    headlines_new += 1

                # Update feed stats
                feed_repo.update_fetch_stats(
                    feed_id=feed.id,
                    items_fetched=headlines_processed,
                    error=None
                )

                logging.info(f"[NewsFetcher] {feed.name}: {headlines_processed} processed, {headlines_new} new")

            except Exception as e:
                logging.error(f"[NewsFetcher] Error fetching {feed.name}: {e}")
                feed_repo.update_fetch_stats(
                    feed_id=feed.id,
                    items_fetched=0,
                    error=str(e)
                )

    total_headlines = sum(len(h) for h in unseen.values())
    logging.info(f"[NewsFetcher] Found {total_headlines} unseen headlines for {len(unseen)} symbols")
    return unseen


def mark_as_seen(headlines: List[Dict[str, any]], triggered_signal: bool = False, signal_id: int = None):
    """
    Mark headlines as seen in database.

    Args:
        headlines: List of headline dicts with {title, url, feed_name, feed_id, symbol}
        triggered_signal: Whether these headlines triggered a trading signal
        signal_id: Optional ID of the signal that was triggered
    """
    with get_db() as db:
        seen_repo = SeenNewsRepository(db)

        for headline in headlines:
            seen_repo.mark_seen(
                headline=headline['title'],
                url=headline['url'],
                feed_id=headline['feed_id'],
                triggered_signal=triggered_signal,
                signal_id=signal_id
            )

        logging.info(f"[NewsFetcher] Marked {len(headlines)} headlines as seen (triggered_signal={triggered_signal})")
