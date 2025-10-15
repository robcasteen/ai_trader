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
