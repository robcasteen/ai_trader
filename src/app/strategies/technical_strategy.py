"""
Technical analysis strategy using price-based indicators.
"""

from typing import Tuple, Dict, Any, List
from app.strategies.base_strategy import BaseStrategy


class TechnicalStrategy(BaseStrategy):
    """Strategy based on technical indicators like RSI, moving averages."""
    
    def __init__(self):
        super().__init__("technical")
        self.weight = 1.0
    
    def get_signal(self, symbol: str, context: Dict[str, Any]) -> Tuple[str, float, str]:
        """
        Get signal based on technical indicators.
        
        Args:
            symbol: Trading pair
            context: Must contain 'price' and optionally 'price_history'
        
        Returns:
            (signal, confidence, reason)
        """
        current_price = context.get('price', 0)
        price_history = context.get('price_history', [])
        
        if not current_price:
            return "HOLD", 0.0, "No price data available"
        
        signals = []
        reasons = []
        
        # Simple Moving Average signal
        if len(price_history) >= 20:
            sma_signal = self._sma_signal(current_price, price_history)
            signals.append(sma_signal)
            reasons.append(f"SMA: {sma_signal[0]}")
        
        # RSI signal (if we have enough data)
        if len(price_history) >= 14:
            rsi_signal = self._rsi_signal(price_history)
            signals.append(rsi_signal)
            reasons.append(f"RSI: {rsi_signal[0]}")
        
        # Momentum signal
        if len(price_history) >= 5:
            momentum_signal = self._momentum_signal(current_price, price_history)
            signals.append(momentum_signal)
            reasons.append(f"Momentum: {momentum_signal[0]}")
        
        if not signals:
            return "HOLD", 0.3, "Insufficient price history for technical analysis"
        
        # Aggregate signals
        final_signal, confidence = self._aggregate_signals(signals)
        reason = "Technical: " + ", ".join(reasons)
        
        return final_signal, confidence, reason
    
    def _sma_signal(self, current_price: float, history: List[float]) -> Tuple[str, float]:
        """Simple Moving Average crossover signal."""
        sma_20 = sum(history[-20:]) / 20
        sma_50 = sum(history[-50:]) / 50 if len(history) >= 50 else sma_20
        
        if current_price > sma_20 > sma_50:
            return "BUY", 0.7
        elif current_price < sma_20 < sma_50:
            return "SELL", 0.7
        else:
            return "HOLD", 0.3
    
    def _rsi_signal(self, history: List[float]) -> Tuple[str, float]:
        """Relative Strength Index signal."""
        if len(history) < 14:
            return "HOLD", 0.0
        
        # Calculate RSI
        changes = [history[i] - history[i-1] for i in range(1, len(history))]
        gains = [max(0, change) for change in changes[-14:]]
        losses = [abs(min(0, change)) for change in changes[-14:]]
        
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # RSI signals
        if rsi < 30:
            return "BUY", 0.8  # Oversold
        elif rsi > 70:
            return "SELL", 0.8  # Overbought
        else:
            return "HOLD", 0.4
    
    def _momentum_signal(self, current_price: float, history: List[float]) -> Tuple[str, float]:
        """Price momentum signal."""
        if len(history) < 5:
            return "HOLD", 0.0
        
        price_5_ago = history[-5]
        change_pct = ((current_price - price_5_ago) / price_5_ago) * 100
        
        if change_pct > 3:
            return "BUY", 0.6  # Strong upward momentum
        elif change_pct < -3:
            return "SELL", 0.6  # Strong downward momentum
        else:
            return "HOLD", 0.4
    
    def _aggregate_signals(self, signals: List[Tuple[str, float]]) -> Tuple[str, float]:
        """
        Aggregate multiple technical signals.
        
        When BUY and SELL signals are closely matched, favor HOLD to avoid
        false signals during consolidation or when trend and mean-reversion
        indicators conflict.
        """
        if not signals:
            return "HOLD", 0.0
        
        buy_score = sum(conf for sig, conf in signals if sig == "BUY")
        sell_score = sum(conf for sig, conf in signals if sig == "SELL")
        hold_score = sum(conf for sig, conf in signals if sig == "HOLD")
        
        # If BUY and SELL scores are close (within 0.2), favor HOLD to avoid whipsaws
        if abs(buy_score - sell_score) < 0.2 and max(buy_score, sell_score) > 0:
            return "HOLD", min(hold_score / len(signals) if hold_score > 0 else 0.4, 1.0)
        
        # Otherwise, use highest total score
        max_score = max(buy_score, sell_score, hold_score)
        
        if max_score == buy_score and buy_score > 0:
            return "BUY", min(buy_score / len(signals), 1.0)
        elif max_score == sell_score and sell_score > 0:
            return "SELL", min(sell_score / len(signals), 1.0)
        else:
            return "HOLD", min(hold_score / len(signals) if hold_score > 0 else 0.3, 1.0)