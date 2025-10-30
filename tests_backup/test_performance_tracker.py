"""
Comprehensive test suite for PerformanceTracker.

Goals:
- Validate that trades.json is the single source of truth.
- Ensure calculations (PnL, trades, win_rate) are consistent with real-time replay.
- Confirm error handling for invalid trade sequences.
- Guarantee output structure remains stable for frontend integration.
"""

import json
import pytest
from pathlib import Path
from app.metrics.performance_tracker import (
    performance_tracker,
    InvalidTradeSequenceError,
)


# -----------------------------------------------------------------------------------
# 1. Structure & Defaults
# -----------------------------------------------------------------------------------

def test_empty_trades_returns_defaults():
    summary = performance_tracker.get_performance_summary([])
    assert summary["symbols"] == {}
    assert summary["total_pnl"] == 0.0
    assert summary["total_trades"] == 0
    assert summary["win_rate"] is None


def test_corrupted_trades_file_returns_defaults(tmp_path):
    bad_file = tmp_path / "trades.json"
    bad_file.write_text(json.dumps({"oops": "not a list"}))

    tracker = performance_tracker
    tracker.trades_file = bad_file
    summary = tracker.get_performance_summary()
    assert summary["symbols"] == {}
    assert summary["total_pnl"] == 0.0


def test_zero_amount_trade_ignored():
    trades = [{"timestamp": "t1", "action": "buy", "symbol": "BTC/USD", "price": 100, "amount": 0}]
    summary = performance_tracker.get_performance_summary(trades)
    assert summary["symbols"] == {}
    assert summary["total_trades"] == 0


def test_invalid_trade_missing_fields():
    trades = [{"timestamp": "t1", "action": "buy"}]  # no symbol/price/amount
    summary = performance_tracker.get_performance_summary(trades)
    assert summary["symbols"] == {}
    assert summary["total_trades"] == 0


# -----------------------------------------------------------------------------------
# 2. Basic Trade Flow
# -----------------------------------------------------------------------------------

def test_basic_buy_sell_win():
    trades = [
        {"timestamp": "t1", "action": "buy", "symbol": "BTC/USD", "price": 100, "amount": 1},
        {"timestamp": "t2", "action": "sell", "symbol": "BTC/USD", "price": 120, "amount": 1},
    ]
    summary = performance_tracker.get_performance_summary(trades)
    assert summary["total_pnl"] == 20
    assert summary["total_trades"] == 2  # buy + sell
    assert summary["win_rate"] == 1.0


def test_basic_buy_sell_loss():
    trades = [
        {"timestamp": "t1", "action": "buy", "symbol": "BTC/USD", "price": 100, "amount": 1},
        {"timestamp": "t2", "action": "sell", "symbol": "BTC/USD", "price": 90, "amount": 1},
    ]
    summary = performance_tracker.get_performance_summary(trades)
    assert summary["total_pnl"] == -10
    assert summary["total_trades"] == 2  # buy + sell
    assert summary["win_rate"] == 0.0


def test_partial_sell():
    trades = [
        {"timestamp": "t1", "action": "buy", "symbol": "BTC/USD", "price": 100, "amount": 2},
        {"timestamp": "t2", "action": "sell", "symbol": "BTC/USD", "price": 110, "amount": 1},
    ]
    summary = performance_tracker.get_performance_summary(trades)
    # Half of position sold: pnl = (110-100)*1 = 10
    assert summary["total_pnl"] == 10
    assert summary["total_trades"] == 2  # buy + sell
    assert summary["win_rate"] == 1.0


def test_multiple_buys_then_sell():
    trades = [
        {"timestamp": "t1", "action": "buy", "symbol": "BTC/USD", "price": 100, "amount": 1},
        {"timestamp": "t2", "action": "buy", "symbol": "BTC/USD", "price": 110, "amount": 1},
        {"timestamp": "t3", "action": "sell", "symbol": "BTC/USD", "price": 120, "amount": 2},
    ]
    summary = performance_tracker.get_performance_summary(trades)
    # PnL = (120-100)*1 + (120-110)*1 = 20 + 10 = 30
    assert summary["total_pnl"] == 30
    assert summary["total_trades"] == 3  # buy + buy + sell
    assert summary["win_rate"] == 1.0


