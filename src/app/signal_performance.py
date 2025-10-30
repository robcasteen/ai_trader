"""
Signal Performance Analysis
Correlates signals with trades and calculates strategy performance metrics.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List
import logging

LOGS_DIR = Path(__file__).parent / "logs"


def load_signals_and_trades():
    """Load signals and trades from database."""
    from app.database.connection import get_db
    from app.database.repositories import SignalRepository, TradeRepository

    signals = []
    trades = []

    try:
        with get_db() as db:
            signal_repo = SignalRepository(db)
            trade_repo = TradeRepository(db)

            # Get all non-test signals from last 7 days
            signal_models = signal_repo.get_recent(hours=24*7, test_mode=False, limit=1000)

            # Convert to dict format for compatibility
            for s in signal_models:
                signals.append({
                    'id': s.id,  # Include signal ID for proper correlation
                    'timestamp': s.timestamp.isoformat() + 'Z' if s.timestamp else None,
                    'symbol': s.symbol,
                    'final_signal': s.final_signal,
                    'final_confidence': float(s.final_confidence) if s.final_confidence else 0,
                    'strategies': s.strategies or {}
                })

            # Get all non-test trades
            trade_models = trade_repo.get_all(test_mode=False)

            # Convert to dict format
            for t in trade_models:
                trades.append({
                    'timestamp': t.timestamp.isoformat() + 'Z' if t.timestamp else None,
                    'symbol': t.symbol,
                    'action': t.action,
                    'price': float(t.price) if t.price else 0,
                    'amount': float(t.amount) if t.amount else 0,
                    'signal_id': t.signal_id
                })

    except Exception as e:
        logging.error(f"Error loading signals and trades from database: {e}")

    return signals, trades


def correlate_signals_to_trades(signals: List[Dict], trades: List[Dict], window_minutes: int = 10) -> List[Dict]:
    """Correlate signals to trades using signal_id, with fallback to time-window matching."""
    correlations = []

    # Create mapping of signal_id -> trade for fast lookup
    trades_by_signal_id = {}
    for trade in trades:
        if trade.get('signal_id'):
            trades_by_signal_id[trade['signal_id']] = trade

    for signal in signals:
        sig_time = datetime.fromisoformat(signal['timestamp'].replace('Z', '+00:00'))
        # Make timezone-naive for comparison
        if sig_time.tzinfo is not None:
            sig_time = sig_time.replace(tzinfo=None)

        sig_id = signal.get('id')
        sig_symbol = signal['symbol']
        sig_action = signal['final_signal']
        sig_conf = signal.get('final_confidence', 0)

        # Skip HOLD signals
        if sig_action == 'HOLD':
            continue

        # PRIORITY 1: Match by signal_id (most accurate)
        matched_trade = None
        if sig_id and sig_id in trades_by_signal_id:
            matched_trade = trades_by_signal_id[sig_id]
        else:
            # FALLBACK: Match by time window (less accurate, only if signal happened BEFORE trade)
            for trade in trades:
                try:
                    trade_time = datetime.fromisoformat(trade['timestamp'])
                except:
                    trade_time = datetime.fromisoformat(trade['timestamp'].replace('Z', '+00:00'))

                # Make timezone-naive for comparison
                if trade_time.tzinfo is not None:
                    trade_time = trade_time.replace(tzinfo=None)

                trade_symbol = trade['symbol']
                trade_action = trade['action'].upper()

                # Check if trade matches signal
                # IMPORTANT: Signal must come BEFORE or at same time as trade (not after!)
                time_diff_seconds = (trade_time - sig_time).total_seconds()
                time_diff_minutes = time_diff_seconds / 60

                if (trade_symbol == sig_symbol and
                    trade_action == sig_action and
                    0 <= time_diff_seconds <= window_minutes * 60):  # Signal must be before trade
                    matched_trade = trade
                    break
        
        correlations.append({
            'signal': {
                'timestamp': signal['timestamp'],
                'symbol': sig_symbol,
                'action': sig_action,
                'confidence': sig_conf
            },
            'trade': matched_trade,
            'executed': matched_trade is not None,
            'strategies': signal.get('strategies', {})
        })
    
    return correlations


def analyze_strategy_performance(correlations: List[Dict], trades: List[Dict]) -> Dict:
    """Analyze performance by strategy."""
    strategy_stats = defaultdict(lambda: {
        'signals_generated': 0,
        'signals_executed': 0,
        'total_pnl': 0.0,
        'wins': 0,
        'losses': 0
    })
    
    # Track which strategies contributed to each signal
    for corr in correlations:
        strategies = corr.get('strategies', {})
        
        for strat_name in strategies:
            strategy_stats[strat_name]['signals_generated'] += 1
            
            if corr['executed']:
                strategy_stats[strat_name]['signals_executed'] += 1
    
    # Calculate win rates
    for strat_name, stats in strategy_stats.items():
        total_completed = stats['wins'] + stats['losses']
        stats['win_rate'] = stats['wins'] / total_completed if total_completed > 0 else 0
        stats['avg_pnl'] = stats['total_pnl'] / total_completed if total_completed > 0 else 0
        stats['execution_rate'] = stats['signals_executed'] / stats['signals_generated'] if stats['signals_generated'] > 0 else 0
    
    return dict(strategy_stats)


def get_signal_performance_analysis() -> Dict:
    """Main analysis function."""
    signals, trades = load_signals_and_trades()

    # Only analyze recent signals (last 24 hours) - use timezone-naive comparison
    cutoff = datetime.now() - timedelta(hours=24)
    recent_signals = [
        s for s in signals
        if datetime.fromisoformat(s['timestamp'].replace('Z', '+00:00')).replace(tzinfo=None) > cutoff
    ]
    
    # Filter out test trades
    real_trades = [
        t for t in trades
        if float(t.get('amount', 0)) > 0 and float(t.get('amount', 0)) < 100
        and float(t['price']) > 0 and float(t['price']) < 200000
    ]
    
    correlations = correlate_signals_to_trades(recent_signals, real_trades)
    strategy_performance = analyze_strategy_performance(correlations, real_trades)
    
    # Calculate summary stats
    total_signals = len([c for c in correlations if c['signal']['action'] != 'HOLD'])
    executed_signals = sum(1 for c in correlations if c['executed'])
    execution_rate = executed_signals / total_signals if total_signals > 0 else 0
    
    return {
        'summary': {
            'total_signals': total_signals,
            'executed_signals': executed_signals,
            'execution_rate': execution_rate,
            'total_trades': len(real_trades),
            'analysis_period_hours': 24
        },
        'correlations': correlations[-30:],  # Last 30
        'strategy_performance': strategy_performance
    }
