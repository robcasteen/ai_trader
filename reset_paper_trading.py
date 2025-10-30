#!/usr/bin/env python3
"""
Reset paper trading state to starting conditions.

This script:
1. Clears all trades from database (keeps test_mode trades separate)
2. Clears all holdings
3. Resets starting balance
4. Archives old data for reference
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from app.database.connection import get_db
from app.database.models import Trade, Holding

def main():
    print("=" * 60)
    print("PAPER TRADING RESET SCRIPT")
    print("=" * 60)

    # Paths
    logs_dir = Path("src/app/logs")
    holdings_file = logs_dir / "holdings.json"
    trades_file = logs_dir / "trades.json"
    backup_dir = Path("backups") / f"reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Create backup directory
    backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Created backup directory: {backup_dir}")

    # Backup existing files
    if holdings_file.exists():
        shutil.copy2(holdings_file, backup_dir / "holdings.json")
        print(f"✅ Backed up holdings.json")

    if trades_file.exists():
        shutil.copy2(trades_file, backup_dir / "trades.json")
        print(f"✅ Backed up trades.json")

    # Count trades in database before clearing
    with get_db() as db:
        trade_count = db.query(Trade).filter(Trade.test_mode == False).count()
        test_trade_count = db.query(Trade).filter(Trade.test_mode == True).count()
        holding_count = db.query(Holding).count()

        print(f"\n📊 Current State:")
        print(f"   - Production trades: {trade_count}")
        print(f"   - Test trades: {test_trade_count}")
        print(f"   - Holdings: {holding_count}")

    # Ask for confirmation
    print(f"\n⚠️  This will DELETE {trade_count} production trades and {holding_count} holdings!")
    print(f"   Test trades ({test_trade_count}) will be preserved.")
    response = input("\nContinue? (yes/no): ").strip().lower()

    if response != "yes":
        print("❌ Aborted.")
        return

    # Clear database (keep test_mode trades)
    print("\n🗑️  Clearing database...")
    with get_db() as db:
        # Delete production trades only
        deleted_trades = db.query(Trade).filter(Trade.test_mode == False).delete()

        # Delete all holdings
        deleted_holdings = db.query(Holding).delete()

        db.commit()

        print(f"   ✅ Deleted {deleted_trades} production trades")
        print(f"   ✅ Deleted {deleted_holdings} holdings")
        print(f"   ℹ️  Preserved {test_trade_count} test trades")

    # Reset holdings file
    print("\n📝 Resetting holdings.json...")
    with open(holdings_file, "w") as f:
        json.dump({}, f, indent=2)
    print("   ✅ Holdings cleared")

    # Reset trades file
    print("\n📝 Resetting trades.json...")
    with open(trades_file, "w") as f:
        json.dump([], f, indent=2)
    print("   ✅ Trades file cleared")

    print("\n" + "=" * 60)
    print("✅ PAPER TRADING RESET COMPLETE")
    print("=" * 60)
    print(f"\n📁 Backup saved to: {backup_dir}")
    print(f"\n🎯 Ready to start fresh with $200 capital")
    print(f"   - All production trades cleared from database")
    print(f"   - All holdings cleared")
    print(f"   - Test trades preserved for testing")

if __name__ == "__main__":
    main()
