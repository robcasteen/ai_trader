#!/usr/bin/env python3
"""
Run backtests on historical data to evaluate strategy performance.

Usage:
    python scripts/run_backtest.py --days 30 --symbols XXBTZUSD XETHZUSD
    python scripts/run_backtest.py --days 7 --interval 15 --capital 5000
    python scripts/run_backtest.py --quick  # Quick 7-day test on BTC/ETH
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import argparse
import logging
import json
from datetime import datetime

from app.backtesting.backtest_engine import BacktestEngine
from app.backtesting.performance_metrics import PerformanceAnalyzer
from app.logic.symbol_scanner import DEFAULT_PRIORITY_SYMBOLS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


def main():
    parser = argparse.ArgumentParser(description='Run strategy backtests on historical data')

    parser.add_argument(
        '--symbols',
        nargs='+',
        default=None,
        help='Symbols to test (default: top priority symbols)'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to backtest (default: 30)'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        choices=[1, 5, 15, 30, 60, 240, 1440],
        help='Candle interval in minutes (default: 60)'
    )

    parser.add_argument(
        '--capital',
        type=float,
        default=10000.0,
        help='Initial capital in USD (default: 10000)'
    )

    parser.add_argument(
        '--position-size',
        type=float,
        default=0.03,
        help='Position size as percentage of portfolio (default: 0.03 = 3%%)'
    )

    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick test: 7 days on BTC and ETH'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Save detailed results to JSON file'
    )

    args = parser.parse_args()

    # Quick test mode
    if args.quick:
        symbols = ["XXBTZUSD", "XETHZUSD"]
        days = 7
        print("\n🚀 Running QUICK backtest (7 days, BTC + ETH)\n")
    else:
        symbols = args.symbols or DEFAULT_PRIORITY_SYMBOLS[:5]  # Top 5 symbols
        days = args.days

    print("=" * 70)
    print("BACKTEST CONFIGURATION")
    print("=" * 70)
    print(f"Symbols:        {', '.join(symbols)}")
    print(f"Period:         {days} days")
    print(f"Interval:       {args.interval} minutes")
    print(f"Capital:        ${args.capital:,.2f}")
    print(f"Position Size:  {args.position_size * 100}%")
    print("=" * 70)
    print()

    # Initialize backtest engine
    engine = BacktestEngine()

    # Run backtest
    print("⏳ Running backtest... (this may take a few minutes)\n")

    try:
        results = engine.run_backtest(
            symbols=symbols,
            days_back=days,
            interval_minutes=args.interval,
            initial_capital=args.capital,
            position_size_pct=args.position_size
        )

        if "error" in results:
            print(f"❌ Error: {results['error']}")
            return 1

        # Calculate metrics
        metrics = PerformanceAnalyzer.calculate_metrics(results)

        # Generate and print report
        report = PerformanceAnalyzer.generate_report(results, metrics)
        print(report)

        # Show trade summary
        if results.get("trades"):
            print("\nRECENT TRADES (last 10)")
            print("-" * 70)
            recent_trades = results["trades"][-10:]
            for trade in recent_trades:
                timestamp = trade["timestamp"].strftime("%Y-%m-%d %H:%M")
                action = trade["action"]
                symbol = trade["symbol"]
                price = trade["price"]
                amount = trade["amount"]
                print(f"{timestamp} | {action:4} | {symbol:10} | ${price:>10,.2f} | {amount:>8.4f}")
            print()

        # Save to file if requested
        if args.output:
            output_data = {
                "config": {
                    "symbols": symbols,
                    "days": days,
                    "interval_minutes": args.interval,
                    "initial_capital": args.capital,
                    "position_size_pct": args.position_size,
                },
                "metrics": metrics,
                "trades": [
                    {**t, "timestamp": t["timestamp"].isoformat()}
                    for t in results["trades"]
                ],
                "portfolio_values": [
                    {**pv, "timestamp": pv["timestamp"].isoformat()}
                    for pv in results["portfolio_values"]
                ],
            }

            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2)

            print(f"✅ Detailed results saved to: {args.output}")
            print()

        # Summary verdict
        print("VERDICT")
        print("-" * 70)

        if metrics['total_return_pct'] > 5:
            verdict = "✅ STRONG PERFORMANCE"
        elif metrics['total_return_pct'] > 0:
            verdict = "⚠️  MODEST GAINS"
        elif metrics['total_return_pct'] > -5:
            verdict = "⚠️  SMALL LOSS"
        else:
            verdict = "❌ POOR PERFORMANCE"

        print(f"{verdict}")
        print(f"Return: {metrics['total_return_pct']:+.2f}% over {days} days")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        print(f"Win Rate: {metrics['win_rate']:.2f}%")
        print("=" * 70)

        return 0

    except Exception as e:
        logging.error(f"Backtest failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
