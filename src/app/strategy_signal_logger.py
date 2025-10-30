"""
Strategy Signal Logger - Enterprise-grade signal tracking and attribution.

This module provides atomic logging of all strategy signals for:
- Performance attribution
- Strategy analysis
- Backtesting validation
- Regulatory compliance
"""

import json
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
from decimal import Decimal
import threading

from app.database.connection import get_db
from app.database.repositories import SignalRepository

logger = logging.getLogger(__name__)


class StrategySignalLogger:
    """
    Thread-safe logger for strategy signals with atomic writes.
    
    Design goals:
    - Zero impact on trading performance (async writes)
    - Complete audit trail
    - Easy querying for analysis
    - Data integrity guarantees
    """
    
    def __init__(self, data_dir: str = "data", use_database: bool = True, test_mode: bool = False):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.signal_file = self.data_dir / "strategy_signals.jsonl"
        self._write_lock = threading.Lock()
        self.use_database = use_database
        self.test_mode = test_mode  # Track if this is test mode
    
    def log_decision(
        self,
        symbol: str,
        price: float,
        final_signal: str,
        final_confidence: float,
        strategy_signals: Dict[str, Dict[str, Any]],
        aggregation_method: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Log a complete trading decision with all strategy inputs.

        Args:
            symbol: Trading pair (e.g., "BTC/USD")
            price: Current price
            final_signal: Aggregated signal (BUY/SELL/HOLD)
            final_confidence: Aggregated confidence
            strategy_signals: Dict mapping strategy name to its signal details
                Example: {
                    "technical": {
                        "signal": "BUY",
                        "confidence": 0.73,
                        "reason": "SMA: BUY, RSI: HOLD",
                        "weight": 1.0,
                        "enabled": True
                    }
                }
            aggregation_method: How signals were combined
            metadata: Optional additional context (market conditions, etc.)

        Returns:
            Database ID of the logged signal (or None if logging failed)
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        record = {
            "timestamp": timestamp,
            "symbol": symbol,
            "price": price,
            "final_signal": final_signal,
            "final_confidence": final_confidence,
            "aggregation_method": aggregation_method,
            "strategies": strategy_signals,
            "metadata": metadata or {}
        }

        return self._append_record(record)
    
    def _append_record(self, record: Dict[str, Any]) -> Optional[int]:
        """
        Write signal record to database.

        Returns:
            Database ID of the created signal (or None if database write failed)
        """
        with self._write_lock:
            # Write to database (primary and only storage)
            signal_id = None
            if self.use_database:
                try:
                    with get_db() as db:
                        repo = SignalRepository(db)
                        signal_model = repo.create(
                            timestamp=datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00')).replace(tzinfo=None),
                            symbol=record['symbol'],
                            price=Decimal(str(record['price'])),
                            final_signal=record['final_signal'],
                            final_confidence=Decimal(str(record['final_confidence'])),
                            aggregation_method=record['aggregation_method'],
                            strategies=record['strategies'],
                            test_mode=self.test_mode,
                            bot_version="1.0.0",
                            signal_metadata=record.get('metadata')
                        )
                        # Commit happens automatically in context manager
                        signal_id = signal_model.id
                except Exception as e:
                    logger.error(f"Failed to write signal to database: {e}", exc_info=True)

            return signal_id
    
    def get_recent_signals(
        self,
        limit: int = 100,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent signals for analysis from database.

        Args:
            limit: Maximum number of records to return
            symbol: Optional filter by symbol

        Returns:
            List of signal records, newest first
        """
        if not self.use_database:
            return []

        try:
            with get_db() as db:
                repo = SignalRepository(db)
                # Get recent signals from last 7 days
                signals_models = repo.get_recent(hours=24*7, test_mode=self.test_mode, limit=limit)

                # Filter by symbol if provided
                if symbol:
                    signals_models = [s for s in signals_models if s.symbol == symbol]

                # Convert to dict format
                signals = []
                for s in signals_models:
                    signals.append({
                        'timestamp': s.timestamp.isoformat() + 'Z' if s.timestamp else None,
                        'symbol': s.symbol,
                        'price': float(s.price) if s.price else 0,
                        'final_signal': s.final_signal,
                        'final_confidence': float(s.final_confidence) if s.final_confidence else 0,
                        'aggregation_method': s.aggregation_method,
                        'strategies': s.strategies or {},
                        'metadata': s.signal_metadata or {}
                    })

                return signals
        except Exception as e:
            logger.error(f"Failed to read strategy signals from database: {e}")
            return []
    
    def get_strategy_performance(
        self,
        strategy_name: str,
        lookback_days: int = 7
    ) -> Dict[str, Any]:
        """
        Calculate performance metrics for a specific strategy.
        
        Args:
            strategy_name: Name of strategy to analyze
            lookback_days: How many days to look back
            
        Returns:
            Performance metrics including:
            - total_signals: Number of non-HOLD signals
            - signal_distribution: Count of BUY/SELL/HOLD
            - avg_confidence: Average confidence when signaling
            - agreement_rate: How often it agrees with final decision
        """
        signals = self.get_recent_signals(limit=10000)
        
        # Filter by date
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        cutoff_iso = cutoff.isoformat()
        signals = [s for s in signals if s['timestamp'] >= cutoff_iso]
        
        if not signals:
            return self._empty_performance_metrics()
        
        # Calculate metrics
        strategy_signals = []
        agreements = 0
        signal_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
        confidences = []
        
        for record in signals:
            if strategy_name in record['strategies']:
                strat = record['strategies'][strategy_name]
                strategy_signals.append(strat)
                
                signal = strat['signal']
                confidence = strat['confidence']
                
                signal_counts[signal] += 1
                confidences.append(confidence)
                
                # Check if strategy agreed with final decision
                if signal == record['final_signal']:
                    agreements += 1
        
        total = len(strategy_signals)
        if total == 0:
            return self._empty_performance_metrics()
        
        return {
            "strategy_name": strategy_name,
            "lookback_days": lookback_days,
            "total_signals": total,
            "signal_distribution": signal_counts,
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "agreement_rate": agreements / total if total > 0 else 0,
            "action_signals": signal_counts["BUY"] + signal_counts["SELL"],
            "action_rate": (signal_counts["BUY"] + signal_counts["SELL"]) / total if total > 0 else 0
        }
    
    def get_all_strategies_performance(
        self,
        lookback_days: int = 7
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get performance metrics for all strategies.
        
        Returns:
            Dict mapping strategy name to performance metrics
        """
        signals = self.get_recent_signals(limit=10000)
        
        if not signals:
            return {}
        
        # Get unique strategy names
        strategy_names = set()
        for record in signals:
            strategy_names.update(record['strategies'].keys())
        
        # Calculate performance for each
        return {
            name: self.get_strategy_performance(name, lookback_days)
            for name in strategy_names
        }
    
    def get_signal_correlation(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate correlation between strategy signals.
        
        Returns:
            Matrix of agreement rates between strategies
        """
        signals = self.get_recent_signals(limit=1000)
        
        if not signals:
            return {}
        
        # Get all strategy names
        strategy_names = set()
        for record in signals:
            strategy_names.update(record['strategies'].keys())
        
        strategy_names = sorted(strategy_names)
        
        # Calculate pairwise agreement
        correlations = {}
        for name1 in strategy_names:
            correlations[name1] = {}
            for name2 in strategy_names:
                if name1 == name2:
                    correlations[name1][name2] = 1.0
                else:
                    agreement = self._calculate_agreement(signals, name1, name2)
                    correlations[name1][name2] = agreement
        
        return correlations
    
    def _calculate_agreement(
        self,
        signals: List[Dict[str, Any]],
        strategy1: str,
        strategy2: str
    ) -> float:
        """Calculate how often two strategies give the same signal."""
        agreements = 0
        total = 0
        
        for record in signals:
            strats = record['strategies']
            if strategy1 in strats and strategy2 in strats:
                if strats[strategy1]['signal'] == strats[strategy2]['signal']:
                    agreements += 1
                total += 1
        
        return agreements / total if total > 0 else 0.0
    
    def _empty_performance_metrics(self) -> Dict[str, Any]:
        """Return empty/zero metrics structure."""
        return {
            "total_signals": 0,
            "signal_distribution": {"BUY": 0, "SELL": 0, "HOLD": 0},
            "avg_confidence": 0.0,
            "agreement_rate": 0.0,
            "action_signals": 0,
            "action_rate": 0.0
        }
    
    def clear_old_signals(self, days_to_keep: int = 30) -> int:
        """
        Delete old signals from database.

        Args:
            days_to_keep: Keep signals from last N days

        Returns:
            Number of records removed
        """
        if not self.use_database:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        with self._write_lock:
            try:
                with get_db() as db:
                    repo = SignalRepository(db)
                    # Get all old signals
                    all_signals = repo.get_all(test_mode=self.test_mode)
                    removed_count = 0

                    for signal in all_signals:
                        if signal.timestamp and signal.timestamp < cutoff.replace(tzinfo=None):
                            db.delete(signal)
                            removed_count += 1

                    db.commit()
                    return removed_count
            except Exception as e:
                logger.error(f"Failed to clear old signals from database: {e}")
                return 0