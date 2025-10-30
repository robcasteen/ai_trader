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
def paper_trader(temp_trades_file, tmp_path):
    """Fixture providing a PaperTrader with temp file."""
    trader = PaperTrader()
    trader.trades_file = temp_trades_file
    trader.holdings_file = tmp_path / "holdings.json"
    # Initialize empty trades file
    with open(temp_trades_file, "w") as f:
        json.dump([], f)
    # Initialize empty holdings file
    with open(trader.holdings_file, "w") as f:
        json.dump({}, f)
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
        assert result["symbol"] == "BTCUSD"
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
        # First buy to create position
        paper_trader.execute_trade(
            symbol="ETH/USD",
            action="buy",
            price=2900.0,
            balance=5000.0,
            reason="Setup",
            amount=0.5
        )

        # Now sell
        result = paper_trader.execute_trade(
            symbol="ETH/USD",
            action="sell",
            price=3000.0,
            balance=5000.0,
            reason="Negative news",
            amount=0.5
        )
        
        assert result["action"] == "sell"
        assert result["symbol"] == "ETHUSD"
        
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
        # First buy to create position
        paper_trader.execute_trade(
            "BTC/USD", "buy", 9500.0, 10000.0, "Setup", 1.0
        )

        # Now sell
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
        """
Test that holdings.json is updated when trades execute.

This test should FAIL with current code (holdings not updated)
and PASS after adding update_holdings() call to execute_trade().
"""

import pytest
import json
from pathlib import Path
from app.logic.paper_trader import PaperTrader


@pytest.fixture
def temp_files(tmp_path):
    """Fixture providing temporary trades and holdings files."""
    trades_file = tmp_path / "trades.json"
    holdings_file = tmp_path / "holdings.json"
    return trades_file, holdings_file


@pytest.fixture
def paper_trader_with_holdings(temp_files):
    """Fixture providing a PaperTrader with temp files for trades and holdings."""
    trades_file, holdings_file = temp_files
    trader = PaperTrader()
    trader.trades_file = trades_file
    trader.holdings_file = holdings_file
    
    # Initialize empty files
    with open(trades_file, "w") as f:
        json.dump([], f)
    with open(holdings_file, "w") as f:
        json.dump({}, f)
    
    return trader


class TestHoldingsUpdateOnTrade:
    """Test that holdings are updated when trades execute."""
    
    def test_buy_trade_creates_holding(self, paper_trader_with_holdings):
        """Test that executing a BUY trade creates a holding."""
        trader = paper_trader_with_holdings
        
        # Execute a buy trade
        trader.execute_trade(
            symbol="BTCUSD",
            action="buy",
            price=50000.0,
            balance=10000.0,
            reason="Test buy",
            amount=0.1
        )
        
        # Verify holdings.json was updated
        holdings = trader.get_holdings()
        
        assert "BTCUSD" in holdings
        assert holdings["BTCUSD"]["amount"] == 0.1
        assert holdings["BTCUSD"]["avg_price"] == 50000.0
        assert holdings["BTCUSD"]["current_price"] == 50000.0
        assert holdings["BTCUSD"]["market_value"] == 5000.0
        assert holdings["BTCUSD"]["cost_basis"] == 5000.0
        assert holdings["BTCUSD"]["unrealized_pnl"] == 0.0
    
    def test_sell_trade_reduces_holding(self, paper_trader_with_holdings):
        """Test that executing a SELL trade reduces a holding."""
        trader = paper_trader_with_holdings
        
        # First buy
        trader.execute_trade(
            symbol="BTCUSD",
            action="buy",
            price=50000.0,
            balance=10000.0,
            reason="Test buy",
            amount=0.1
        )
        
        # Then sell half
        trader.execute_trade(
            symbol="BTCUSD",
            action="sell",
            price=51000.0,
            balance=10000.0,
            reason="Test sell",
            amount=0.05
        )
        
        # Verify holdings updated
        holdings = trader.get_holdings()
        
        assert "BTCUSD" in holdings
        assert holdings["BTCUSD"]["amount"] == 0.05
        assert holdings["BTCUSD"]["avg_price"] == 50000.0  # Unchanged
        assert holdings["BTCUSD"]["current_price"] == 51000.0
        assert holdings["BTCUSD"]["market_value"] == 2550.0  # 0.05 * 51000
        assert holdings["BTCUSD"]["unrealized_pnl"] == 50.0  # Profit from price increase
    
    def test_sell_entire_position_removes_holding(self, paper_trader_with_holdings):
        """Test that selling entire position removes it from holdings."""
        trader = paper_trader_with_holdings
        
        # Buy
        trader.execute_trade(
            symbol="ETHUSD",
            action="buy",
            price=3000.0,
            balance=10000.0,
            reason="Test buy",
            amount=1.0
        )
        
        # Sell entire position
        trader.execute_trade(
            symbol="ETHUSD",
            action="sell",
            price=3100.0,
            balance=10000.0,
            reason="Test sell",
            amount=1.0
        )
        
        # Verify position removed
        holdings = trader.get_holdings()
        assert "ETHUSD" not in holdings
    
    def test_multiple_buys_average_price(self, paper_trader_with_holdings):
        """Test that multiple buys correctly calculate average price."""
        trader = paper_trader_with_holdings
        
        # First buy: 0.1 BTC at $50,000
        trader.execute_trade(
            symbol="BTCUSD",
            action="buy",
            price=50000.0,
            balance=10000.0,
            reason="First buy",
            amount=0.1
        )
        
        # Second buy: 0.1 BTC at $60,000
        trader.execute_trade(
            symbol="BTCUSD",
            action="buy",
            price=60000.0,
            balance=10000.0,
            reason="Second buy",
            amount=0.1
        )
        
        # Verify average price
        holdings = trader.get_holdings()
        
        assert holdings["BTCUSD"]["amount"] == 0.2
        # Average: (0.1 * 50000 + 0.1 * 60000) / 0.2 = 55000
        assert holdings["BTCUSD"]["avg_price"] == 55000.0
        assert holdings["BTCUSD"]["cost_basis"] == 11000.0  # 0.2 * 55000
    
    def test_hold_action_does_not_update_holdings(self, paper_trader_with_holdings):
        """Test that HOLD actions don't update holdings."""
        trader = paper_trader_with_holdings
        
        # Execute hold (should do nothing to holdings)
        trader.execute_trade(
            symbol="BTCUSD",
            action="hold",
            price=50000.0,
            balance=10000.0,
            reason="Low confidence",
            amount=0.1
        )
        
        # Verify holdings still empty
        holdings = trader.get_holdings()
        assert holdings == {}
    
    def test_multiple_symbols_tracked_separately(self, paper_trader_with_holdings):
        """Test that multiple symbols are tracked independently."""
        trader = paper_trader_with_holdings
        
        # Buy BTC
        trader.execute_trade(
            symbol="BTCUSD",
            action="buy",
            price=50000.0,
            balance=10000.0,
            reason="Buy BTC",
            amount=0.1
        )
        
        # Buy ETH
        trader.execute_trade(
            symbol="ETHUSD",
            action="buy",
            price=3000.0,
            balance=10000.0,
            reason="Buy ETH",
            amount=1.0
        )
        
        # Verify both tracked
        holdings = trader.get_holdings()
        
        assert "BTCUSD" in holdings
        assert "ETHUSD" in holdings
        assert holdings["BTCUSD"]["amount"] == 0.1
        assert holdings["ETHUSD"]["amount"] == 1.0
    
