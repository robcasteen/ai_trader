"""
Strategy Manager - Orchestrates multiple trading strategies.
Combines signals from different strategies with configurable weights.
"""

from typing import List, Dict, Any, Tuple, Optional
import logging
from collections import defaultdict

from app.strategies.base_strategy import BaseStrategy
from app.strategies.sentiment_strategy import SentimentStrategy
from app.strategies.technical_strategy import TechnicalStrategy
from app.strategies.volume_strategy import VolumeStrategy
from app.strategy_signal_logger import StrategySignalLogger
from app.utils.symbol_normalizer import normalize_symbol
from app.utils.symbol_normalizer import normalize_symbol


class StrategyManager:
    """
    Manages multiple trading strategies and aggregates their signals.
    """

    def __init__(self, config: Dict[str, Any] = None, db_session=None):
        """
        Initialize strategy manager.

        Args:
            config: Configuration dict with strategy settings
            db_session: Optional database session for loading strategy definitions
        """
        self.config = config or {}
        self.db_session = db_session
        self.strategies: List[BaseStrategy] = []
        self.min_confidence = self.config.get("min_confidence", 0.5)
        self.aggregation_method = self.config.get("aggregation_method", "weighted_vote")

        # Initialize strategies (from database if session provided, otherwise use defaults)
        self._initialize_strategies()
        # Initialize signal logger
        logs_dir = self.config.get("logs_dir", "data")
        self.signal_logger = StrategySignalLogger(data_dir=logs_dir)
        logging.info(f"[StrategyManager] Logging to {logs_dir}/strategy_signals.jsonl")

    def _initialize_strategies(self):
        """Initialize and register all available strategies from database or defaults."""
        # If database session provided, load strategies from database
        if self.db_session:
            self._load_strategies_from_database()
        else:
            # Fallback to hardcoded strategies (for backward compatibility)
            self._load_default_strategies()

    def _load_strategies_from_database(self):
        """Load strategies from database using StrategyDefinitionRepository."""
        try:
            from app.database.repositories import StrategyDefinitionRepository

            repo = StrategyDefinitionRepository(self.db_session)
            strategy_defs = repo.get_all_enabled()

            if not strategy_defs:
                logging.warning("[StrategyManager] No strategies found in database, using defaults")
                self._load_default_strategies()
                return

            # Map strategy names to their class implementations
            strategy_classes = {
                "sentiment": SentimentStrategy,
                "technical": TechnicalStrategy,
                "volume": VolumeStrategy,
            }

            for strategy_def in strategy_defs:
                strategy_class = strategy_classes.get(strategy_def.name)

                if not strategy_class:
                    logging.warning(
                        f"[StrategyManager] Unknown strategy '{strategy_def.name}', skipping"
                    )
                    continue

                # Instantiate strategy
                strategy = strategy_class()

                # Apply database configuration
                strategy.weight = float(strategy_def.weight)
                strategy.enabled = strategy_def.enabled

                # Apply strategy-specific parameters if provided
                if strategy_def.parameters:
                    for param_name, param_value in strategy_def.parameters.items():
                        if hasattr(strategy, param_name):
                            setattr(strategy, param_name, param_value)

                self.strategies.append(strategy)
                logging.info(
                    f"[StrategyManager] Loaded {strategy.name} from database "
                    f"(weight={strategy.weight}, enabled={strategy.enabled})"
                )

        except Exception as e:
            logging.error(f"[StrategyManager] Failed to load strategies from database: {e}")
            logging.info("[StrategyManager] Falling back to default strategies")
            self._load_default_strategies()

    def _load_default_strategies(self):
        """Load hardcoded default strategies (backward compatibility)."""
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

        # Apply custom weights if provided in config
        custom_weights = self.config.get("strategy_weights", {})
        for strategy in self.strategies:
            if strategy.name in custom_weights:
                strategy.weight = custom_weights[strategy.name]

        logging.info(f"[StrategyManager] Loaded {len(self.strategies)} default strategies")

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
    ) -> Tuple[str, float, str, Optional[int]]:
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
            Tuple of (signal, confidence, reason, signal_id)
            - signal: "BUY", "SELL", or "HOLD"
            - confidence: 0.0 to 1.0
            - reason: Detailed explanation
            - signal_id: Database ID of logged signal (or None)
        """
        # Normalize symbol to canonical format (BTCUSD, ETHUSD, etc.)
        try:
            symbol = normalize_symbol(symbol)
        except ValueError:
            logging.warning(f"[StrategyManager] Unknown symbol format: {symbol}, using as-is")
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
        signal_id = None
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

                signal_id = self.signal_logger.log_decision(
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

                # Emit SIGNAL_GENERATED event
                try:
                    import asyncio
                    from app.events.event_bus import event_bus, EventType
                    from datetime import datetime, timezone

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(event_bus.emit(EventType.SIGNAL_GENERATED, {
                                "signal_id": signal_id,
                                "symbol": symbol,
                                "signal": final_signal,
                                "confidence": final_confidence,
                                "price": current_price,
                                "num_strategies": len(strategy_results),
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }))
                        else:
                            loop.run_until_complete(event_bus.emit(EventType.SIGNAL_GENERATED, {
                                "signal_id": signal_id,
                                "symbol": symbol,
                                "signal": final_signal,
                                "confidence": final_confidence,
                                "price": current_price,
                                "num_strategies": len(strategy_results),
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }))
                    except RuntimeError:
                        asyncio.run(event_bus.emit(EventType.SIGNAL_GENERATED, {
                            "signal_id": signal_id,
                            "symbol": symbol,
                            "signal": final_signal,
                            "confidence": final_confidence,
                            "price": current_price,
                            "num_strategies": len(strategy_results),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }))
                except Exception as emit_error:
                    logging.error(f"[StrategyManager] Failed to emit SIGNAL_GENERATED event: {emit_error}")

            except Exception as e:
                # Never let logging errors crash trading
                logging.warning(f"⚠️  Signal logging failed: {e}")

        # Apply minimum confidence threshold
        if final_confidence < self.min_confidence:
            logging.info(
                f"[StrategyManager] Confidence {final_confidence:.2f} below threshold {self.min_confidence}, converting to HOLD"
            )
            return "HOLD", final_confidence, f"Low confidence: {final_reason}", signal_id

        return final_signal, final_confidence, final_reason, signal_id

    def get_signal_with_telemetry(
        self, symbol: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get aggregated trading signal with comprehensive telemetry.

        This method provides the same signal as get_signal() but returns
        detailed telemetry for analysis and debugging.

        Args:
            symbol: Trading pair (e.g., "BTC/USD")
            context: Context data (same as get_signal)

        Returns:
            Dict containing:
                - final_signal: "BUY", "SELL", or "HOLD"
                - final_confidence: 0.0 to 1.0
                - final_reason: Detailed explanation
                - signal_id: Database ID of logged signal (or None)
                - telemetry: Detailed breakdown dict
        """
        from datetime import datetime

        # Normalize symbol
        try:
            symbol = normalize_symbol(symbol)
        except ValueError:
            logging.warning(f"[StrategyManager] Unknown symbol format: {symbol}, using as-is")

        # Early exit if no strategies
        if not self.strategies:
            return {
                "final_signal": "HOLD",
                "final_confidence": 0.0,
                "final_reason": "No strategies available",
                "signal_id": None,
                "telemetry": {
                    "strategy_votes": [],
                    "aggregation": {},
                    "execution": {"would_execute": False, "reason": "No strategies"},
                    "context": {"symbol": symbol, "timestamp": datetime.now()},
                    "attribution": {}
                }
            }

        # Collect signals from all strategies
        strategy_results = []
        for strategy in self.strategies:
            if not strategy.enabled:
                continue

            try:
                signal, confidence, reason = strategy.get_signal(symbol, context)
                strategy_results.append({
                    "strategy": strategy.name,
                    "signal": signal,
                    "confidence": confidence,
                    "reason": reason,
                    "weight": strategy.weight,
                })
                logging.info(
                    f"[{strategy.name}] {symbol}: {signal} (conf: {confidence:.2f}) - {reason}"
                )
            except Exception as e:
                logging.error(
                    f"[{strategy.name}] Error getting signal for {symbol}: {e}"
                )
                continue

        if not strategy_results:
            return {
                "final_signal": "HOLD",
                "final_confidence": 0.0,
                "final_reason": "No strategies produced signals",
                "signal_id": None,
                "telemetry": {
                    "strategy_votes": [],
                    "aggregation": {},
                    "execution": {"would_execute": False, "reason": "No signals produced"},
                    "context": {"symbol": symbol, "timestamp": datetime.now()},
                    "attribution": {}
                }
            }

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

        # Build telemetry
        telemetry = self._build_telemetry(
            symbol=symbol,
            context=context,
            strategy_results=strategy_results,
            final_signal=final_signal,
            final_confidence=final_confidence,
            final_reason=final_reason
        )

        # Log signal to database
        current_price = context.get("price", 0.0)
        signal_id = None
        if current_price > 0 and strategy_results:
            try:
                strategy_details = {}
                for result in strategy_results:
                    strategy_details[result["strategy"]] = {
                        "signal": result["signal"],
                        "confidence": result["confidence"],
                        "reason": result["reason"],
                        "weight": result["weight"],
                        "enabled": True,
                    }

                signal_id = self.signal_logger.log_decision(
                    symbol=symbol,
                    price=current_price,
                    final_signal=final_signal,
                    final_confidence=final_confidence,
                    strategy_signals=strategy_details,
                    aggregation_method=self.aggregation_method,
                    metadata={
                        "min_confidence": self.min_confidence,
                        "num_strategies": len(strategy_results),
                        "telemetry": telemetry  # Store telemetry in metadata
                    },
                )
            except Exception as e:
                logging.warning(f"⚠️  Signal logging failed: {e}")

        # Check if would execute
        would_execute = final_confidence >= self.min_confidence
        if not would_execute:
            logging.info(
                f"[StrategyManager] Confidence {final_confidence:.2f} below threshold {self.min_confidence}"
            )

        return {
            "final_signal": final_signal,
            "final_confidence": final_confidence,
            "final_reason": final_reason,
            "signal_id": signal_id,
            "telemetry": telemetry
        }

    def _build_telemetry(
        self,
        symbol: str,
        context: Dict[str, Any],
        strategy_results: List[Dict],
        final_signal: str,
        final_confidence: float,
        final_reason: str
    ) -> Dict[str, Any]:
        """Build comprehensive telemetry data."""
        from datetime import datetime

        # 1. Strategy votes
        strategy_votes = []
        for result in strategy_results:
            strategy_votes.append({
                "strategy_name": result["strategy"],
                "signal": result["signal"],
                "confidence": result["confidence"],
                "reason": result["reason"],
                "weight": result["weight"],
                "enabled": True
            })

        # 2. Aggregation breakdown
        buy_score = sum(r["confidence"] * r["weight"] for r in strategy_results if r["signal"] == "BUY")
        sell_score = sum(r["confidence"] * r["weight"] for r in strategy_results if r["signal"] == "SELL")
        hold_score = sum(r["confidence"] * r["weight"] for r in strategy_results if r["signal"] == "HOLD")
        total_weight = sum(r["weight"] for r in strategy_results)

        aggregation = {
            "method": self.aggregation_method,
            "buy_score": float(buy_score),
            "sell_score": float(sell_score),
            "hold_score": float(hold_score),
            "total_weight": float(total_weight)
        }

        # 3. Execution decision
        would_execute = final_confidence >= self.min_confidence
        confidence_gap = self.min_confidence - final_confidence if not would_execute else 0.0
        near_miss = abs(confidence_gap) < 0.1 and not would_execute

        execution = {
            "would_execute": would_execute,
            "min_confidence_threshold": self.min_confidence,
            "actual_confidence": final_confidence,
            "reason": f"Meets threshold of {self.min_confidence}" if would_execute else f"Below threshold by {confidence_gap:.3f}",
            "confidence_gap": confidence_gap,
            "near_miss": near_miss
        }

        # 4. Market context
        context_data = {
            "symbol": symbol,
            "price": context.get("price", 0.0),
            "volume": context.get("volume", 0.0),
            "num_headlines": len(context.get("headlines", [])),
            "timestamp": datetime.now()
        }

        # 5. Strategy attribution
        agreeing = [r["strategy"] for r in strategy_results if r["signal"] == final_signal]
        disagreeing = [r["strategy"] for r in strategy_results if r["signal"] != final_signal]

        # Calculate contribution percentages
        contributions = {}
        for result in strategy_results:
            if result["signal"] == final_signal:
                contribution_pct = (result["confidence"] * result["weight"] / total_weight * 100) if total_weight > 0 else 0.0
                contributions[result["strategy"]] = float(contribution_pct)

        attribution = {
            "agreeing_strategies": agreeing,
            "disagreeing_strategies": disagreeing,
            "contribution_by_strategy": contributions
        }

        return {
            "strategy_votes": strategy_votes,
            "aggregation": aggregation,
            "execution": execution,
            "context": context_data,
            "attribution": attribution
        }

    def _weighted_vote_aggregation(self, results: List[Dict]) -> Tuple[str, float, str]:
        """
        Aggregate signals using weighted voting.
        HOLD signals don't dilute BUY/SELL confidence.
        """
        scores = defaultdict(float)
        reasons_by_signal = defaultdict(list)
        actionable_weight = 0  # Weight of BUY/SELL signals
        hold_weight = 0  # Weight of HOLD signals
        
        for result in results:
            signal = result["signal"]
            confidence = result["confidence"]
            weight = result["weight"]
            weighted_score = confidence * weight
            
            scores[signal] += weighted_score
            reasons_by_signal[signal].append(
                f"{result['strategy']}: {result['reason']}"
            )
            
            # Track weights separately
            if signal in ["BUY", "SELL"]:
                actionable_weight += weight
            else:
                hold_weight += weight
        
        # Find winning signal
        if not scores:
            return "HOLD", 0.0, "No valid signals"
        
        winning_signal = max(scores.items(), key=lambda x: x[1])
        signal = winning_signal[0]
        raw_score = winning_signal[1]
        
        # Calculate confidence based on signal type
        if signal in ["BUY", "SELL"] and actionable_weight > 0:
            # For actionable signals, only divide by actionable weight
            confidence = min(raw_score / actionable_weight, 1.0)
        elif actionable_weight + hold_weight > 0:
            # For HOLD, use total weight
            confidence = min(raw_score / (actionable_weight + hold_weight), 1.0)
        else:
            confidence = 0.0
        
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
