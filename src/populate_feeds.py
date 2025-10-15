"""
Run this script to populate your dashboard with reputable crypto news RSS feeds.

Usage:
    python populate_feeds.py
"""

import json
from pathlib import Path
from datetime import datetime, timezone

# Path should be src/logs
PROJECT_ROOT = Path(__file__).resolve().parent  # If script is in project root
LOGS_DIR = PROJECT_ROOT / "src" / "logs"
RSS_FEEDS_FILE = LOGS_DIR / "rss_feeds.json"

# Ensure logs directory exists
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Comprehensive list of reputable crypto news RSS feeds
CRYPTO_FEEDS = [
    # Tier 1 - Major crypto news sites
    {
        "name": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "description": "Leading crypto news and analysis"
    },
    {
        "name": "CoinTelegraph",
        "url": "https://cointelegraph.com/rss",
        "description": "Global blockchain and crypto news"
    },
    {
        "name": "CryptoPotato",
        "url": "https://cryptopotato.com/feed/",
        "description": "Crypto news and price analysis"
    },
    {
        "name": "Decrypt",
        "url": "https://decrypt.co/feed",
        "description": "Bitcoin, Ethereum, and Web3 news"
    },
    {
        "name": "The Block",
        "url": "https://www.theblock.co/rss.xml",
        "description": "Institutional crypto news"
    },
    {
        "name": "Bitcoin Magazine",
        "url": "https://bitcoinmagazine.com/.rss/full/",
        "description": "Original Bitcoin-focused publication"
    },
    
    # Tier 2 - Quality crypto news sources
    {
        "name": "CoinJournal",
        "url": "https://coinjournal.net/feed/",
        "description": "Crypto news and educational content"
    },
    {
        "name": "BeInCrypto",
        "url": "https://beincrypto.com/feed/",
        "description": "Market analysis and breaking news"
    },
    {
        "name": "Bitcoin.com News",
        "url": "https://news.bitcoin.com/feed/",
        "description": "Bitcoin and crypto ecosystem news"
    },
    {
        "name": "CryptoSlate",
        "url": "https://cryptoslate.com/feed/",
        "description": "Blockchain and crypto news"
    },
    {
        "name": "NewsBTC",
        "url": "https://www.newsbtc.com/feed/",
        "description": "Bitcoin and altcoin news"
    },
    {
        "name": "U.Today",
        "url": "https://u.today/rss",
        "description": "Crypto news and market updates"
    },
    
    # Tier 3 - Specialized and technical sources
    {
        "name": "Bitcoinist",
        "url": "https://bitcoinist.com/feed/",
        "description": "Bitcoin news and analysis"
    },
    {
        "name": "CryptoNews",
        "url": "https://cryptonews.com/news/feed/",
        "description": "Latest cryptocurrency news"
    },
    {
        "name": "AMBCrypto",
        "url": "https://ambcrypto.com/feed/",
        "description": "Crypto market analysis"
    },
    {
        "name": "Crypto Briefing",
        "url": "https://cryptobriefing.com/feed/",
        "description": "Research-driven crypto news"
    },
    {
        "name": "CoinGape",
        "url": "https://coingape.com/feed/",
        "description": "Cryptocurrency and blockchain news"
    },
    {
        "name": "CCN",
        "url": "https://www.ccn.com/feed/",
        "description": "Bitcoin and financial news"
    },
]


def create_feeds_file():
    """Create rss_feeds.json with all crypto news sources."""
    
    feeds = []
    
    for i, feed_info in enumerate(CRYPTO_FEEDS, start=1):
        feed = {
            "id": i,
            "name": feed_info["name"],
            "url": feed_info["url"],
            "status": "active",
            "last_fetch": None,
            "headlines_count": 0,
            "relevant_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "description": feed_info.get("description", "")
        }
        feeds.append(feed)
    
    # Save to file
    with RSS_FEEDS_FILE.open("w") as f:
        json.dump(feeds, f, indent=2)
    
    print(f"✅ Created {RSS_FEEDS_FILE}")
    print(f"📰 Added {len(feeds)} crypto news feeds:")
    print()
    
    for feed in feeds:
        print(f"  {feed['id']:2d}. {feed['name']:<25} - {feed['url']}")
    
    print()
    print("🚀 Ready to use! Click 'Run Now' on your dashboard.")


def main():
    if RSS_FEEDS_FILE.exists():
        response = input(f"⚠️  {RSS_FEEDS_FILE} already exists. Overwrite? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Cancelled. No changes made.")
            return
    
    create_feeds_file()


if __name__ == "__main__":
    main()