"""
Base strategy class for all trading strategies.
All strategies must implement the get_signal method.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""
    
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.weight = 1.0  # Weight for signal aggregation
    
    @abstractmethod
    def get_signal(self, symbol: str, context: Dict[str, Any]) -> Tuple[str, float, str]:
        """
        Get trading signal for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USD")
            context: Dictionary with market data, news, etc.
        
        Returns:
            Tuple of (signal, confidence, reason)
            - signal: "BUY", "SELL", or "HOLD"
            - confidence: 0.0 to 1.0
            - reason: Explanation for the signal
        """
        pass
    
    def enable(self):
        """Enable this strategy."""
        self.enabled = True
    
    def disable(self):
        """Disable this strategy."""
        self.enabled = False
