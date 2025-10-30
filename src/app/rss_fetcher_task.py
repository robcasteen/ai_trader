"""
Background RSS Feed Fetcher - Database Only

Fetches RSS feeds from configured sources and saves headlines to database.
NO JSON files are used - everything goes to database.
"""

import logging
import feedparser
from datetime import datetime, timezone
from typing import List, Dict, Optional
from app.database.connection import get_db
from app.database.repositories import RSSFeedRepository


def fetch_all_rss_feeds():
    """
    Fetch all enabled RSS feeds and update database.

    This runs as a background task every N minutes.
    """
    logging.info("[RSSFetcher] Starting RSS feed fetch cycle")

    with get_db() as db:
        feed_repo = RSSFeedRepository(db)
        feeds = feed_repo.get_all()

        enabled_feeds = [f for f in feeds if f.enabled]
        logging.info(f"[RSSFetcher] Found {len(enabled_feeds)} enabled feeds out of {len(feeds)} total")

        for feed in enabled_feeds:
            try:
                fetch_single_feed(feed, db)
            except Exception as e:
                logging.error(f"[RSSFetcher] Error fetching {feed.name}: {e}")
                # Update error count and last_error in database
                feed.error_count = (feed.error_count or 0) + 1
                feed.last_error = str(e)
                db.commit()

        logging.info("[RSSFetcher] RSS feed fetch cycle complete")


def fetch_single_feed(feed, db):
    """
    Fetch a single RSS feed and save headlines to database.

    Args:
        feed: RSSFeed model instance
        db: Database session
    """
    logging.info(f"[RSSFetcher] Fetching {feed.name} from {feed.url}")

    try:
        # Parse RSS feed
        parsed = feedparser.parse(feed.url)

        if parsed.bozo:  # Feed has errors
            error_msg = f"Feed parse error: {parsed.bozo_exception}"
            logging.warning(f"[RSSFetcher] {feed.name}: {error_msg}")
            feed.last_error = error_msg
            feed.error_count = (feed.error_count or 0) + 1

        entries = parsed.entries
        logging.info(f"[RSSFetcher] {feed.name}: Retrieved {len(entries)} entries")

        # Update feed metadata
        feed.last_fetch = datetime.now(timezone.utc)
        feed.total_items_fetched = (feed.total_items_fetched or 0) + len(entries)

        # TODO: Save headlines to a Headline table
        # For now, we'll just update the feed's last_fetch time
        # Next step: Create Headline table and HeadlineRepository

        db.commit()

        logging.info(f"[RSSFetcher] {feed.name}: Successfully fetched and updated")

    except Exception as e:
        error_msg = f"Failed to fetch feed: {e}"
        logging.error(f"[RSSFetcher] {feed.name}: {error_msg}")
        feed.last_error = error_msg
        feed.error_count = (feed.error_count or 0) + 1
        db.commit()
        raise
