"""
Tests for signal performance analysis module.
"""
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from app.signal_performance import (
    correlate_signals_to_trades,
    analyze_strategy_performance,
    get_signal_performance_analysis
)


@pytest.fixture
def sample_signals():
    """Sample signals for testing."""
    now = datetime.now()
    return [
        {
            "timestamp": now.isoformat(),
            "symbol": "BTCUSD",
            "final_signal": "BUY",
            "final_confidence": 0.85,
            "strategies": {
                "sentiment": {
                    "signal": "BUY",
                    "confidence": 0.9,
                    "reason": "Positive news"
                },
                "technical": {
                    "signal": "BUY",
                    "confidence": 0.8,
                    "reason": "RSI oversold"
                }
            }
        },
        {
            "timestamp": (now - timedelta(minutes=5)).isoformat(),
            "symbol": "ETHUSD",
            "final_signal": "SELL",
            "final_confidence": 0.75,
            "strategies": {
                "technical": {
                    "signal": "SELL",
                    "confidence": 0.75,
                    "reason": "RSI overbought"
                }
            }
        },
        {
            "timestamp": (now - timedelta(minutes=10)).isoformat(),
            "symbol": "SOLUSD",
            "final_signal": "HOLD",
            "final_confidence": 0.5,
            "strategies": {}
        }
    ]


@pytest.fixture
def sample_trades():
    """Sample trades for testing."""
    now = datetime.now()
    return [
        {
            "timestamp": (now + timedelta(minutes=2)).isoformat(),
            "action": "buy",
            "symbol": "BTCUSD",
            "price": 50000.0,
            "amount": 0.001,
            "net_value": 50.0
        },
        {
            "timestamp": (now - timedelta(minutes=3)).isoformat(),
            "action": "sell",
            "symbol": "ETHUSD",
            "price": 3000.0,
            "amount": 0.01,
            "net_value": 30.0
        },
        {
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "action": "buy",
            "symbol": "XRPUSD",
            "price": 0.5,
            "amount": 100,
            "net_value": 50.0
        }
    ]


def test_correlate_signals_to_trades_match(sample_signals, sample_trades):
    """Test that signals are correctly correlated to trades within time window."""
    correlations = correlate_signals_to_trades(sample_signals, sample_trades, window_minutes=10)

    # Should have 2 correlations (HOLD signals excluded)
    assert len(correlations) == 2

    # First signal (BTCUSD BUY) should match first trade
    btc_corr = correlations[0]
    assert btc_corr['signal']['symbol'] == 'BTCUSD'
    assert btc_corr['signal']['action'] == 'BUY'
    assert btc_corr['executed'] is True
    assert btc_corr['trade'] is not None
    assert btc_corr['trade']['symbol'] == 'BTCUSD'

    # Second signal (ETHUSD SELL) should match second trade
    eth_corr = correlations[1]
    assert eth_corr['signal']['symbol'] == 'ETHUSD'
    assert eth_corr['signal']['action'] == 'SELL'
    assert eth_corr['executed'] is True
    assert eth_corr['trade'] is not None


def test_correlate_signals_to_trades_no_match(sample_signals):
    """Test that signals with no matching trades are marked as not executed."""
    # Trades with different symbols
    unmatched_trades = [
        {
            "timestamp": datetime.now().isoformat(),
            "action": "buy",
            "symbol": "XRPUSD",
            "price": 0.5,
            "amount": 100,
            "net_value": 50.0
        }
    ]

    correlations = correlate_signals_to_trades(sample_signals, unmatched_trades, window_minutes=10)

    # Should have 2 correlations (HOLD excluded) but none executed
    assert len(correlations) == 2
    assert all(not corr['executed'] for corr in correlations)
    assert all(corr['trade'] is None for corr in correlations)


def test_correlate_signals_excludes_hold(sample_signals, sample_trades):
    """Test that HOLD signals are excluded from correlations."""
    correlations = correlate_signals_to_trades(sample_signals, sample_trades)

    # Should not include the HOLD signal for SOLUSD
    symbols = [c['signal']['symbol'] for c in correlations]
    assert 'SOLUSD' not in symbols


def test_correlate_signals_time_window(sample_signals):
    """Test that time window is respected."""
    now = datetime.now()

    # Trade outside time window (15 minutes later)
    late_trade = [
        {
            "timestamp": (now + timedelta(minutes=15)).isoformat(),
            "action": "buy",
            "symbol": "BTCUSD",
            "price": 50000.0,
            "amount": 0.001,
            "net_value": 50.0
        }
    ]

    correlations = correlate_signals_to_trades(sample_signals, late_trade, window_minutes=10)

    # BTCUSD signal should not match the late trade
    btc_corr = [c for c in correlations if c['signal']['symbol'] == 'BTCUSD'][0]
    assert btc_corr['executed'] is False


