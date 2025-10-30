"""
Test that PaperTrader normalizes symbols to prevent duplicate position tracking.
"""

import pytest
import json
from pathlib import Path
from app.logic.paper_trader import PaperTrader


@pytest.fixture
def paper_trader_normalized(tmp_path):
    """Fixture providing a PaperTrader with temp files."""
    trades_file = tmp_path / "trades.json"
    holdings_file = tmp_path / "holdings.json"
    
    trader = PaperTrader()
    trader.trades_file = trades_file
    trader.holdings_file = holdings_file
    
    # Initialize empty files
    with open(trades_file, "w") as f:
        json.dump([], f)
    with open(holdings_file, "w") as f:
        json.dump({}, f)
    
    return trader


class TestSymbolNormalization:
    """Test that different symbol formats are normalized to canonical format."""
    
    def test_buy_with_slash_format_normalizes(self, paper_trader_normalized):
        """Test that BTC/USD normalizes to BTCUSD in holdings."""
        trader = paper_trader_normalized
        
        trader.execute_trade(
            symbol="BTC/USD",
            action="buy",
            price=50000.0,
            balance=10000.0,
            reason="Test",
            amount=0.1
        )
        
        holdings = trader.get_holdings()
        
        assert "BTCUSD" in holdings
        assert "BTC/USD" not in holdings
        assert holdings["BTCUSD"]["amount"] == 0.1
    
    def test_multiple_formats_same_position(self, paper_trader_normalized):
        """Test that trades with different formats update the same position."""
        trader = paper_trader_normalized
        
        trader.execute_trade(
            symbol="BTC/USD",
            action="buy",
            price=50000.0,
            balance=10000.0,
            reason="First buy",
            amount=0.1
        )
        
        trader.execute_trade(
            symbol="BTCUSD",
            action="buy",
            price=51000.0,
            balance=10000.0,
            reason="Second buy",
            amount=0.05
        )
        
        holdings = trader.get_holdings()
        
        assert len(holdings) == 1
        assert "BTCUSD" in holdings
        # Use pytest.approx for floating point comparison
        assert holdings["BTCUSD"]["amount"] == pytest.approx(0.15, abs=1e-10)
    
    def test_kraken_format_normalizes(self, paper_trader_normalized):
        """Test that Kraken format (XBTCUSD) normalizes to BTCUSD."""
        trader = paper_trader_normalized
        
        trader.execute_trade(
            symbol="XBTCUSD",
            action="buy",
            price=50000.0,
            balance=10000.0,
            reason="Test",
            amount=0.1
        )
        
        holdings = trader.get_holdings()
        
        assert "BTCUSD" in holdings
        assert "XBTCUSD" not in holdings
    
    def test_sell_with_different_format_reduces_position(self, paper_trader_normalized):
        """Test that selling with different format reduces the same position."""
        trader = paper_trader_normalized
        
        trader.execute_trade(
            symbol="BTCUSD",
            action="buy",
            price=50000.0,
            balance=10000.0,
            reason="Buy",
            amount=0.1
        )
        
        trader.execute_trade(
            symbol="BTC/USD",
            action="sell",
            price=51000.0,
            balance=10000.0,
            reason="Sell",
            amount=0.05
        )
        
        holdings = trader.get_holdings()
        
        assert "BTCUSD" in holdings
        assert holdings["BTCUSD"]["amount"] == pytest.approx(0.05, abs=1e-10)
    
    def test_trades_log_uses_canonical_format(self, paper_trader_normalized):
        """Test that trades are logged with canonical symbol format."""
        trader = paper_trader_normalized
        
        trader.execute_trade("BTC/USD", "buy", 50000.0, 10000.0, "Test 1", 0.1)
        trader.execute_trade("XBTCUSD", "buy", 51000.0, 10000.0, "Test 2", 0.05)
        trader.execute_trade("Bitcoin", "sell", 52000.0, 10000.0, "Test 3", 0.03)
        
        with open(trader.trades_file, "r") as f:
            trades = json.load(f)
        
        assert all(trade["symbol"] == "BTCUSD" for trade in trades)
    
    def test_case_insensitive_symbol_handling(self, paper_trader_normalized):
        """Test that symbol matching is case-insensitive."""
        trader = paper_trader_normalized
        
        trader.execute_trade("btc", "buy", 50000.0, 10000.0, "Test", 0.1)
        trader.execute_trade("BTC", "buy", 51000.0, 10000.0, "Test", 0.05)
        trader.execute_trade("Bitcoin", "sell", 52000.0, 10000.0, "Test", 0.03)
        
        holdings = trader.get_holdings()
        
        assert len(holdings) == 1
        assert "BTCUSD" in holdings
        assert holdings["BTCUSD"]["amount"] == pytest.approx(0.12, abs=1e-10)
    
    def test_multiple_symbols_normalized_separately(self, paper_trader_normalized):
        """Test that different symbols are tracked separately after normalization."""
        trader = paper_trader_normalized
        
        trader.execute_trade("BTC/USD", "buy", 50000.0, 10000.0, "Buy BTC", 0.1)
        trader.execute_trade("ETH/USD", "buy", 3000.0, 10000.0, "Buy ETH", 1.0)
        trader.execute_trade("XBTCUSD", "buy", 51000.0, 10000.0, "More BTC", 0.05)
        
        holdings = trader.get_holdings()
        
        assert len(holdings) == 2
        assert "BTCUSD" in holdings
        assert "ETHUSD" in holdings
        assert holdings["BTCUSD"]["amount"] == pytest.approx(0.15, abs=1e-10)
        assert holdings["ETHUSD"]["amount"] == 1.0
