"""
Volume-based strategy analyzing trading volume patterns.
High volume with price movement can indicate strong trends.
"""

from typing import Tuple, Dict, Any, List
from app.strategies.base_strategy import BaseStrategy


class VolumeStrategy(BaseStrategy):
    """Strategy based on trading volume analysis."""

    def __init__(self):
        super().__init__("volume")
        self.weight = 0.8  # Slightly lower weight than sentiment/technical

    def get_signal(
        self, symbol: str, context: Dict[str, Any]
    ) -> Tuple[str, float, str]:
        """
        Get signal based on volume analysis.

        Args:
            symbol: Trading pair
            context: Must contain 'volume', 'price', and optionally 'volume_history'

        Returns:
            (signal, confidence, reason)
        """
        current_volume = context.get("volume", 0)
        current_price = context.get("price", 0)
        volume_history = context.get("volume_history", [])
        price_history = context.get("price_history", [])

        if not current_volume or not current_price:
            return "HOLD", 0.0, "No volume data available"

        signals = []
        reasons = []

        # Volume spike signal
        if len(volume_history) >= 20:
            spike_signal = self._volume_spike_signal(current_volume, volume_history)
            signals.append(spike_signal)
            reasons.append(spike_signal[2])

        # Volume-price divergence
        if len(volume_history) >= 10 and len(price_history) >= 10:
            divergence_signal = self._volume_price_divergence(
                current_price, current_volume, price_history, volume_history
            )
            signals.append(divergence_signal)
            reasons.append(divergence_signal[2])

        # On-Balance Volume (OBV)
        if len(price_history) >= 5 and len(volume_history) >= 5:
            obv_signal = self._obv_signal(price_history, volume_history)
            signals.append(obv_signal)
            reasons.append(obv_signal[2])

        if not signals:
            return "HOLD", 0.3, "Insufficient volume history for analysis"

        # Aggregate signals
        final_signal, confidence = self._aggregate_signals(signals)
        reason = "Volume: " + " | ".join([s[2] for s in signals])

        return final_signal, confidence, reason

    def _volume_spike_signal(
        self, current_volume: float, history: List[float]
    ) -> Tuple[str, float, str]:
        """
        Detect volume spikes that may indicate strong moves.
        High volume with price increase = bullish
        High volume with price decrease = bearish
        """
        avg_volume = sum(history[-20:]) / 20
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        if volume_ratio > 2.0:
            # Significant volume spike - need price context to determine direction
            return "HOLD", 0.7, f"Volume spike {volume_ratio:.1f}x avg"
        elif volume_ratio > 1.5:
            return "HOLD", 0.5, f"Elevated volume {volume_ratio:.1f}x avg"
        else:
            return "HOLD", 0.3, "Normal volume"

    def _volume_price_divergence(
        self,
        current_price: float,
        current_volume: float,
        price_history: List[float],
        volume_history: List[float],
    ) -> Tuple[str, float, str]:
        """
        Detect volume-price divergence patterns.
        Price up + Volume up = Strong bullish (BUY)
        Price down + Volume up = Strong bearish (SELL)
        Price up + Volume down = Weak bullish (HOLD)
        Price down + Volume down = Weak bearish (HOLD)
        """
        # Calculate recent trends
        price_change = ((current_price - price_history[-5]) / price_history[-5]) * 100
        avg_recent_volume = sum(volume_history[-5:]) / 5
        avg_older_volume = sum(volume_history[-10:-5]) / 5

        volume_increasing = avg_recent_volume > avg_older_volume * 1.2
        volume_decreasing = avg_recent_volume < avg_older_volume * 0.8

        price_up = price_change > 2
        price_down = price_change < -2

        if price_up and volume_increasing:
            return "BUY", 0.8, "Price↑ + Volume↑ (strong bullish)"
        elif price_down and volume_increasing:
            return "SELL", 0.8, "Price↓ + Volume↑ (strong bearish)"
        elif price_up and volume_decreasing:
            return "HOLD", 0.4, "Price↑ + Volume↓ (weak trend)"
        elif price_down and volume_decreasing:
            return "HOLD", 0.4, "Price↓ + Volume↓ (weak trend)"
        else:
            return "HOLD", 0.3, "No clear volume-price pattern"

    def _obv_signal(
        self, price_history: List[float], volume_history: List[float]
    ) -> Tuple[str, float, str]:
        """
        On-Balance Volume indicator.
        OBV rising = accumulation (bullish)
        OBV falling = distribution (bearish)
        """
        if len(price_history) < 5 or len(volume_history) < 5:
            return "HOLD", 0.0, "Insufficient OBV data"

        # Calculate OBV for all available periods
        obv_values = [0]
        for i in range(1, min(len(price_history), len(volume_history))):
            if price_history[i] > price_history[i - 1]:
                obv_values.append(obv_values[-1] + volume_history[i])
            elif price_history[i] < price_history[i - 1]:
                obv_values.append(obv_values[-1] - volume_history[i])
            else:
                obv_values.append(obv_values[-1])

        # Compare recent OBV trend (last 5 periods)
        if len(obv_values) < 5:
            return "HOLD", 0.0, "Insufficient OBV data"

        recent_obv = obv_values[-5:]
        obv_start = recent_obv[0]
        obv_end = recent_obv[-1]

        # Calculate OBV trend
        if obv_end > obv_start * 1.05:  # OBV rising by >5%
            return "BUY", 0.6, "OBV rising (accumulation)"
        elif obv_end < obv_start * 0.95:  # OBV falling by >5%
            return "SELL", 0.6, "OBV falling (distribution)"
        else:
            return "HOLD", 0.3, "OBV neutral"

    def _aggregate_signals(
        self, signals: List[Tuple[str, float, str]]
    ) -> Tuple[str, float]:
        """Aggregate multiple volume signals."""
        buy_score = sum(conf for sig, conf, _ in signals if sig == "BUY")
        sell_score = sum(conf for sig, conf, _ in signals if sig == "SELL")
        hold_score = sum(conf for sig, conf, _ in signals if sig == "HOLD")

        max_score = max(buy_score, sell_score, hold_score)

        if max_score == buy_score and buy_score > 0:
            return "BUY", min(buy_score / len(signals), 1.0)
        elif max_score == sell_score and sell_score > 0:
            return "SELL", min(sell_score / len(signals), 1.0)
        else:
            return "HOLD", min(hold_score / len(signals), 1.0)
