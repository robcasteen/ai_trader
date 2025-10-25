"""
Test that paper_trader correctly handles HOLD actions - FIXED VERSION.

Save this as: tests/test_paper_trader_hold.py

Run with: pytest tests/test_paper_trader_hold.py -v
"""
import pytest
from unittest.mock import patch
from pathlib import Path


class TestPaperTraderHoldActions:
    """Test HOLD action handling in paper trader."""
    
    def test_hold_does_not_execute_trade(self, tmp_path):
        """Test that HOLD actions do not create trades."""
        trades_file = tmp_path / "trades.json"
        trades_file.write_text('[]')
        
        holdings_file = tmp_path / "holdings.json"
        holdings_file.write_text('{}')
        
        # Patch the module-level constants before importing
        with patch('app.logic.paper_trader.TRADES_FILE', trades_file):
            with patch('app.logic.paper_trader.HOLDINGS_FILE', holdings_file):
                from app.logic.paper_trader import PaperTrader
                
                trader = PaperTrader()
                
                # Execute HOLD action
                result = trader.execute_trade(
                    symbol="BTCUSD",
                    action="HOLD",
                    price=100000.0,
                    balance=10000.0,
                    reason="No strong signal",
                    amount=0.01
                )
                
                # Should return success but not execute
                assert result["success"] == True
                assert result["action"] == "HOLD"
                assert "No trade executed" in result.get("message", "")
                
                # Should NOT add to trades.json
                import json
                with open(trades_file) as f:
                    trades = json.load(f)
                
                assert len(trades) == 0  # No trades should be created
    
    def test_hold_does_not_modify_holdings(self, tmp_path):
        """Test that HOLD actions do not modify holdings."""
        holdings_file = tmp_path / "holdings.json"
        initial_holdings = {"BTCUSD": {"amount": 0.05, "avg_price": 99000.0, "cost_basis": 4950.0}}
        holdings_file.write_text('{"BTCUSD": {"amount": 0.05, "avg_price": 99000.0, "cost_basis": 4950.0}}')
        
        trades_file = tmp_path / "trades.json"
        trades_file.write_text('[]')
        
        with patch('app.logic.paper_trader.TRADES_FILE', trades_file):
            with patch('app.logic.paper_trader.HOLDINGS_FILE', holdings_file):
                from app.logic.paper_trader import PaperTrader
                
                trader = PaperTrader()
                
                # Execute HOLD action
                trader.execute_trade(
                    symbol="BTCUSD",
                    action="HOLD",
                    price=100000.0,
                    balance=10000.0,
                    reason="No strong signal",
                    amount=0.01
                )
                
                # Holdings should be unchanged
                import json
                with open(holdings_file) as f:
                    holdings = json.load(f)
                
                assert holdings == initial_holdings
    
    def test_buy_executes_correctly(self, tmp_path):
        """Test that BUY actions still work correctly."""
        trades_file = tmp_path / "trades.json"
        trades_file.write_text('[]')
        
        holdings_file = tmp_path / "holdings.json"
        holdings_file.write_text('{}')
        
        with patch('app.logic.paper_trader.TRADES_FILE', trades_file):
            with patch('app.logic.paper_trader.HOLDINGS_FILE', holdings_file):
                from app.logic.paper_trader import PaperTrader
                
                trader = PaperTrader()
                
                result = trader.execute_trade(
                    symbol="BTCUSD",
                    action="BUY",
                    price=100000.0,
                    balance=10000.0,
                    reason="Strong buy signal",
                    amount=0.01
                )
                
                assert result["success"] == True
                assert result["action"] == "BUY"
                
                # Should create trade
                import json
                with open(trades_file) as f:
                    trades = json.load(f)
                
                assert len(trades) == 1
                assert trades[0]["action"] == "buy"
    
    def test_sell_executes_correctly(self, tmp_path):
        """Test that SELL actions still work correctly."""
        trades_file = tmp_path / "trades.json"
        trades_file.write_text('[]')
        
        # Need existing position to sell (with correct structure)
        holdings_file = tmp_path / "holdings.json"
        holdings_file.write_text('{"BTCUSD": {"amount": 0.05, "avg_price": 99000.0, "cost_basis": 4950.0}}')
        
        with patch('app.logic.paper_trader.TRADES_FILE', trades_file):
            with patch('app.logic.paper_trader.HOLDINGS_FILE', holdings_file):
                from app.logic.paper_trader import PaperTrader
                
                trader = PaperTrader()
                
                result = trader.execute_trade(
                    symbol="BTCUSD",
                    action="SELL",
                    price=100000.0,
                    balance=10000.0,
                    reason="Strong sell signal",
                    amount=0.01
                )
                
                assert result["success"] == True
                assert result["action"] == "SELL"
                
                # Should create trade
                import json
                with open(trades_file) as f:
                    trades = json.load(f)
                
                assert len(trades) == 1
                assert trades[0]["action"] == "sell"
    
    def test_action_case_insensitive(self, tmp_path):
        """Test that action strings are case-insensitive."""
        trades_file = tmp_path / "trades.json"
        trades_file.write_text('[]')
        
        holdings_file = tmp_path / "holdings.json"
        holdings_file.write_text('{}')
        
        with patch('app.logic.paper_trader.TRADES_FILE', trades_file):
            with patch('app.logic.paper_trader.HOLDINGS_FILE', holdings_file):
                from app.logic.paper_trader import PaperTrader
                
                trader = PaperTrader()
                
                # Test lowercase
                trader.execute_trade("BTCUSD", "hold", 100000.0, 10000.0, "test", 0.01)
                
                # Test uppercase
                trader.execute_trade("BTCUSD", "HOLD", 100000.0, 10000.0, "test", 0.01)
                
                # Test mixed
                trader.execute_trade("BTCUSD", "Hold", 100000.0, 10000.0, "test", 0.01)
                
                # None should create trades
                import json
                with open(trades_file) as f:
                    trades = json.load(f)
                
                assert len(trades) == 0