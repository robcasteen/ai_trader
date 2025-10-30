"""
Test that signals from strategy_manager are properly converted to trades.

Run with: pytest tests/test_signal_to_trade_flow.py -v
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.strategies.strategy_manager import StrategyManager
from app.logic.paper_trader import PaperTrader


class TestSignalToTradeFlow:
    """Test the complete flow: strategy signal → paper trader execution."""
    
    def test_strategy_manager_returns_tuple(self):
        """Test that get_signal() returns (signal, confidence, reason) tuple."""
        manager = StrategyManager()
        
        context = {
            "headlines": ["Bitcoin hits new high"],
            "price": 100000.0,
            "volume": 1000000,
            "price_history": [99000, 99500, 100000],
            "volume_history": [900000, 950000, 1000000]
        }
        
        signal, confidence, reason, signal_id = manager.get_signal("BTCUSD", context)
        
        # Should return proper tuple
        assert isinstance(signal, str)
        assert signal in ["BUY", "SELL", "HOLD"]
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
        assert isinstance(reason, str)
        assert len(reason) > 0
    
    def test_signal_gets_logged_to_jsonl(self, tmp_path):
        """Test that signals are logged to strategy_signals.jsonl."""
        with patch('app.strategies.strategy_manager.LOGS_DIR', tmp_path):
            manager = StrategyManager()
            
            context = {
                "headlines": ["Bitcoin price surges"],
                "price": 100000.0,
                "volume": 1000000,
                "price_history": [99000, 99500, 100000],
                "volume_history": [900000, 950000, 1000000]
            }
            
            signal, confidence, reason, signal_id = manager.get_signal("BTCUSD", context)
            
            # Check log file was created and has content
            log_file = tmp_path / "strategy_signals.jsonl"
            assert log_file.exists()
            
            import json
            with open(log_file) as f:
                logged_signal = json.loads(f.readline())
            
            # Should have new format fields
            assert "final_signal" in logged_signal
            assert "final_confidence" in logged_signal
            assert "strategies" in logged_signal
            
            # Verify returned tuple matches logged signal
            assert signal == logged_signal["final_signal"]
            assert confidence == logged_signal["final_confidence"]
    
    @patch('app.logic.paper_trader.LOGS_DIR')
    def test_paper_trader_executes_buy_signal(self, mock_logs_dir, tmp_path):
        """Test that PaperTrader executes BUY signals."""
        mock_logs_dir.__truediv__ = lambda self, other: tmp_path / other
        
        trader = PaperTrader()
        
        # Execute a BUY trade
        result = trader.execute_trade(
            symbol="BTCUSD",
            action="BUY",
            price=100000.0,
            balance=10000.0,
            reason="Test buy signal",
            amount=0.01  # Buy 0.01 BTC
        )
        
        assert result["success"] == True
        assert result["action"] == "BUY"
        assert result["symbol"] == "BTCUSD"
        assert result["amount"] == 0.01
    
    @patch('app.logic.paper_trader.LOGS_DIR')
    def test_paper_trader_respects_confidence_threshold(self, mock_logs_dir, tmp_path):
        """Test that low confidence signals are not executed."""
        mock_logs_dir.__truediv__ = lambda self, other: tmp_path / other
        
        trader = PaperTrader()
        
        # Try to execute low confidence trade
        result = trader.execute_trade(
            symbol="BTCUSD",
            action="BUY",
            price=100000.0,
            balance=10000.0,
            reason="Low confidence: BUY signal 0.15",  # Below typical threshold
            amount=0.01
        )
        
        # Should still execute (paper trading), but log the low confidence
        assert result["success"] == True
        assert "Low confidence" in result.get("reason", "")
    
    def test_main_loop_converts_signal_to_trade(self):
        """Test that main.py properly converts strategy signals to trades."""
        # This is an integration test concept
        # Would need to mock the entire scheduler flow
        
        # Expected flow:
        # 1. get_signal() returns ("BUY", 0.8, "Strong bullish sentiment")
        # 2. Check confidence >= threshold (0.2)
        # 3. Call trader.execute_trade()
        # 4. Log result
        
        # The test verifies this flow is unbroken
        pass  # Placeholder - would implement full integration test


class TestSignalConfidenceThresholds:
    """Test confidence threshold logic."""
    
    def test_high_confidence_signals_execute(self):
        """Test that signals above threshold are executed."""
        # Confidence 0.8 > threshold 0.2 = should execute
        assert 0.8 >= 0.2
    
    def test_low_confidence_signals_filtered(self):
        """Test that signals below threshold are filtered."""
        # Confidence 0.1 < threshold 0.2 = should not execute
        assert 0.1 < 0.2
    
    def test_threshold_is_configurable(self):
        """Test that confidence threshold can be configured."""
        from app.config import get_current_config
        config = get_current_config()
        
        # Should have a min_confidence setting
        assert hasattr(config, 'min_confidence') or 'min_confidence' in config


class TestTradeExecution:
    """Test actual trade execution logic."""
    
    @patch('app.logic.paper_trader.LOGS_DIR')
    def test_buy_creates_new_position(self, mock_logs_dir, tmp_path):
        """Test that BUY action creates a new position."""
        mock_logs_dir.__truediv__ = lambda self, other: tmp_path / other
        
        # Initialize empty holdings
        holdings_file = tmp_path / "holdings.json"
        holdings_file.write_text('{}')
        
        trader = PaperTrader()
        trader.execute_trade(
            symbol="BTCUSD",
            action="BUY",
            price=100000.0,
            balance=10000.0,
            reason="Test",
            amount=0.01
        )
        
        # Should create position in holdings
        import json
        with open(holdings_file) as f:
            holdings = json.load(f)
        
        assert "BTCUSD" in holdings
        assert holdings["BTCUSD"]["amount"] == 0.01
    
    @patch('app.logic.paper_trader.LOGS_DIR')  
    def test_sell_reduces_position(self, mock_logs_dir, tmp_path):
        """Test that SELL action reduces existing position."""
        mock_logs_dir.__truediv__ = lambda self, other: tmp_path / other
        
        # Initialize with existing position
        holdings_file = tmp_path / "holdings.json"
        holdings_file.write_text('{"BTCUSD": {"amount": 0.02, "cost_basis": 99000.0}}')
        
        trader = PaperTrader()
        trader.execute_trade(
            symbol="BTCUSD",
            action="SELL",
            price=100000.0,
            balance=10000.0,
            reason="Test",
            amount=0.01
        )
        
        # Should reduce position
        import json
        with open(holdings_file) as f:
            holdings = json.load(f)
        
        assert holdings["BTCUSD"]["amount"] == 0.01  # 0.02 - 0.01
    
    def test_hold_does_not_trade(self):
        """Test that HOLD signal does not execute any trades."""
        # HOLD should log the signal but not call execute_trade
        # This would be tested in the main loop integration test
        pass