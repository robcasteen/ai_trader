"""
Unit tests for PaperTrader.

Tests cover:
- Trade execution and logging
- JSON file creation and updates
- Trade data structure validation
- File persistence across operations
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from app.logic.paper_trader import PaperTrader


@pytest.fixture
def temp_trades_file(tmp_path):
    """Fixture providing a temporary trades file."""
    trades_file = tmp_path / "trades.json"
    return trades_file


@pytest.fixture
def paper_trader(temp_trades_file):
    """Fixture providing a PaperTrader with temp file."""
    trader = PaperTrader()
    trader.trades_file = temp_trades_file
    # Initialize empty trades file
    with open(temp_trades_file, "w") as f:
        json.dump([], f)
    return trader


class TestTradeExecution:
    def test_execute_buy_trade(self, paper_trader):
        """Test execution of a buy trade."""
        result = paper_trader.execute_trade(
            symbol="BTC/USD",
            action="buy",
            price=50000.0,
            balance=10000.0,
            reason="Positive sentiment",
            amount=0.1
        )
        
        assert result["action"] == "buy"
        assert result["symbol"] == "BTC/USD"
        assert result["price"] == 50000.0
        assert result["amount"] == 0.1
        assert result["value"] == 5000.0
        assert result["reason"] == "Positive sentiment"
        assert "timestamp" in result

    def test_execute_sell_trade(self, paper_trader):
        """Test execution of a sell trade."""
        result = paper_trader.execute_trade(
            symbol="ETH/USD",
            action="sell",
            price=3000.0,
            balance=5000.0,
            reason="Negative news",
            amount=0.5
        )
        
        assert result["action"] == "sell"
        assert result["symbol"] == "ETH/USD"
        assert result["value"] == 1500.0

    def test_default_amount(self, paper_trader):
        """Test trade with default amount."""
        result = paper_trader.execute_trade(
            symbol="BTC/USD",
            action="buy",
            price=50000.0,
            balance=10000.0,
            reason="Test"
        )
        
        assert result["amount"] == 0.01
        assert result["value"] == 500.0


class TestFilePersistence:
    def test_trades_persisted_to_file(self, paper_trader):
        """Test that trades are written to file."""
        paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 10000.0, "Test", 0.1
        )
        
        assert paper_trader.trades_file.exists()
        with open(paper_trader.trades_file, "r") as f:
            trades = json.load(f)
        
        assert len(trades) == 1
        assert trades[0]["symbol"] == "BTC/USD"

    def test_multiple_trades_appended(self, paper_trader):
        """Test that multiple trades are appended correctly."""
        paper_trader.execute_trade("BTC/USD", "buy", 50000.0, 10000.0, "Test 1")
        paper_trader.execute_trade("ETH/USD", "sell", 3000.0, 5000.0, "Test 2")
        paper_trader.execute_trade("SOL/USD", "buy", 100.0, 1000.0, "Test 3")
        
        with open(paper_trader.trades_file, "r") as f:
            trades = json.load(f)
        
        assert len(trades) == 3
        assert trades[0]["symbol"] == "BTC/USD"
        assert trades[1]["symbol"] == "ETH/USD"
        assert trades[2]["symbol"] == "SOL/USD"

    def test_corrupted_file_recovery(self, paper_trader):
        """Test recovery when trades file is corrupted."""
        # Write corrupted data
        with open(paper_trader.trades_file, "w") as f:
            f.write("{ invalid json }")
        
        # Should still execute and create new list
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 10000.0, "Recovery test"
        )
        
        assert result is not None
        
        # Check file now contains valid data
        with open(paper_trader.trades_file, "r") as f:
            trades = json.load(f)
        
        assert len(trades) == 1


class TestTradeDataStructure:
    def test_timestamp_format(self, paper_trader):
        """Test that timestamp is in ISO format."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 10000.0, "Test"
        )
        
        # Should be parseable as datetime
        timestamp = datetime.fromisoformat(result["timestamp"])
        assert isinstance(timestamp, datetime)

    def test_value_calculation(self, paper_trader):
        """Test that value is calculated correctly."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 10000.0, "Test", 0.123
        )
        
        expected_value = round(0.123 * 50000.0, 2)
        assert result["value"] == expected_value

    def test_all_required_fields_present(self, paper_trader):
        """Test that all required fields are in trade result."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 10000.0, "Test"
        )
        
        required_fields = [
            "timestamp", "action", "symbol", 
            "price", "amount", "value", "reason"
        ]
        for field in required_fields:
            assert field in result


class TestEdgeCases:
    def test_zero_price(self, paper_trader):
        """Test trade with zero price."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 0.0, 10000.0, "Test"
        )
        
        assert result["value"] == 0.0

    def test_large_amounts(self, paper_trader):
        """Test trade with large amounts."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 10000000.0, "Test", 100.0
        )
        
        assert result["amount"] == 100.0
        assert result["value"] == 5000000.0

    def test_fractional_amounts(self, paper_trader):
        """Test trade with very small fractional amounts."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 10000.0, "Test", 0.00001
        )
        
        assert result["amount"] == 0.00001
        assert result["value"] == 0.5