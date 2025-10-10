"""
Sentiment-based strategy using GPT analysis of news headlines.
"""

from typing import Tuple, Dict, Any
from app.strategies.base_strategy import BaseStrategy
from app.logic.sentiment import SentimentSignal


class SentimentStrategy(BaseStrategy):
    """Strategy based on news sentiment analysis."""
    
    def __init__(self):
        super().__init__("sentiment")
        self.sentiment_model = SentimentSignal()
        self.weight = 1.0
    
    def get_signal(self, symbol: str, context: Dict[str, Any]) -> Tuple[str, float, str]:
        """
        Get signal based on news sentiment.
        
        Args:
            symbol: Trading pair
            context: Must contain 'headlines' key with list of news headlines
        
        Returns:
            (signal, confidence, reason)
        """
        headlines = context.get('headlines', [])
        
        if not headlines:
            return "HOLD", 0.0, "No news headlines available"
        
        # Get sentiment signal
        if len(headlines) == 1:
            signal, reason = self.sentiment_model.get_signal(headlines[0], symbol)
        else:
            signal, reason = self.sentiment_model.get_signals(headlines, symbol)
        
        # Convert signal to confidence
        confidence = self._signal_to_confidence(signal, reason)
        
        return signal, confidence, f"Sentiment: {reason}"
    
    def _signal_to_confidence(self, signal: str, reason: str) -> float:
        """Convert sentiment signal to confidence score."""
        # Strong keywords indicate high confidence
        strong_positive = ['surge', 'soar', 'record high', 'bullish', 'rally']
        strong_negative = ['plunge', 'collapse', 'crash', 'bearish', 'ban']
        
        reason_lower = reason.lower()
        
        if signal == "BUY":
            if any(word in reason_lower for word in strong_positive):
                return 0.8
            return 0.6
        elif signal == "SELL":
            if any(word in reason_lower for word in strong_negative):
                return 0.8
            return 0.6
        else:  # HOLD
            return 0.3