def test_analyze_strategy_performance(sample_signals, sample_trades):
    """Test strategy performance analysis."""
    correlations = correlate_signals_to_trades(sample_signals, sample_trades)
    strategy_stats = analyze_strategy_performance(correlations, sample_trades)

    # Should have stats for sentiment and technical strategies
    assert 'sentiment' in strategy_stats
    assert 'technical' in strategy_stats

    # Sentiment was in 1 signal
    assert strategy_stats['sentiment']['signals_generated'] == 1
    assert strategy_stats['sentiment']['signals_executed'] == 1
    assert strategy_stats['sentiment']['execution_rate'] == 1.0

    # Technical was in 2 signals
    assert strategy_stats['technical']['signals_generated'] == 2
    assert strategy_stats['technical']['signals_executed'] == 2
    assert strategy_stats['technical']['execution_rate'] == 1.0


def test_analyze_strategy_performance_partial_execution(sample_signals):
    """Test strategy stats with only partial signal execution."""
    # Only one trade matching first signal
    limited_trades = [
        {
            "timestamp": datetime.now().isoformat(),
            "action": "buy",
            "symbol": "BTCUSD",
            "price": 50000.0,
            "amount": 0.001,
            "net_value": 50.0
        }
    ]

    correlations = correlate_signals_to_trades(sample_signals, limited_trades)
    strategy_stats = analyze_strategy_performance(correlations, limited_trades)

    # Technical was in 2 signals but only 1 executed
    assert strategy_stats['technical']['signals_generated'] == 2
    assert strategy_stats['technical']['signals_executed'] == 1
    assert strategy_stats['technical']['execution_rate'] == 0.5


def test_get_signal_performance_analysis():
    """Test full analysis function with real data files."""
    try:
        result = get_signal_performance_analysis()

        # Check structure
        assert 'summary' in result
        assert 'correlations' in result
        assert 'strategy_performance' in result

        # Check summary fields
        summary = result['summary']
        assert 'total_signals' in summary
        assert 'executed_signals' in summary
        assert 'execution_rate' in summary
        assert 'total_trades' in summary
        assert 'analysis_period_hours' in summary

        # Execution rate should be between 0 and 1
        assert 0 <= summary['execution_rate'] <= 1

        # Correlations should be a list
        assert isinstance(result['correlations'], list)

        # Strategy performance should be a dict
        assert isinstance(result['strategy_performance'], dict)

    except FileNotFoundError:
        pytest.skip("Data files not found - skipping integration test")


def test_timezone_handling():
    """Test that timezone-aware and timezone-naive datetimes are handled correctly."""
    now = datetime.now()

    # Signal with timezone
    signal_with_tz = {
        "timestamp": datetime.now().isoformat() + "+00:00",
        "symbol": "BTCUSD",
        "final_signal": "BUY",
        "final_confidence": 0.8,
        "strategies": {}
    }

    # Trade without timezone
    trade_no_tz = {
        "timestamp": datetime.now().isoformat(),
        "action": "buy",
        "symbol": "BTCUSD",
        "price": 50000.0,
        "amount": 0.001,
        "net_value": 50.0
    }

    # Should not raise timezone comparison error
    correlations = correlate_signals_to_trades([signal_with_tz], [trade_no_tz])
    assert len(correlations) == 1


def test_edge_case_empty_inputs():
    """Test with empty signals and trades."""
    correlations = correlate_signals_to_trades([], [])
    assert correlations == []

    strategy_stats = analyze_strategy_performance([], [])
    assert strategy_stats == {}


def test_edge_case_missing_fields():
    """Test handling of missing optional fields."""
    signal_minimal = {
        "timestamp": datetime.now().isoformat(),
        "symbol": "BTCUSD",
        "final_signal": "BUY",
        # Missing final_confidence and strategies
    }

    trade_minimal = {
        "timestamp": datetime.now().isoformat(),
        "action": "buy",
        "symbol": "BTCUSD",
        "price": 50000.0,
        # Missing amount, net_value
    }

    correlations = correlate_signals_to_trades([signal_minimal], [trade_minimal])
    assert len(correlations) == 1
    assert correlations[0]['signal']['confidence'] == 0  # Default value
