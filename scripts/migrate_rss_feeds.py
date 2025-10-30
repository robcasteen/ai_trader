#!/usr/bin/env python3
"""
Migrate RSS feeds from JSON file to database.
"""
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.database.connection import get_db
from app.database.repositories import RSSFeedRepository

def migrate_rss_feeds():
    """Migrate RSS feeds from JSON to database."""

    # Load from JSON file
    json_file = Path(__file__).parent.parent / "src/app/logs/rss_feeds.json"

    if not json_file.exists():
        print(f"❌ RSS feeds file not found: {json_file}")
        return

    with open(json_file, 'r') as f:
        feeds_data = json.load(f)

    print(f"📄 Found {len(feeds_data)} feeds in JSON file")

    # Migrate to database
    migrated = 0
    skipped = 0

    with get_db() as db:
        repo = RSSFeedRepository(db)

        for feed in feeds_data:
            url = feed.get('url')
            name = feed.get('name', 'Unknown')
            enabled = feed.get('enabled', True) or feed.get('active', True)
            keywords = feed.get('keywords', [])

            if not url:
                print(f"⚠️  Skipping feed with no URL: {feed}")
                skipped += 1
                continue

            # Check if already exists
            existing = repo.get_by_url(url)
            if existing:
                print(f"⏭️  Feed already exists: {name} ({url})")
                skipped += 1
                continue

            # Create new feed
            try:
                new_feed = repo.create(
                    url=url,
                    name=name,
                    enabled=enabled,
                    keywords=keywords
                )
                print(f"✅ Migrated: {name} ({url})")
                migrated += 1
            except Exception as e:
                print(f"❌ Failed to migrate {name}: {e}")
                skipped += 1

    print(f"\n📊 Migration complete!")
    print(f"   ✅ Migrated: {migrated}")
    print(f"   ⏭️  Skipped: {skipped}")
    print(f"   📄 Total: {len(feeds_data)}")

if __name__ == "__main__":
    migrate_rss_feeds()
