"""Tests for RiskManager."""
import pytest
from datetime import date
from app.risk_manager import RiskManager

def test_initialization():
    rm = RiskManager(starting_capital=200)
    assert rm.starting_capital == 200
    assert rm.current_capital == 200

def test_position_size_calculation():
    rm = RiskManager(starting_capital=200)
    # 3% of $200 = $6, at $50000/BTC = 0.00012 BTC
    amount = rm.calculate_position_size(50000)
    assert amount == 0.00012

def test_daily_loss_limit_shutdown():
    rm = RiskManager(starting_capital=200)
    rm.update_after_trade(-11)  # Lose $11 (> 5% = $10)
    assert rm.can_trade() is False
    assert rm.shutdown is True


class TestPositionSizingWithBalance:
    """Test position sizing with provided balance."""
    
    def test_position_size_uses_provided_balance(self):
        """Test that position sizing uses provided balance instead of internal capital."""
        manager = RiskManager(starting_capital=200)
        
        # Provide a different balance (e.g., from exchange)
        exchange_balance = 195.50
        price = 50000.0
        
        amount = manager.calculate_position_size(price, balance=exchange_balance)
        
        # Should use exchange_balance: 3% of 195.50 = 5.865
        # At $50k per BTC: 5.865 / 50000 = 0.00011730
        expected_amount = (exchange_balance * 0.03) / price
        assert amount == pytest.approx(expected_amount, abs=0.000001)
    
    def test_position_size_falls_back_to_internal_capital(self):
        """Test that position sizing falls back to internal capital if no balance provided."""
        manager = RiskManager(starting_capital=200)
        price = 50000.0
        
        amount = manager.calculate_position_size(price)  # No balance param
        
        # Should use internal current_capital: 3% of 200 = 6
        # At $50k per BTC: 6 / 50000 = 0.00012
        expected_amount = (200 * 0.03) / price
        assert amount == pytest.approx(expected_amount, abs=0.000001)
    
    def test_position_size_with_higher_exchange_balance(self):
        """Test position sizing with higher exchange balance."""
        manager = RiskManager(starting_capital=200)
        
        # Exchange has more than we thought
        exchange_balance = 100000.0
        price = 50000.0
        
        amount = manager.calculate_position_size(price, balance=exchange_balance)
        
        # Should use exchange_balance: 3% of 100k = 3000
        # At $50k per BTC: 3000 / 50000 = 0.06
        expected_amount = (exchange_balance * 0.03) / price
        assert amount == pytest.approx(expected_amount, abs=0.000001)
