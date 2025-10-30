#!/usr/bin/env python3
"""
Backfill Historical Market Data for Backtesting

Fetches historical OHLCV data from Kraken for all tracked symbols
and caches it in the database for backtesting.

Usage:
    python scripts/backfill_market_data.py --days 90 --interval 5m
    python scripts/backfill_market_data.py --verify-only
"""

import sys
import os
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.database.connection import get_db
from app.backtesting.historical_data import HistoricalDataFetcher
from app.database.repositories import HistoricalOHLCVRepository

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Symbols to fetch (normalized format)
SYMBOLS = [
    "BTCUSD",   # Bitcoin
    "ETHUSD",   # Ethereum
    "XRPUSD",   # Ripple
    "ADAUSD",   # Cardano
    "SOLUSD",   # Solana
    "DOTUSD",   # Polkadot
    "LINKUSD",  # Chainlink
    "UNIUSD",   # Uniswap
    "DOGEUSD",  # Dogecoin
    "SHIBUSD",  # Shiba Inu
]


def backfill_historical_data(days_back=90, interval="5m"):
    """
    Fetch historical data for all tracked symbols.

    Args:
        days_back: How many days of history to fetch
        interval: Candle interval ("5m", "1h", "1d")
    """
    logging.info("=" * 70)
    logging.info(f"BACKFILLING HISTORICAL DATA")
    logging.info(f"Days back: {days_back} | Interval: {interval}")
    logging.info("=" * 70)

    total_candles = 0
    successful = 0
    failed = 0

    with get_db() as db:
        fetcher = HistoricalDataFetcher(db)

        for i, symbol in enumerate(SYMBOLS, 1):
            try:
                logging.info(f"\n[{i}/{len(SYMBOLS)}] Fetching {symbol}...")

                candles_count = fetcher.fetch_and_cache(
                    symbol=symbol,
                    interval=interval,
                    days_back=days_back
                )

                if candles_count > 0:
                    logging.info(f"✅ {symbol}: Fetched {candles_count} candles")
                    total_candles += candles_count
                    successful += 1
                else:
                    logging.warning(f"⚠️  {symbol}: No data fetched")
                    failed += 1

            except Exception as e:
                logging.error(f"❌ {symbol}: Error - {e}")
                failed += 1

    # Summary
    logging.info("\n" + "=" * 70)
    logging.info("BACKFILL COMPLETE")
    logging.info("=" * 70)
    logging.info(f"Successful: {successful}/{len(SYMBOLS)} symbols")
    logging.info(f"Failed: {failed}/{len(SYMBOLS)} symbols")
    logging.info(f"Total candles fetched: {total_candles:,}")
    logging.info(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info("=" * 70)


def verify_data():
    """Verify what data we have in the database."""
    logging.info("\n" + "=" * 70)
    logging.info("DATABASE VERIFICATION")
    logging.info("=" * 70)

    with get_db() as db:
        repo = HistoricalOHLCVRepository(db)

        for symbol in SYMBOLS:
            try:
                count = repo.count_candles(symbol, "5m")
                if count > 0:
                    latest = repo.get_latest_timestamp(symbol, "5m")
                    logging.info(f"{symbol:10} {count:6,} candles | Latest: {latest}")
                else:
                    logging.info(f"{symbol:10} No data")
            except Exception as e:
                logging.error(f"{symbol:10} Error: {e}")

    logging.info("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill historical market data")
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of days of history to fetch (default: 90)"
    )
    parser.add_argument(
        "--interval",
        type=str,
        default="5m",
        choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        help="Candle interval (default: 5m)"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing data, don't fetch new data"
    )

    args = parser.parse_args()

    if args.verify_only:
        verify_data()
    else:
        backfill_historical_data(days_back=args.days, interval=args.interval)
        verify_data()
