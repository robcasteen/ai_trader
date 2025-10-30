import pytest
import json
from pathlib import Path
from app.logic.paper_trader import PaperTrader


@pytest.fixture
def paper_trader(tmp_path):
    """Create a PaperTrader instance with temporary files."""
    trader = PaperTrader()
    trader.trades_file = tmp_path / "trades.json"
    trader.holdings_file = tmp_path / "holdings.json"

    # Initialize empty files
    with open(trader.trades_file, "w") as f:
        json.dump([], f)
    with open(trader.holdings_file, "w") as f:
        json.dump({}, f)

    return trader


def test_cannot_sell_nonexistent_position(paper_trader):
    """Test that selling a position you don't own fails."""
    result = paper_trader.execute_trade(
        symbol="BTCUSD",
        action="SELL",
        price=67000.0,
        balance=200.0,
        reason="test"
    )

    assert result["success"] is False
    assert result["action"] == "SELL"
    assert result["symbol"] == "BTCUSD"
    assert "no position" in result["message"].lower()


def test_cannot_sell_zero_amount_position(paper_trader):
    """Test that selling when amount is 0 fails."""
    # Create holding with 0 amount
    holdings = {"BTCUSD": {"amount": 0, "avg_price": 67000.0}}
    with open(paper_trader.holdings_file, "w") as f:
        json.dump(holdings, f)

    result = paper_trader.execute_trade(
        symbol="BTCUSD",
        action="SELL",
        price=67000.0,
        balance=200.0,
        reason="test"
    )

    assert result["success"] is False
    assert "no position" in result["message"].lower()


def test_can_sell_existing_position(paper_trader):
    """Test that selling an existing position succeeds."""
    # Create holding
    holdings = {"BTCUSD": {"amount": 0.01, "avg_price": 67000.0}}
    with open(paper_trader.holdings_file, "w") as f:
        json.dump(holdings, f)

    result = paper_trader.execute_trade(
        symbol="BTCUSD",
        action="SELL",
        price=68000.0,
        balance=200.0,
        reason="test",
        amount=0.01
    )

    # Returns trade dict on success
    assert result["action"] == "sell"
    assert result["symbol"] == "BTCUSD"
    assert "timestamp" in result


def test_sell_validation_uses_canonical_symbol(paper_trader):
    """Test that SELL validation normalizes symbol format."""
    # Create holding with canonical symbol
    holdings = {"BTCUSD": {"amount": 0.01, "avg_price": 67000.0}}
    with open(paper_trader.holdings_file, "w") as f:
        json.dump(holdings, f)

    # Try to sell using different format
    result = paper_trader.execute_trade(
        symbol="BTC/USD",
        action="SELL",
        price=68000.0,
        balance=200.0,
        reason="test",
        amount=0.01
    )

    # Should succeed because BTC/USD normalizes to BTCUSD
    assert result["action"] == "sell"
    assert result["symbol"] == "BTCUSD"


def test_buy_still_works_without_position(paper_trader):
    """Test that BUY works even without existing position."""
    result = paper_trader.execute_trade(
        symbol="ETHUSD",
        action="BUY",
        price=2500.0,
        balance=200.0,
        reason="test",
        amount=0.01
    )

    assert result["action"] == "buy"
    assert result["symbol"] == "ETHUSD"
    assert "timestamp" in result
