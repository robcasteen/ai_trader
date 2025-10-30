"""
Tests for BacktestPortfolio - TDD approach for portfolio simulation.
"""

import pytest
from datetime import datetime
from app.backtesting.backtest_engine import BacktestPortfolio


class TestBacktestPortfolio:
    """Test portfolio simulation for backtesting."""

    def test_portfolio_initialization(self):
        """Test portfolio starts with correct initial values."""
        portfolio = BacktestPortfolio(initial_capital=10000.0, fee_rate=0.0026)

        assert portfolio.initial_capital == 10000.0
        assert portfolio.cash == 10000.0
        assert portfolio.fee_rate == 0.0026
        assert len(portfolio.positions) == 0
        assert len(portfolio.trades) == 0
        assert len(portfolio.portfolio_values) == 0

    def test_buy_order_success(self):
        """Test successful buy order execution."""
        portfolio = BacktestPortfolio(initial_capital=10000.0)
        timestamp = datetime.now()

        result = portfolio.buy("BTCUSD", 50000.0, 0.1, timestamp)

        assert result is True
        assert portfolio.positions["BTCUSD"] == 0.1
        assert portfolio.cash < 10000.0  # Cash decreased
        assert len(portfolio.trades) == 1

        # Check trade details
        trade = portfolio.trades[0]
        assert trade["action"] == "BUY"
        assert trade["symbol"] == "BTCUSD"
        assert trade["price"] == 50000.0
        assert trade["amount"] == 0.1
        assert trade["fee"] > 0  # Fee was charged

    def test_buy_order_insufficient_funds(self):
        """Test buy order fails with insufficient funds."""
        portfolio = BacktestPortfolio(initial_capital=1000.0)
        timestamp = datetime.now()

        result = portfolio.buy("BTCUSD", 50000.0, 1.0, timestamp)

        assert result is False
        assert "BTCUSD" not in portfolio.positions
        assert portfolio.cash == 1000.0  # Cash unchanged
        assert len(portfolio.trades) == 0

    def test_sell_order_success(self):
        """Test successful sell order execution."""
        portfolio = BacktestPortfolio(initial_capital=10000.0)
        timestamp = datetime.now()

        # First buy
        portfolio.buy("BTCUSD", 50000.0, 0.1, timestamp)
        initial_cash = portfolio.cash

        # Then sell
        result = portfolio.sell("BTCUSD", 51000.0, 0.1, timestamp)

        assert result is True
        assert "BTCUSD" not in portfolio.positions  # Position closed
        assert portfolio.cash > initial_cash  # Made profit
        assert len(portfolio.trades) == 2

    def test_sell_order_insufficient_holdings(self):
        """Test sell order fails with insufficient holdings."""
        portfolio = BacktestPortfolio(initial_capital=10000.0)
        timestamp = datetime.now()

        result = portfolio.sell("BTCUSD", 50000.0, 0.1, timestamp)

        assert result is False
        assert len(portfolio.trades) == 0

    def test_partial_sell(self):
        """Test selling part of a position."""
        portfolio = BacktestPortfolio(initial_capital=10000.0)
        timestamp = datetime.now()

        portfolio.buy("BTCUSD", 50000.0, 0.19, timestamp)  # 9500 + 24.7 fee = 9524.7 total
        portfolio.sell("BTCUSD", 51000.0, 0.09, timestamp)  # Sell about half

        assert portfolio.positions.get("BTCUSD", 0) == 0.1  # 0.19 - 0.09 = 0.1 remaining
        assert len(portfolio.trades) == 2

    def test_fee_calculation(self):
        """Test trading fees are calculated correctly."""
        portfolio = BacktestPortfolio(initial_capital=10000.0, fee_rate=0.01)  # 1% fee
        timestamp = datetime.now()

        portfolio.buy("BTCUSD", 1000.0, 1.0, timestamp)

        trade = portfolio.trades[0]
        expected_fee = 1000.0 * 0.01  # 1% of $1000
        assert trade["fee"] == expected_fee
        assert trade["total_cost"] == 1000.0 + expected_fee

    def test_get_portfolio_value(self):
        """Test portfolio value calculation."""
        portfolio = BacktestPortfolio(initial_capital=10000.0)
        timestamp = datetime.now()

        # Buy some assets
        portfolio.buy("BTCUSD", 50000.0, 0.1, timestamp)
        portfolio.buy("ETHUSD", 3000.0, 1.0, timestamp)

        # Calculate value at new prices
        current_prices = {"BTCUSD": 52000.0, "ETHUSD": 3200.0}
        value = portfolio.get_portfolio_value(current_prices)

        expected_holdings = (0.1 * 52000.0) + (1.0 * 3200.0)
        expected_total = portfolio.cash + expected_holdings

        assert value == expected_total

    def test_record_value_snapshot(self):
        """Test recording portfolio value over time."""
        portfolio = BacktestPortfolio(initial_capital=10000.0)
        timestamp = datetime.now()

        prices = {"BTCUSD": 50000.0}
        portfolio.record_value(timestamp, prices)

        assert len(portfolio.portfolio_values) == 1
        snapshot = portfolio.portfolio_values[0]
        assert snapshot["timestamp"] == timestamp
        assert snapshot["cash"] == 10000.0
        assert snapshot["total_value"] == 10000.0

    def test_multiple_positions(self):
        """Test managing multiple positions simultaneously."""
        portfolio = BacktestPortfolio(initial_capital=10000.0)
        timestamp = datetime.now()

        portfolio.buy("BTCUSD", 50000.0, 0.05, timestamp)
        portfolio.buy("ETHUSD", 3000.0, 0.5, timestamp)
        portfolio.buy("SOLUSD", 100.0, 5.0, timestamp)

        assert len(portfolio.positions) == 3
        assert portfolio.positions["BTCUSD"] == 0.05
        assert portfolio.positions["ETHUSD"] == 0.5
        assert portfolio.positions["SOLUSD"] == 5.0
