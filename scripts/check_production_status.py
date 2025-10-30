#!/usr/bin/env python3
"""
Check production environment status.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.database.connection import get_db
from app.database.models import (
    Signal, Trade, Holding, RSSFeed, BotStatus,
    StrategyPerformance, StrategyDefinition, SeenNews
)

def check_status():
    """Check all database tables."""

    with get_db() as db:
        print("=== PRODUCTION DATABASE STATUS ===\n")

        # Core data
        print("Core Trading Data:")
        print(f"  Signals: {db.query(Signal).count()} (test_mode=False: {db.query(Signal).filter(Signal.test_mode==False).count()})")
        print(f"  Trades: {db.query(Trade).count()} (test_mode=False: {db.query(Trade).filter(Trade.test_mode==False).count()})")
        print(f"  Holdings: {db.query(Holding).count()}")

        # RSS Feeds
        print(f"\nRSS Feeds: {db.query(RSSFeed).count()}")
        feeds = db.query(RSSFeed).all()
        for feed in feeds[:5]:
            print(f"  {feed.name}: enabled={feed.enabled}")
        if len(feeds) > 5:
            print(f"  ... and {len(feeds) - 5} more")

        # Strategy Performance
        print(f"\nStrategy Performance: {db.query(StrategyPerformance).count()}")
        perf = db.query(StrategyPerformance).all()
        for p in perf:
            print(f"  {p.strategy_name}: {p.total_signals} signals")

        # Strategy Definitions
        print(f"\nStrategy Definitions: {db.query(StrategyDefinition).count()}")
        defs = db.query(StrategyDefinition).all()
        for d in defs:
            print(f"  {d.name}: enabled={d.enabled}")

        # Bot Status
        print(f"\nBot Status Records: {db.query(BotStatus).count()}")
        status = db.query(BotStatus).order_by(BotStatus.timestamp.desc()).first()
        if status:
            print(f"  Last: {status.status} at {status.timestamp}")

        # Seen News
        print(f"\nSeen News: {db.query(SeenNews).count()}")

        print("\n=== END STATUS ===")

if __name__ == "__main__":
    check_status()