# -----------------------------------------------------------------------------------
# 3. Multi-Symbol Handling
# -----------------------------------------------------------------------------------

def test_multiple_symbols():
    trades = [
        {"timestamp": "t1", "action": "buy", "symbol": "BTC/USD", "price": 100, "amount": 1},
        {"timestamp": "t2", "action": "sell", "symbol": "BTC/USD", "price": 120, "amount": 1},
        {"timestamp": "t3", "action": "buy", "symbol": "ETH/USD", "price": 50, "amount": 2},
        {"timestamp": "t4", "action": "sell", "symbol": "ETH/USD", "price": 55, "amount": 2},
    ]
    summary = performance_tracker.get_performance_summary(trades)
    assert summary["symbols"]["BTC/USD"]["pnl"] == 20
    assert summary["symbols"]["ETH/USD"]["pnl"] == 10
    assert summary["total_pnl"] == 30
    assert summary["total_trades"] == 4  # 2 buys + 2 sells
    assert summary["win_rate"] == 1.0


# -----------------------------------------------------------------------------------
# 4. Error Handling
# -----------------------------------------------------------------------------------

def test_sell_before_buy_raises_error():
    trades = [
        {"timestamp": "t1", "action": "sell", "symbol": "BTC/USD", "price": 120, "amount": 1},
    ]
    with pytest.raises(InvalidTradeSequenceError):
        performance_tracker.get_performance_summary(trades)


def test_oversell_raises_error():
    trades = [
        {"timestamp": "t1", "action": "buy", "symbol": "BTC/USD", "price": 100, "amount": 1},
        {"timestamp": "t2", "action": "sell", "symbol": "BTC/USD", "price": 110, "amount": 2},
    ]
    with pytest.raises(InvalidTradeSequenceError):
        performance_tracker.get_performance_summary(trades)


# -----------------------------------------------------------------------------------
# 5. Persistence & Replay
# -----------------------------------------------------------------------------------

def test_persistence_round_trip(tmp_path):
    trades = [
        {"timestamp": "t1", "action": "buy", "symbol": "BTC/USD", "price": 100, "amount": 1},
        {"timestamp": "t2", "action": "sell", "symbol": "BTC/USD", "price": 120, "amount": 1},
    ]
    trades_file = tmp_path / "trades.json"
    trades_file.write_text(json.dumps(trades))

    tracker = performance_tracker
    tracker.trades_file = trades_file

    loaded_summary = tracker.get_performance_summary()
    direct_summary = tracker.get_performance_summary(trades)

    assert loaded_summary == direct_summary


def test_replay_vs_batch_consistency():
    trades = [
        {"timestamp": "t1", "action": "buy", "symbol": "BTC/USD", "price": 100, "amount": 1},
        {"timestamp": "t2", "action": "sell", "symbol": "BTC/USD", "price": 120, "amount": 1},
    ]
    replay_summary = performance_tracker.get_performance_summary(trades)
    batch_summary = performance_tracker.get_performance_summary(trades.copy())
    assert replay_summary == batch_summary


# -----------------------------------------------------------------------------------
# 6. Output Contract
# -----------------------------------------------------------------------------------

def test_output_contract_with_no_trades():
    summary = performance_tracker.get_performance_summary([])
    assert set(summary.keys()) == {"symbols", "total_pnl", "total_trades", "win_rate"}


def test_output_contract_with_real_trades():
    trades = [
        {"timestamp": "t1", "action": "buy", "symbol": "BTC/USD", "price": 100, "amount": 1},
        {"timestamp": "t2", "action": "sell", "symbol": "BTC/USD", "price": 120, "amount": 1},
    ]
    summary = performance_tracker.get_performance_summary(trades)
    assert "BTC/USD" in summary["symbols"]
    assert set(summary["symbols"]["BTC/USD"].keys()) >= {"pnl", "trades", "wins", "losses", "win_rate"}
