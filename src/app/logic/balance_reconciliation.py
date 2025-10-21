"""
Balance reconciliation module.

Tracks both exchange balance (ground truth) and calculated balance (from trades)
to measure slippage caused by fees and market conditions.
"""
import logging
from typing import Dict, Any


class BalanceReconciliation:
    """Track exchange vs calculated balance and measure slippage."""
    
    def __init__(self, starting_balance: float):
        """
        Initialize balance reconciliation.
        
        Args:
            starting_balance: Initial capital in USD
        """
        self.starting_balance = starting_balance
        self.exchange_balance = starting_balance  # Ground truth from exchange
        self.calculated_balance = starting_balance  # Derived from trades
        
    @property
    def slippage(self) -> float:
        """
        Calculate slippage (difference between exchange and calculated balance).
        
        Returns:
            Slippage in USD (negative = loss, positive = gain)
        """
        return self.exchange_balance - self.calculated_balance
    
    def update_exchange_balance(self, balance: float):
        """
        Update balance from exchange API.
        
        Args:
            balance: Current balance from exchange
        """
        old_balance = self.exchange_balance
        self.exchange_balance = balance
        
        logging.info(
            f"[BalanceRecon] Exchange balance updated: "
            f"${old_balance:.2f} → ${balance:.2f}"
        )
    
    def record_trade(self, cost: float, action: str):
        """
        Record a trade and update calculated balance.
        
        Args:
            cost: Net cost/proceeds of trade (positive = cost, negative = proceeds)
            action: "buy" or "sell"
        """
        if action.lower() == "buy":
            self.calculated_balance -= cost
        else:  # sell
            self.calculated_balance += cost
        
        logging.info(
            f"[BalanceRecon] Trade recorded: {action.upper()} "
            f"${cost:.2f}, calculated balance: ${self.calculated_balance:.2f}"
        )
    
    def get_balance_for_trading(self) -> float:
        """
        Get the balance to use for position sizing.
        
        Returns:
            Exchange balance (ground truth)
        """
        return self.exchange_balance
    
    def get_reconciliation_report(self) -> Dict[str, Any]:
        """
        Generate reconciliation report.
        
        Returns:
            Dictionary with balance details and slippage
        """
        slippage_pct = (self.slippage / self.starting_balance * 100) if self.starting_balance > 0 else 0.0
        
        return {
            "starting_balance": self.starting_balance,
            "exchange_balance": self.exchange_balance,
            "calculated_balance": self.calculated_balance,
            "slippage": self.slippage,
            "slippage_percent": slippage_pct,
        }
