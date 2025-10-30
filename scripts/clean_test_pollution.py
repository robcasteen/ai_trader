#!/usr/bin/env python3
"""
Clean ALL test pollution from production database.
This removes any data that was created during testing.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.database.connection import get_db
from app.database.models import Signal, Trade, Holding, SeenNews, ErrorLog
from sqlalchemy import text

def clean_all_test_data():
    """Remove all test data and start fresh."""

    with get_db() as db:
        print("Cleaning production database of test pollution...")

        # Disable FK constraints for clean deletion
        db.execute(text("PRAGMA foreign_keys = OFF"))

        # Delete all holdings (references trades and signals)
        holdings_count = db.query(Holding).delete()
        print(f"  Deleted {holdings_count} holdings")

        # Delete all trades
        trades_count = db.query(Trade).delete()
        print(f"  Deleted {trades_count} trades")

        # Delete all signals (from testing)
        signals_count = db.query(Signal).delete()
        print(f"  Deleted {signals_count} signals")

        # Delete seen news
        news_count = db.query(SeenNews).delete()
        print(f"  Deleted {news_count} seen news items")

        # Delete error logs
        errors_count = db.query(ErrorLog).delete()
        print(f"  Deleted {errors_count} error logs")

        db.commit()

        # Re-enable FK constraints
        db.execute(text("PRAGMA foreign_keys = ON"))
        db.commit()

        print("\n✓ Production database is now CLEAN!")
        print("  Ready for live trading validation")

def verify_clean_state():
    """Verify database is clean."""
    with get_db() as db:
        from app.database.models import RSSFeed

        signals = db.query(Signal).count()
        trades = db.query(Trade).count()
        holdings = db.query(Holding).count()
        feeds = db.query(RSSFeed).count()

        print(f"\nFinal state:")
        print(f"  Signals: {signals}")
        print(f"  Trades: {trades}")
        print(f"  Holdings: {holdings}")
        print(f"  RSS Feeds: {feeds}")

        if signals == 0 and trades == 0 and holdings == 0:
            print("\n✓ PRISTINE - Ready for production validation!")
        else:
            print("\n⚠ Warning: Some data still present")

if __name__ == "__main__":
    clean_all_test_data()
    verify_clean_state()
