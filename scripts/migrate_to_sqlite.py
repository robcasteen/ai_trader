"""
Migration script: JSON files → SQLite database

Cleanly migrates data with validation and test mode tagging.
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.database.connection import get_db, init_db, get_table_counts
from app.database.models import Signal, Trade, Holding, RSSFeed, SeenNews, ErrorLog

# File locations
SRC_DIR = Path(__file__).parent.parent / "src"
LOGS_DIR = SRC_DIR / "app" / "logs"


def load_jsonl(filepath):
    """Load JSONL file."""
    records = []
    if not filepath.exists():
        print(f"⚠️  File not found: {filepath}")
        return records

    with open(filepath, 'r') as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"⚠️  Error parsing line {line_num} in {filepath}: {e}")
    return records


def load_json(filepath):
    """Load JSON file."""
    if not filepath.exists():
        print(f"⚠️  File not found: {filepath}")
        return [] if "trades" in str(filepath) or "seen_news" in str(filepath) else {}

    with open(filepath, 'r') as f:
        return json.load(f)


def is_test_trade(trade):
    """Determine if a trade is test data."""
    amount = float(trade.get('amount', 0))
    price = float(trade.get('price', 0))

    # Test data has zero amounts or unrealistic values
    if amount == 0:
        return True
    if amount > 1000:  # Unrealistically large
        return True
    if price > 200000:  # BTC > $200k is test data
        return True

    return False


def migrate_signals(db):
    """Migrate signal data."""
    print("\n" + "=" * 80)
    print("MIGRATING SIGNALS")
    print("=" * 80)

    # Load from ACTIVE location (src/app/logs)
    signals_file = LOGS_DIR / "strategy_signals.jsonl"
    signals = load_jsonl(signals_file)

    print(f"Found {len(signals)} signals in {signals_file}")

    # Filter to recent signals only (last 48 hours)
    cutoff = datetime.now().timestamp() - (48 * 3600)
    recent_signals = []

    for sig in signals:
        try:
            ts = datetime.fromisoformat(sig['timestamp'].replace('Z', '+00:00'))
            if ts.timestamp() > cutoff:
                recent_signals.append(sig)
        except:
            pass

    print(f"Keeping {len(recent_signals)} recent signals (last 48 hours)")

    # Insert into database
    inserted = 0
    for sig in recent_signals:
        try:
            # Parse timestamp
            ts = datetime.fromisoformat(sig['timestamp'].replace('Z', '+00:00')).replace(tzinfo=None)

            # Determine if test mode (signals with test symbols or unrealistic data)
            test_mode = (
                sig.get('symbol', '').startswith('TEST') or
                float(sig.get('price', 0)) > 200000
            )

            signal = Signal(
                timestamp=ts,
                symbol=sig['symbol'],
                price=Decimal(str(sig['price'])),
                final_signal=sig['final_signal'],
                final_confidence=Decimal(str(sig.get('final_confidence', 0))),
                aggregation_method=sig.get('aggregation_method', 'weighted_average'),
                strategies=sig.get('strategies', {}),
                test_mode=test_mode,
                bot_version="1.0.0",
                signal_metadata=sig.get('metadata')
            )

            db.add(signal)
            inserted += 1

        except Exception as e:
            print(f"⚠️  Error migrating signal: {e}")
            continue

    db.commit()
    print(f"✓ Migrated {inserted} signals")

    return inserted


def migrate_trades(db):
    """Migrate trade data."""
    print("\n" + "=" * 80)
    print("MIGRATING TRADES")
    print("=" * 80)

    trades_file = LOGS_DIR / "trades.json"
    trades = load_json(trades_file)

    print(f"Found {len(trades)} trades in {trades_file}")

    # Separate test and production trades
    test_trades = [t for t in trades if is_test_trade(t)]
    prod_trades = [t for t in trades if not is_test_trade(t)]

    print(f"  Test trades: {len(test_trades)}")
    print(f"  Production trades: {len(prod_trades)}")

    # Insert all trades with proper test_mode flag
    inserted = 0
    for trade_data in trades:
        try:
            ts = datetime.fromisoformat(trade_data['timestamp']).replace(tzinfo=None)

            trade = Trade(
                timestamp=ts,
                action=trade_data['action'],
                symbol=trade_data['symbol'],
                price=Decimal(str(trade_data['price'])),
                amount=Decimal(str(trade_data['amount'])),
                gross_value=Decimal(str(trade_data.get('gross_value', 0))),
                fee=Decimal(str(trade_data.get('fee', 0))),
                net_value=Decimal(str(trade_data.get('net_value', 0))),
                test_mode=is_test_trade(trade_data),
                bot_version="1.0.0",
                reason=trade_data.get('reason'),
                strategies_used=[]  # TODO: Parse from reason
            )

            db.add(trade)
            inserted += 1

        except Exception as e:
            print(f"⚠️  Error migrating trade: {e}")
            continue

    db.commit()
    print(f"✓ Migrated {inserted} trades ({len(prod_trades)} production, {len(test_trades)} test)")

    return inserted


def migrate_rss_feeds(db):
    """Migrate RSS feed configurations."""
    print("\n" + "=" * 80)
    print("MIGRATING RSS FEEDS")
    print("=" * 80)

    feeds_file = LOGS_DIR / "rss_feeds.json"
    feeds_data = load_json(feeds_file)

    if not feeds_data:
        print("No RSS feeds to migrate")
        return 0

    inserted = 0
    for feed_data in feeds_data:
        try:
            feed = RSSFeed(
                url=feed_data['url'],
                name=feed_data.get('name', feed_data['url']),
                enabled=feed_data.get('enabled', True),
                keywords=feed_data.get('keywords', [])
            )

            db.add(feed)
            inserted += 1

        except Exception as e:
            print(f"⚠️  Error migrating feed: {e}")
            continue

    db.commit()
    print(f"✓ Migrated {inserted} RSS feeds")

    return inserted


def main():
    """Run migration."""
    print("=" * 80)
    print("KRAKEN AI BOT - DATABASE MIGRATION")
    print("=" * 80)

    # Initialize database
    print("\n1. Initializing SQLite database...")
    init_db()

    # Show current state
    print("\n2. Current database state:")
    counts = get_table_counts()
    for table, count in counts.items():
        if count > 0:
            print(f"   {table}: {count} records")

    # Confirm migration
    print("\n3. Migration source:")
    print(f"   Signals: {LOGS_DIR / 'strategy_signals.jsonl'}")
    print(f"   Trades: {LOGS_DIR / 'trades.json'}")
    print(f"   RSS Feeds: {LOGS_DIR / 'rss_feeds.json'}")

    response = input("\nProceed with migration? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled")
        return

    # Run migrations
    with get_db() as db:
        signal_count = migrate_signals(db)
        trade_count = migrate_trades(db)
        feed_count = migrate_rss_feeds(db)

    # Show final state
    print("\n" + "=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)

    final_counts = get_table_counts()
    print(f"\nFinal database state:")
    print(f"  Total Signals: {final_counts['signals']}")
    print(f"    Production: {final_counts['prod_signals']}")
    print(f"    Test: {final_counts['test_signals']}")
    print(f"  Total Trades: {final_counts['trades']}")
    print(f"    Production: {final_counts['prod_trades']}")
    print(f"    Test: {final_counts['test_trades']}")
    print(f"  RSS Feeds: {final_counts['rss_feeds']}")

    print(f"\n✓ Database location: data/trading_bot.db")
    print(f"✓ Ready to use!")


if __name__ == "__main__":
    main()
