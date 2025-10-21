"""
Test balance reconciliation between exchange and calculated balances.
"""
import pytest
from app.logic.balance_reconciliation import BalanceReconciliation


class TestBalanceReconciliation:
    """Test balance tracking and slippage calculation."""
    
    def test_initialization(self):
        """Test that reconciliation initializes with starting balance."""
        recon = BalanceReconciliation(starting_balance=200.0)
        
        assert recon.starting_balance == 200.0
        assert recon.exchange_balance == 200.0
        assert recon.calculated_balance == 200.0
        assert recon.slippage == 0.0
    
    def test_update_exchange_balance(self):
        """Test updating balance from exchange."""
        recon = BalanceReconciliation(starting_balance=200.0)
        
        recon.update_exchange_balance(195.50)
        
        assert recon.exchange_balance == 195.50
        assert recon.calculated_balance == 200.0  # Unchanged
        assert recon.slippage == -4.50  # Lost $4.50 to fees/slippage
    
    def test_update_calculated_balance_from_trade(self):
        """Test updating calculated balance after a trade."""
        recon = BalanceReconciliation(starting_balance=200.0)
        
        # Simulate a trade: bought 0.01 BTC at $50k = $500 + $1.30 fee
        recon.record_trade(cost=501.30, action="buy")
        
        assert recon.calculated_balance == pytest.approx(200.0 - 501.30, abs=0.01)
    
    def test_slippage_calculation(self):
        """Test slippage calculation."""
        recon = BalanceReconciliation(starting_balance=200.0)
        
        # Execute trade: spend $50
        recon.record_trade(cost=50.0, action="buy")
        # Calculated balance now: 200 - 50 = 150
        
        # Update exchange balance (lost $0.50 to fees)
        recon.update_exchange_balance(149.50)
        
        # Exchange: 149.50
        # Calculated: 150.00
        # Slippage: 149.50 - 150.00 = -0.50
        assert recon.slippage == pytest.approx(-0.50, abs=0.01)
    
    def test_get_balance_for_position_sizing(self):
        """Test getting the correct balance for position sizing."""
        recon = BalanceReconciliation(starting_balance=200.0)
        recon.update_exchange_balance(195.50)
        
        # Should use exchange balance (ground truth)
        balance = recon.get_balance_for_trading()
        
        assert balance == 195.50
    
    def test_reconciliation_report(self):
        """Test generating reconciliation report."""
        recon = BalanceReconciliation(starting_balance=200.0)
        recon.update_exchange_balance(195.50)
        recon.record_trade(cost=2.0, action="buy")  # calculated becomes 198
        
        report = recon.get_reconciliation_report()
        
        assert report["exchange_balance"] == 195.50
        assert report["calculated_balance"] == 198.00
        assert report["slippage"] == -2.50
        assert report["slippage_percent"] == pytest.approx(-1.25, abs=0.01)
