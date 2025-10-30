#!/usr/bin/env python3
"""
Restore production data from backups after testing cleanup.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.database.connection import get_db
from app.database.repositories import RSSFeedRepository, BotConfigRepository
from app.database.models import Signal
from decimal import Decimal

def restore_rss_feeds():
    """Restore RSS feeds from backup."""
    backup_file = Path(__file__).parent.parent / "backups/pre_mongodb_20251025_140028/rss_feeds.json"

    with open(backup_file, 'r') as f:
        feeds_data = json.load(f)

    with get_db() as db:
        repo = RSSFeedRepository(db)

        # Only restore feeds with valid crypto URLs (skip test data)
        valid_feeds = [f for f in feeds_data if 'example.com' not in f['url']]

        for feed in valid_feeds:
            # Check if feed already exists
            existing = repo.get_by_url(feed['url'])
            if not existing:
                repo.create(
                    name=feed.get('name', ''),
                    url=feed['url'],
                    enabled=feed.get('active', True)
                )
                print(f"Restored feed: {feed['name']}")
            else:
                print(f"Feed already exists: {feed['name']}")

        db.commit()

def restore_bot_config():
    """Restore bot configuration if missing."""
    with get_db() as db:
        repo = BotConfigRepository(db)
        config = repo.get_current()

        if not config:
            config = repo.create_or_update(
                mode='paper',
                min_confidence=Decimal('0.5'),
                position_size=Decimal('0.03'),
                balance=Decimal('200.0')
            )
            db.commit()
            print(f"Created bot config: mode={config.mode}, min_confidence={config.min_confidence}")
        else:
            print(f"Bot config already exists: mode={config.mode}")

def clean_test_signals():
    """Remove any test signals that got created."""
    with get_db() as db:
        test_signals = db.query(Signal).filter(Signal.test_mode == True).delete()
        db.commit()
        print(f"Cleaned {test_signals} test signals")

def main():
    print("Restoring production data...")

    print("\n1. Restoring RSS feeds...")
    restore_rss_feeds()

    print("\n2. Restoring bot configuration...")
    restore_bot_config()

    print("\n3. Cleaning test signals...")
    clean_test_signals()

    print("\n✓ Production data restored!")

    # Show final counts
    with get_db() as db:
        from app.database.models import RSSFeed, Trade, Signal
        feeds = db.query(RSSFeed).count()
        trades = db.query(Trade).filter(Trade.test_mode == False).count()
        signals = db.query(Signal).filter(Signal.test_mode == False).count()

        print(f"\nCurrent production data:")
        print(f"  RSS Feeds: {feeds}")
        print(f"  Trades: {trades}")
        print(f"  Signals: {signals}")

if __name__ == "__main__":
    main()
