"""
Unit tests for Notifier.

Tests cover:
- Notification sending with complete trade data
- Handling of incomplete/missing data
- Logging behavior
"""

import pytest
import logging
from unittest.mock import Mock, patch
from app.logic.notifier import Notifier


@pytest.fixture
def notifier():
    """Fixture providing a Notifier instance."""
    return Notifier()


@pytest.fixture
def caplog_info(caplog):
    """Fixture to capture INFO level logs."""
    caplog.set_level(logging.INFO)
    return caplog


class TestSendNotification:
    def test_send_complete_trade(self, notifier, caplog_info):
        """Test sending notification with complete trade data."""
        trade_result = {
            "symbol": "BTC/USD",
            "action": "BUY",
            "price": 50000.0,
            "reason": "Positive sentiment detected"
        }
        
        notifier.send(trade_result)
        
        # Verify log contains all expected information
        assert "BTC/USD" in caplog_info.text
        assert "BUY" in caplog_info.text
        assert "50000" in caplog_info.text
        assert "Positive sentiment detected" in caplog_info.text
        assert "[ALERT]" in caplog_info.text

    def test_send_sell_trade(self, notifier, caplog_info):
        """Test sending notification for sell trade."""
        trade_result = {
            "symbol": "ETH/USD",
            "action": "SELL",
            "price": 3000.0,
            "reason": "Negative news"
        }
        
        notifier.send(trade_result)
        
        assert "ETH/USD" in caplog_info.text
        assert "SELL" in caplog_info.text
        assert "3000" in caplog_info.text

    def test_send_hold_signal(self, notifier, caplog_info):
        """Test sending notification for hold signal."""
        trade_result = {
            "symbol": "SOL/USD",
            "action": "HOLD",
            "price": 100.0,
            "reason": "Mixed sentiment"
        }
        
        notifier.send(trade_result)
        
        assert "SOL/USD" in caplog_info.text
        assert "HOLD" in caplog_info.text


class TestMissingData:
    def test_send_none_trade_result(self, notifier, caplog_info):
        """Test handling of None trade result."""
        notifier.send(None)
        
        # Should return early, no log entries
        assert "[ALERT]" not in caplog_info.text

    def test_send_empty_dict(self, notifier, caplog_info):
        """Test handling of empty trade result."""
        notifier.send({})
        
        # Empty dict should return early without logging
        # This is correct behavior - no alert for empty trade
        assert "[ALERT]" not in caplog_info.text

    def test_send_missing_symbol(self, notifier, caplog_info):
        """Test trade result with missing symbol."""
        trade_result = {
            "action": "BUY",
            "price": 50000.0,
            "reason": "Test"
        }
        
        notifier.send(trade_result)
        
        assert "?" in caplog_info.text  # Default symbol
        assert "BUY" in caplog_info.text

    def test_send_missing_action(self, notifier, caplog_info):
        """Test trade result with missing action."""
        trade_result = {
            "symbol": "BTC/USD",
            "price": 50000.0,
            "reason": "Test"
        }
        
        notifier.send(trade_result)
        
        assert "BTC/USD" in caplog_info.text
        assert "HOLD" in caplog_info.text  # Default action

    def test_send_missing_price(self, notifier, caplog_info):
        """Test trade result with missing price."""
        trade_result = {
            "symbol": "BTC/USD",
            "action": "BUY",
            "reason": "Test"
        }
        
        notifier.send(trade_result)
        
        assert "0" in caplog_info.text  # Default price

    def test_send_missing_reason(self, notifier, caplog_info):
        """Test trade result with missing reason."""
        trade_result = {
            "symbol": "BTC/USD",
            "action": "BUY",
            "price": 50000.0
        }
        
        notifier.send(trade_result)
        
        assert "No reason" in caplog_info.text


class TestLoggingFormat:
    def test_log_level_is_info(self, notifier, caplog):
        """Test that notifications are logged at INFO level."""
        caplog.set_level(logging.INFO)
        
        trade_result = {
            "symbol": "BTC/USD",
            "action": "BUY",
            "price": 50000.0,
            "reason": "Test"
        }
        
        notifier.send(trade_result)
        
        # Check that at least one INFO log was created
        assert any(record.levelname == "INFO" for record in caplog.records)

    def test_alert_prefix_present(self, notifier, caplog_info):
        """Test that [ALERT] prefix is present in logs."""
        trade_result = {
            "symbol": "BTC/USD",
            "action": "BUY",
            "price": 50000.0,
            "reason": "Test"
        }
        
        notifier.send(trade_result)
        
        assert "[ALERT]" in caplog_info.text

    def test_price_at_symbol_format(self, notifier, caplog_info):
        """Test that log uses '@ price' format."""
        trade_result = {
            "symbol": "BTC/USD",
            "action": "BUY",
            "price": 50000.0,
            "reason": "Test"
        }
        
        notifier.send(trade_result)
        
        assert "@" in caplog_info.text
        assert "50000" in caplog_info.text


class TestMultipleNotifications:
    def test_send_multiple_notifications(self, notifier, caplog_info):
        """Test sending multiple notifications in sequence."""
        trades = [
            {"symbol": "BTC/USD", "action": "BUY", "price": 50000.0, "reason": "Buy signal"},
            {"symbol": "ETH/USD", "action": "SELL", "price": 3000.0, "reason": "Sell signal"},
            {"symbol": "SOL/USD", "action": "HOLD", "price": 100.0, "reason": "Hold signal"},
        ]
        
        for trade in trades:
            notifier.send(trade)
        
        # All trades should be logged
        assert "BTC/USD" in caplog_info.text
        assert "ETH/USD" in caplog_info.text
        assert "SOL/USD" in caplog_info.text
        assert caplog_info.text.count("[ALERT]") == 3