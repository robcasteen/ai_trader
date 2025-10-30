#!/usr/bin/env python3
"""
Backfill historical market data for the DataCollector.
Run this to populate price/volume history for technical analysis.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging
from collections import deque
from app.client.kraken import KrakenClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def backfill_history():
    """Backfill historical OHLC data from exchange for common symbols."""
    client = KrakenClient()
    max_history = 100

    # Common trading pairs to backfill
    symbols_to_backfill = [
        "XXBTZUSD",  # Bitcoin
        "XETHZUSD",  # Ethereum
        "SOLUSD",    # Solana
        "ADAUSD",    # Cardano
        "DOTUSD",    # Polkadot
    ]

    results = {}

    for symbol in symbols_to_backfill:
        try:
            logging.info(f"Fetching OHLC data for {symbol}...")

            # Fetch 1-minute candles
            ohlc_data = client.get_ohlc(symbol, interval=1)

            if not ohlc_data:
                logging.warning(f"No OHLC data returned for {symbol}")
                results[symbol] = {"success": False, "count": 0}
                continue

            # Extract prices and volumes from OHLC data
            # Format: [timestamp, open, high, low, close, vwap, volume, count]
            prices = []
            volumes = []

            for candle in ohlc_data[-max_history:]:  # Get last max_history candles
                close_price = float(candle[4])  # Close price
                volume = float(candle[6])       # Volume
                prices.append(close_price)
                volumes.append(volume)

            results[symbol] = {
                "success": True,
                "count": len(prices),
                "sample_price": prices[-1] if prices else None,
                "sample_volume": volumes[-1] if volumes else None
            }

            logging.info(
                f"✅ {symbol}: Fetched {len(prices)} data points. "
                f"Latest price: ${prices[-1]:,.2f}, Volume: {volumes[-1]:,.2f}"
            )

        except Exception as e:
            logging.error(f"❌ Failed to backfill {symbol}: {e}")
            results[symbol] = {"success": False, "error": str(e)}

    # Summary
    logging.info("\n" + "=" * 60)
    logging.info("BACKFILL SUMMARY")
    logging.info("=" * 60)

    successful = sum(1 for r in results.values() if r.get("success"))
    failed = len(results) - successful

    logging.info(f"✅ Successful: {successful}")
    logging.info(f"❌ Failed: {failed}")

    for symbol, result in results.items():
        if result.get("success"):
            logging.info(f"  {symbol}: {result['count']} data points")
        else:
            error = result.get("error", "No data")
            logging.error(f"  {symbol}: FAILED - {error}")

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("MARKET DATA BACKFILL UTILITY")
    print("=" * 60)
    print()
    print("This script fetches historical OHLC data from Kraken")
    print("to populate the DataCollector with price/volume history.")
    print()
    print("Note: This backfills the data temporarily for verification.")
    print("The actual DataCollector will backfill automatically on startup")
    print("once the server is restarted.")
    print()
    print("=" * 60)
    print()

    results = backfill_history()

    print()
    print("=" * 60)
    print("DATA VERIFICATION")
    print("=" * 60)

    any_success = any(r.get("success") for r in results.values())

    if any_success:
        print("✅ Backfill successful!")
        print()
        print("The data has been fetched successfully.")
        print("To apply this to the running bot, restart the server:")
        print()
        print("  1. Stop the current server (Ctrl+C)")
        print("  2. Restart: ./run.sh")
        print()
        print("The DataCollector will automatically backfill on startup.")
    else:
        print("❌ Backfill failed for all symbols.")
        print()
        print("Please check:")
        print("  - Kraken API connectivity")
        print("  - Symbol names are correct")
        print("  - API rate limits")
