"""
Unit tests for PaperTrader with CORRECTED transaction fees.

Tests cover:
- Trade execution and logging with fees
- JSON file creation and updates
- Trade data structure validation
- File persistence across operations
- Correct fee application (fees reduce proceeds for both buy and sell)
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
        """Test execution of a buy trade with fees."""
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
        
        # Gross value = 0.1 * 50000 = 5000
        assert result["gross_value"] == 5000.0
        
        # Fee = 5000 * 0.0026 = 13
        assert result["fee"] == 13.0
        
        # Net value for BUY = gross + fee = 5000 + 13 = 5013 (total cost)
        assert result["net_value"] == 5013.0
        assert result["value"] == 5013.0
        
        assert result["reason"] == "Positive sentiment"
        assert "timestamp" in result

    def test_execute_sell_trade(self, paper_trader):
        """Test execution of a sell trade with fees."""
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
        
        # Gross value = 0.5 * 3000 = 1500
        assert result["gross_value"] == 1500.0
        
        # Fee = 1500 * 0.0026 = 3.9
        assert result["fee"] == 3.9
        
        # Net value for SELL = gross - fee = 1500 - 3.9 = 1496.1 (what you receive)
        assert result["net_value"] == 1496.1
        assert result["value"] == 1496.1

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
        # Gross = 0.01 * 50000 = 500
        # Fee = 500 * 0.0026 = 1.3
        # Net = 500 + 1.3 = 501.3 (buy cost)
        assert result["value"] == 501.3


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
        assert "fee" in trades[0]
        assert "gross_value" in trades[0]

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
        """Test that value is calculated correctly with fees."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 10000.0, "Test", 0.123
        )
        
        # Gross = 0.123 * 50000 = 6150
        gross_value = 0.123 * 50000.0
        assert result["gross_value"] == round(gross_value, 2)
        
        # Fee = 6150 * 0.0026 = 15.99
        fee = gross_value * 0.0026
        assert result["fee"] == round(fee, 2)
        
        # Net = 6150 + 15.99 = 6165.99 (buy cost includes fee)
        expected_net = round(gross_value + fee, 2)
        assert result["net_value"] == expected_net
        assert result["value"] == expected_net

    def test_all_required_fields_present(self, paper_trader):
        """Test that all required fields are in trade result."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 10000.0, "Test"
        )
        
        required_fields = [
            "timestamp", "action", "symbol", 
            "price", "amount", "value", "reason",
            "gross_value", "fee", "net_value"
        ]
        for field in required_fields:
            assert field in result


class TestEdgeCases:
    def test_zero_price(self, paper_trader):
        """Test trade with zero price."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 0.0, 10000.0, "Test"
        )
        
        assert result["gross_value"] == 0.0
        assert result["fee"] == 0.0
        assert result["net_value"] == 0.0

    def test_large_amounts(self, paper_trader):
        """Test trade with large amounts."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 10000000.0, "Test", 100.0
        )
        
        assert result["amount"] == 100.0
        # Gross = 100 * 50000 = 5,000,000
        assert result["gross_value"] == 5000000.0
        # Fee = 5,000,000 * 0.0026 = 13,000
        assert result["fee"] == 13000.0
        # Net = 5,000,000 + 13,000 = 5,013,000 (buy cost)
        assert result["net_value"] == 5013000.0

    def test_fractional_amounts(self, paper_trader):
        """Test trade with very small fractional amounts."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 10000.0, "Test", 0.00001
        )
        
        assert result["amount"] == 0.00001
        # Gross = 0.00001 * 50000 = 0.5
        assert result["gross_value"] == 0.5
        # Fee = 0.5 * 0.0026 = 0.0013, rounded to 0.0
        assert result["fee"] == 0.0
        # Net = 0.5 + 0.0 = 0.5
        assert result["net_value"] == 0.5


class TestFeeCalculation:
    """Test suite specifically for CORRECT fee calculations."""
    
    def test_buy_fee_increases_cost(self, paper_trader):
        """Test that buying applies fee correctly (increases total cost)."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 10000.0, 10000.0, "Test", 1.0
        )
        
        # When you BUY, you pay the asset price PLUS the fee
        # Gross = 10000
        # Fee = 10000 * 0.0026 = 26
        # Net = 10000 + 26 = 10026 (total you pay)
        assert result["gross_value"] == 10000.0
        assert result["fee"] == 26.0
        assert result["net_value"] == 10026.0
    
    def test_sell_fee_reduces_proceeds(self, paper_trader):
        """Test that selling applies fee correctly (reduces what you receive)."""
        result = paper_trader.execute_trade(
            "BTC/USD", "sell", 10000.0, 10000.0, "Test", 1.0
        )
        
        # When you SELL, you receive the asset price MINUS the fee
        # Gross = 10000
        # Fee = 10000 * 0.0026 = 26
        # Net = 10000 - 26 = 9974 (total you receive)
        assert result["gross_value"] == 10000.0
        assert result["fee"] == 26.0
        assert result["net_value"] == 9974.0
    
    def test_fee_rate_is_correct(self, paper_trader):
        """Test that fee rate is 0.26% (0.0026)."""
        result = paper_trader.execute_trade(
            "BTC/USD", "buy", 1000.0, 10000.0, "Test", 1.0
        )
        
        # Fee should be exactly 0.26% of gross value
        expected_fee = 1000.0 * 0.0026
        assert result["fee"] == round(expected_fee, 2)
    
    def test_round_trip_cost(self, paper_trader):
        """Test the total cost of a round trip (buy then sell same amount)."""
        # Buy 1 BTC at $50,000
        buy = paper_trader.execute_trade(
            "BTC/USD", "buy", 50000.0, 100000.0, "Test", 1.0
        )
        
        # Sell 1 BTC at $50,000 (same price)
        sell = paper_trader.execute_trade(
            "BTC/USD", "sell", 50000.0, 100000.0, "Test", 1.0
        )
        
        # Total cost = what you paid - what you received
        # Buy cost: 50000 + 130 = 50130
        # Sell proceeds: 50000 - 130 = 49870
        # Net loss: 50130 - 49870 = 260 (0.52% round trip fee)
        total_paid = buy["net_value"]
        total_received = sell["net_value"]
        round_trip_cost = total_paid - total_received
        
        assert round_trip_cost == 260.0  # 2 * fee (0.26% * 2)