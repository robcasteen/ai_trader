"""
Integration test for balance usage in trade cycle.
"""
import pytest


def test_calculate_position_size_should_accept_balance_parameter():
    """
    Test that calculate_position_size can accept a balance parameter.
    
    This test verifies that when we call:
        amount = risk_manager.calculate_position_size(price, balance)
    
    It should work correctly and use the provided balance.
    """
    from app.risk_manager import risk_manager
    
    # Call with balance parameter
    price = 50000.0
    balance = 195.50
    
    amount = risk_manager.calculate_position_size(price, balance=balance)
    
    # Should calculate: 3% of 195.50 = 5.865
    # At $50k: 5.865 / 50000 = 0.00011730
    expected = (balance * 0.03) / price
    
    assert amount == pytest.approx(expected, abs=0.000001)


def test_main_should_pass_balance_to_calculate_position_size():
    """
    Manual verification test for main.py integration.
    
    This test documents what needs to be changed in main.py:
    
    BEFORE:
        amount = risk_manager.calculate_position_size(price)
    
    AFTER:
        amount = risk_manager.calculate_position_size(price, balance)
    
    This test will fail until main.py is updated.
    """
    # Read main.py and check if balance is being passed
    with open('src/app/main.py', 'r') as f:
        content = f.read()
    
    # Look for the pattern we want to see
    expected_pattern = "calculate_position_size(price, balance)"
    
    assert expected_pattern in content, (
        f"main.py should call: calculate_position_size(price, balance)\n"
        f"Currently it's missing the balance parameter"
    )
