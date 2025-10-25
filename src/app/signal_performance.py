"""
Signal Performance Analysis
Correlates signals with trades and calculates strategy performance metrics.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List

LOGS_DIR = Path(__file__).parent / "logs"


def load_signals_and_trades():
    """Load signals from jsonl and trades from json."""
    signals = []
    signals_file = Path(__file__).parent.parent.parent / "data" / "strategy_signals.jsonl"
    
    if signals_file.exists():
        with open(signals_file, 'r') as f:
            for line in f:
                try:
                    signals.append(json.loads(line))
                except:
                    pass
    
    trades = []
    trades_file = LOGS_DIR / "trades.json"
    if trades_file.exists():
        with open(trades_file, 'r') as f:
            trades = json.load(f)
    
    return signals, trades


def correlate_signals_to_trades(signals: List[Dict], trades: List[Dict], window_minutes: int = 10) -> List[Dict]:
    """Correlate signals to trades that happened within a time window."""
    correlations = []

    for signal in signals:
        sig_time = datetime.fromisoformat(signal['timestamp'].replace('Z', '+00:00'))
        # Make timezone-naive for comparison
        if sig_time.tzinfo is not None:
            sig_time = sig_time.replace(tzinfo=None)

        sig_symbol = signal['symbol']
        sig_action = signal['final_signal']
        sig_conf = signal.get('final_confidence', 0)

        # Skip HOLD signals
        if sig_action == 'HOLD':
            continue

        # Find matching trade within time window
        matched_trade = None
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
            time_diff = abs((trade_time - sig_time).total_seconds() / 60)
            if (trade_symbol == sig_symbol and
                trade_action == sig_action and
                time_diff <= window_minutes):
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
