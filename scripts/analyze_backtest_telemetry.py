"""
Analyze Backtest Telemetry

This script runs a mini-backtest with telemetry to understand why strategies
aren't generating tradeable signals.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import datetime, timedelta
from app.database.connection import get_db
from app.database.repositories import HistoricalOHLCVRepository
from app.strategies.strategy_manager import StrategyManager


def analyze_backtest_signals(symbol="BTCUSD", days=3, sample_size=10):
    """
    Run strategy manager on historical data and analyze telemetry.

    Args:
        symbol: Symbol to analyze
        days: How many days of data to analyze
        sample_size: How many data points to analyze
    """
    print("="*80)
    print("BACKTEST TELEMETRY ANALYSIS")
    print("="*80)
    print()

    # Load historical data
    with get_db() as db:
        repo = HistoricalOHLCVRepository(db)

        # Get date range from database
        end = datetime(2025, 10, 30, 23, 59, 59)
        start = end - timedelta(days=days)

        db_candles = repo.get_range(symbol, start, end, '5m')

        # Convert to dicts inside session to avoid detachment
        candles = []
        for c in db_candles:
            candles.append({
                "timestamp": c.timestamp,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume)
            })

        print(f"✓ Loaded {len(candles)} candles for {symbol}")
        print(f"  Date range: {candles[0]['timestamp']} to {candles[-1]['timestamp']}")
        print(f"  Price range: ${min(c['close'] for c in candles):,.2f} - ${max(c['close'] for c in candles):,.2f}")
        print()

    if len(candles) < 100:
        print("❌ Not enough candles for analysis (need 100+)")
        return

    # Initialize strategy manager
    manager = StrategyManager(config={
        "min_confidence": 0.5,
        "aggregation_method": "weighted_vote"
    })

    print(f"✓ Strategy Manager initialized")
    print(f"  Min confidence: {manager.min_confidence}")
    print(f"  Aggregation: {manager.aggregation_method}")
    print(f"  Strategies: {len(manager.strategies)}")
    for strategy in manager.strategies:
        print(f"    - {strategy.name} (weight={strategy.weight}, enabled={strategy.enabled})")
    print()

    # Analyze signals at different points
    print("="*80)
    print("SIGNAL ANALYSIS")
    print("="*80)
    print()

    # Sample evenly throughout the dataset
    step = max(1, len(candles) // sample_size)
    signals_analyzed = 0
    signals_would_execute = 0
    signals_near_miss = 0

    signal_distribution = {"BUY": 0, "SELL": 0, "HOLD": 0}
    confidence_levels = []

    for i in range(100, len(candles), step):
        if signals_analyzed >= sample_size:
            break

        # Build context
        price_history = [c['close'] for c in candles[:i]]
        volume_history = [c['volume'] for c in candles[:i]]

        context = {
            "headlines": [],  # No news in backtest
            "price": candles[i]['close'],
            "volume": candles[i]['volume'],
            "price_history": price_history,
            "volume_history": volume_history
        }

        # Get signal with telemetry
        result = manager.get_signal_with_telemetry(symbol, context)

        signals_analyzed += 1
        signal = result["final_signal"]
        confidence = result["final_confidence"]
        telemetry = result["telemetry"]

        signal_distribution[signal] += 1
        confidence_levels.append(confidence)

        if telemetry["execution"]["would_execute"]:
            signals_would_execute += 1

        if telemetry["execution"].get("near_miss", False):
            signals_near_miss += 1

        # Print first few signals in detail
        if signals_analyzed <= 3:
            print(f"Signal #{signals_analyzed} @ {candles[i]['timestamp']}")
            print(f"  Price: ${context['price']:,.2f}")
            print(f"  Final: {signal} (confidence: {confidence:.3f})")
            print(f"  Would execute: {telemetry['execution']['would_execute']}")
            print()

            print("  Strategy Votes:")
            for vote in telemetry["strategy_votes"]:
                print(f"    {vote['strategy_name']:12s}: {vote['signal']:4s} ({vote['confidence']:.3f}) - {vote['reason'][:50]}")
            print()

            print(f"  Aggregation:")
            print(f"    BUY score:  {telemetry['aggregation']['buy_score']:.3f}")
            print(f"    SELL score: {telemetry['aggregation']['sell_score']:.3f}")
            print(f"    HOLD score: {telemetry['aggregation']['hold_score']:.3f}")
            print()

            print(f"  Execution Decision:")
            print(f"    {telemetry['execution']['reason']}")
            if not telemetry['execution']['would_execute']:
                print(f"    Gap: {telemetry['execution']['confidence_gap']:.3f}")
                print(f"    Near miss: {telemetry['execution']['near_miss']}")
            print()
            print("-"*80)
            print()

    # Print summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print()

    print(f"Signals analyzed: {signals_analyzed}")
    print()

    print(f"Signal Distribution:")
    for sig, count in signal_distribution.items():
        pct = (count / signals_analyzed * 100) if signals_analyzed > 0 else 0
        print(f"  {sig:4s}: {count:3d} ({pct:5.1f}%)")
    print()

    print(f"Execution Analysis:")
    print(f"  Would execute: {signals_would_execute}/{signals_analyzed} ({signals_would_execute/signals_analyzed*100:.1f}%)")
    print(f"  Near misses:   {signals_near_miss}/{signals_analyzed} ({signals_near_miss/signals_analyzed*100:.1f}%)")
    print()

    avg_confidence = sum(confidence_levels) / len(confidence_levels) if confidence_levels else 0
    max_confidence = max(confidence_levels) if confidence_levels else 0
    min_confidence = min(confidence_levels) if confidence_levels else 0

    print(f"Confidence Statistics:")
    print(f"  Average: {avg_confidence:.3f}")
    print(f"  Max:     {max_confidence:.3f}")
    print(f"  Min:     {min_confidence:.3f}")
    print(f"  Threshold: {manager.min_confidence:.3f}")
    print()

    # Diagnosis
    print("="*80)
    print("DIAGNOSIS")
    print("="*80)
    print()

    if signals_would_execute == 0:
        print("❌ PROBLEM: Zero signals would execute")
        print()
        if avg_confidence < manager.min_confidence - 0.2:
            print("   Root cause: Confidence levels are VERY low")
            print(f"   Average confidence ({avg_confidence:.3f}) is far below threshold ({manager.min_confidence:.3f})")
            print()
            print("   Possible fixes:")
            print("   1. Lower min_confidence threshold (e.g., 0.3)")
            print("   2. Tune strategy parameters to generate stronger signals")
            print("   3. Check if strategies are working correctly")
        elif signals_near_miss > 0:
            print("   Root cause: Signals are just below threshold (near misses)")
            print(f"   {signals_near_miss} signals were within 0.1 of threshold")
            print()
            print("   Possible fixes:")
            print(f"   1. Lower min_confidence from {manager.min_confidence:.3f} to ~{manager.min_confidence - 0.1:.3f}")
            print("   2. Adjust strategy weights to boost confidence")
        else:
            print("   Root cause: Confidence generally too low")
            print()
            print("   Possible fixes:")
            print("   1. Check strategy logic (technical indicators may be too strict)")
            print("   2. Verify data quality (price/volume history)")
            print("   3. Add more strategies or increase weights")
    elif signals_would_execute < signals_analyzed * 0.1:
        print("⚠️  WARNING: Very few signals would execute (<10%)")
        print()
        print("   This may be intentional (conservative strategy), but verify:")
        print("   - Strategy thresholds are appropriate")
        print("   - Market conditions in backtest period were tradeable")
    else:
        print("✓ System appears functional")
        print(f"  {signals_would_execute/signals_analyzed*100:.1f}% of signals would execute")

    print()


if __name__ == "__main__":
    analyze_backtest_signals(symbol="BTCUSD", days=3, sample_size=10)
