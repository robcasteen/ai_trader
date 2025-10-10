"""
Strategy Manager - Orchestrates multiple trading strategies.
Combines signals from different strategies with configurable weights.
"""

from typing import List, Dict, Any, Tuple
import logging
from collections import defaultdict

from app.strategies.base_strategy import BaseStrategy
from app.strategies.sentiment_strategy import SentimentStrategy
from app.strategies.technical_strategy import TechnicalStrategy
from app.strategies.volume_strategy import VolumeStrategy
from app.strategy_signal_logger import StrategySignalLogger


class StrategyManager:
    """
    Manages multiple trading strategies and aggregates their signals.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize strategy manager.

        Args:
            config: Configuration dict with strategy settings
        """
        self.config = config or {}
        self.strategies: List[BaseStrategy] = []
        self.min_confidence = self.config.get("min_confidence", 0.5)
        self.aggregation_method = self.config.get("aggregation_method", "weighted_vote")

        # Initialize default strategies
        self._initialize_strategies()
        # Initialize signal logger
        self.signal_logger = StrategySignalLogger()
        logging.info(
            f"[StrategyManager] Initialized with {len(self.strategies)} strategies"
        )

    def _initialize_strategies(self):
        """Initialize and register all available strategies."""
        # Sentiment strategy (always enabled)
        sentiment = SentimentStrategy()
        self.strategies.append(sentiment)

        # Technical strategy (optional)
        if self.config.get("use_technical", True):
            technical = TechnicalStrategy()
            self.strategies.append(technical)

        # Volume strategy (optional)
        if self.config.get("use_volume", True):
            volume = VolumeStrategy()
            self.strategies.append(volume)

        # Apply custom weights if provided
        custom_weights = self.config.get("strategy_weights", {})
        for strategy in self.strategies:
            if strategy.name in custom_weights:
                strategy.weight = custom_weights[strategy.name]

    def add_strategy(self, strategy: BaseStrategy):
        """Add a custom strategy to the manager."""
        self.strategies.append(strategy)
        logging.info(f"[StrategyManager] Added strategy: {strategy.name}")

    def remove_strategy(self, strategy_name: str):
        """Remove a strategy by name."""
        self.strategies = [s for s in self.strategies if s.name != strategy_name]
        logging.info(f"[StrategyManager] Removed strategy: {strategy_name}")

    def enable_strategy(self, strategy_name: str):
        """Enable a specific strategy."""
        for strategy in self.strategies:
            if strategy.name == strategy_name:
                strategy.enable()
                logging.info(f"[StrategyManager] Enabled strategy: {strategy_name}")
                return True
        return False

    def disable_strategy(self, strategy_name: str):
        """Disable a specific strategy."""
        for strategy in self.strategies:
            if strategy.name == strategy_name:
                strategy.disable()
                logging.info(f"[StrategyManager] Disabled strategy: {strategy_name}")
                return True
        return False

    def get_signal(
        self, symbol: str, context: Dict[str, Any]
    ) -> Tuple[str, float, str]:
        """
        Get aggregated trading signal from all enabled strategies.

        Args:
            symbol: Trading pair (e.g., "BTC/USD")
            context: Context data containing:
                - headlines: List of news headlines
                - price: Current price
                - volume: Current volume
                - price_history: Historical prices
                - volume_history: Historical volumes

        Returns:
            Tuple of (signal, confidence, reason)
            - signal: "BUY", "SELL", or "HOLD"
            - confidence: 0.0 to 1.0
            - reason: Detailed explanation
        """
        if not self.strategies:
            return "HOLD", 0.0, "No strategies available"

        # Collect signals from all enabled strategies
        strategy_results = []

        for strategy in self.strategies:
            if not strategy.enabled:
                continue

            try:
                signal, confidence, reason = strategy.get_signal(symbol, context)
                strategy_results.append(
                    {
                        "strategy": strategy.name,
                        "signal": signal,
                        "confidence": confidence,
                        "reason": reason,
                        "weight": strategy.weight,
                    }
                )
                logging.info(
                    f"[{strategy.name}] {symbol}: {signal} (conf: {confidence:.2f}) - {reason}"
                )
            except Exception as e:
                logging.error(
                    f"[{strategy.name}] Error getting signal for {symbol}: {e}"
                )
                continue

        if not strategy_results:
            return "HOLD", 0.0, "No strategies produced signals"

        # Aggregate signals
        if self.aggregation_method == "weighted_vote":
            final_signal, final_confidence, final_reason = (
                self._weighted_vote_aggregation(strategy_results)
            )
        elif self.aggregation_method == "highest_confidence":
            final_signal, final_confidence, final_reason = (
                self._highest_confidence_aggregation(strategy_results)
            )
        elif self.aggregation_method == "unanimous":
            final_signal, final_confidence, final_reason = self._unanimous_aggregation(
                strategy_results
            )
        else:
            final_signal, final_confidence, final_reason = (
                self._weighted_vote_aggregation(strategy_results)
            )

        logging.info(
            f"[StrategyManager] Final signal for {symbol}: {final_signal} (conf: {final_confidence:.2f})"
        )

        # Log signal details for analysis (BEFORE confidence check)
        current_price = context.get("price", 0.0)
        if current_price > 0 and strategy_results:
            try:
                # Convert strategy_results to the format expected by logger
                strategy_details = {}
                for result in strategy_results:
                    strategy_details[result["strategy"]] = {
                        "signal": result["signal"],
                        "confidence": result["confidence"],
                        "reason": result["reason"],
                        "weight": result["weight"],
                        "enabled": True,
                    }

                self.signal_logger.log_decision(
                    symbol=symbol,
                    price=current_price,
                    final_signal=final_signal,
                    final_confidence=final_confidence,
                    strategy_signals=strategy_details,
                    aggregation_method=self.aggregation_method,
                    metadata={
                        "min_confidence": self.min_confidence,
                        "num_strategies": len(strategy_results),
                    },
                )
            except Exception as e:
                # Never let logging errors crash trading
                logging.warning(f"⚠️  Signal logging failed: {e}")

        # Apply minimum confidence threshold
        if final_confidence < self.min_confidence:
            logging.info(
                f"[StrategyManager] Confidence {final_confidence:.2f} below threshold {self.min_confidence}, converting to HOLD"
            )
            return "HOLD", final_confidence, f"Low confidence: {final_reason}"

        return final_signal, final_confidence, final_reason

    def _weighted_vote_aggregation(self, results: List[Dict]) -> Tuple[str, float, str]:
        """
        Aggregate signals using weighted voting.
        Each strategy's signal is weighted by its confidence and strategy weight.
        """
        scores = defaultdict(float)
        reasons_by_signal = defaultdict(list)

        total_weight = 0

        for result in results:
            signal = result["signal"]
            confidence = result["confidence"]
            weight = result["weight"]
            weighted_score = confidence * weight

            scores[signal] += weighted_score
            total_weight += weight
            reasons_by_signal[signal].append(
                f"{result['strategy']}: {result['reason']}"
            )

        # Find winning signal
        if not scores:
            return "HOLD", 0.0, "No valid signals"

        winning_signal = max(scores.items(), key=lambda x: x[1])
        signal = winning_signal[0]
        raw_score = winning_signal[1]

        # Normalize confidence
        confidence = min(raw_score / total_weight, 1.0) if total_weight > 0 else 0.0

        # Build reason
        reason = (
            f"{signal} signal from {len(reasons_by_signal[signal])} strategies: "
            + "; ".join(reasons_by_signal[signal][:2])
        )

        return signal, confidence, reason

    def _highest_confidence_aggregation(
        self, results: List[Dict]
    ) -> Tuple[str, float, str]:
        """
        Use the signal with the highest confidence score.
        Useful when you trust one strategy over others.
        """
        if not results:
            return "HOLD", 0.0, "No signals"

        best_result = max(results, key=lambda x: x["confidence"] * x["weight"])

        return (
            best_result["signal"],
            best_result["confidence"],
            f"Highest confidence from {best_result['strategy']}: {best_result['reason']}",
        )

    def _unanimous_aggregation(self, results: List[Dict]) -> Tuple[str, float, str]:
        """
        Only give BUY/SELL if all strategies agree.
        Very conservative approach.
        """
        if not results:
            return "HOLD", 0.0, "No signals"

        signals = [r["signal"] for r in results]

        # Check if all signals are the same
        if len(set(signals)) == 1:
            # All agree
            avg_confidence = sum(r["confidence"] for r in results) / len(results)
            all_reasons = [f"{r['strategy']}: {r['reason']}" for r in results]
            reason = "All strategies agree: " + "; ".join(all_reasons[:2])
            return signals[0], avg_confidence, reason
        else:
            # Disagreement - default to HOLD
            return "HOLD", 0.3, f"Strategies disagree: {', '.join(signals)}"

    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get summary of all strategies and their status."""
        return {
            "total_strategies": len(self.strategies),
            "enabled_strategies": len([s for s in self.strategies if s.enabled]),
            "strategies": [
                {"name": s.name, "enabled": s.enabled, "weight": s.weight}
                for s in self.strategies
            ],
            "config": {
                "min_confidence": self.min_confidence,
                "aggregation_method": self.aggregation_method,
            },
        }

    def update_config(self, new_config: Dict[str, Any]):
        """Update strategy manager configuration."""
        self.config.update(new_config)

        if "min_confidence" in new_config:
            self.min_confidence = new_config["min_confidence"]

        if "aggregation_method" in new_config:
            self.aggregation_method = new_config["aggregation_method"]

        # Update strategy weights
        if "strategy_weights" in new_config:
            for strategy in self.strategies:
                if strategy.name in new_config["strategy_weights"]:
                    strategy.weight = new_config["strategy_weights"][strategy.name]

        logging.info(f"[StrategyManager] Configuration updated")
