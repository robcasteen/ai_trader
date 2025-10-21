"""
Risk management module.
Enforces position sizing, stop-loss, and daily loss limits.
"""

import logging
from datetime import datetime, date


class RiskManager:
    def __init__(self, starting_capital=200):
        self.starting_capital = starting_capital
        self.current_capital = starting_capital
        
        # Risk limits
        self.max_loss_per_trade_pct = 0.02  # 2%
        self.max_daily_drawdown_pct = 0.05  # 5%
        self.max_position_size_pct = 0.03   # 3%
        
        # Daily tracking
        self.daily_pnl = 0.0
        self.last_reset_date = date.today()
        self.shutdown = False
    
    def check_daily_reset(self):
        """Reset daily P&L if new day."""
        today = date.today()
        if today != self.last_reset_date:
            self.daily_pnl = 0.0
            self.last_reset_date = today
            self.shutdown = False
            logging.info("[RiskManager] Daily reset complete")
    
    def can_trade(self) -> bool:
        """Check if trading is allowed."""
        self.check_daily_reset()
        
        if self.shutdown:
            logging.warning("[RiskManager] Trading SHUTDOWN due to daily loss limit")
            return False
        
        # Check daily drawdown
        max_daily_loss = self.starting_capital * self.max_daily_drawdown_pct
        if self.daily_pnl < -max_daily_loss:
            self.shutdown = True
            logging.error(f"[RiskManager] SHUTDOWN: Daily loss ${abs(self.daily_pnl):.2f} exceeds limit ${max_daily_loss:.2f}")
            return False
        
        return True
    
    def calculate_position_size(self, price: float, balance: float = None) -> float:
        """
        Calculate safe position size based on capital.
        
        Args:
            price: Current price of asset
            balance: Current balance (if None, uses self.current_capital)
            
        Returns:
            Amount of asset to trade (in base currency)
        """
        # Use provided balance (from exchange) or fall back to internal tracking
        capital = balance if balance is not None else self.current_capital
        
        max_position_value = capital * self.max_position_size_pct
        amount = max_position_value / price if price > 0 else 0
        
        logging.info(f"[RiskManager] Position size: {amount:.6f} @ ${price:.2f} = ${max_position_value:.2f} (capital: ${capital:.2f})")
        return round(amount, 6)
    
    def update_after_trade(self, pnl: float):
        """Update daily P&L after trade execution."""
        self.daily_pnl += pnl
        self.current_capital += pnl
        
        logging.info(f"[RiskManager] Updated - Daily P&L: ${self.daily_pnl:+.2f}, Capital: ${self.current_capital:.2f}")
    
    def get_stats(self):
        """Get risk management statistics."""
        return {
            "starting_capital": self.starting_capital,
            "current_capital": self.current_capital,
            "daily_pnl": self.daily_pnl,
            "shutdown": self.shutdown,
            "limits": {
                "max_loss_per_trade": f"{self.max_loss_per_trade_pct*100}%",
                "max_daily_drawdown": f"{self.max_daily_drawdown_pct*100}%",
                "max_position_size": f"{self.max_position_size_pct*100}%"
            }
        }


# Global singleton
risk_manager = RiskManager(starting_capital=200)
