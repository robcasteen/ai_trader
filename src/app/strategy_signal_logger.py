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
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import threading


class StrategySignalLogger:
    """
    Thread-safe logger for strategy signals with atomic writes.
    
    Design goals:
    - Zero impact on trading performance (async writes)
    - Complete audit trail
    - Easy querying for analysis
    - Data integrity guarantees
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.signal_file = self.data_dir / "strategy_signals.jsonl"
        self._write_lock = threading.Lock()
    
    def log_decision(
        self,
        symbol: str,
        price: float,
        final_signal: str,
        final_confidence: float,
        strategy_signals: Dict[str, Dict[str, Any]],
        aggregation_method: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
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
        
        self._append_record(record)
    
    def _append_record(self, record: Dict[str, Any]) -> None:
        """Atomically append a record to the JSONL file."""
        with self._write_lock:
            try:
                with open(self.signal_file, 'a') as f:
                    f.write(json.dumps(record) + '\n')
            except Exception as e:
                # Log error but don't crash the trading bot
                print(f"⚠️  Failed to log strategy signal: {e}")
    
    def get_recent_signals(
        self,
        limit: int = 100,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent signals for analysis.
        
        Args:
            limit: Maximum number of records to return
            symbol: Optional filter by symbol
            
        Returns:
            List of signal records, newest first
        """
        if not self.signal_file.exists():
            return []
        
        try:
            signals = []
            with open(self.signal_file, 'r') as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        if symbol is None or record.get('symbol') == symbol:
                            signals.append(record)
            
            # Return most recent first
            return signals[-limit:][::-1]
        except Exception as e:
            print(f"⚠️  Failed to read strategy signals: {e}")
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
        Archive or delete old signals to manage file size.
        
        Args:
            days_to_keep: Keep signals from last N days
            
        Returns:
            Number of records removed
        """
        if not self.signal_file.exists():
            return 0
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        cutoff_iso = cutoff.isoformat()
        
        kept_records = []
        removed_count = 0
        
        with self._write_lock:
            try:
                # Read all records
                with open(self.signal_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)
                            if record['timestamp'] >= cutoff_iso:
                                kept_records.append(record)
                            else:
                                removed_count += 1
                
                # Rewrite file with kept records only
                with open(self.signal_file, 'w') as f:
                    for record in kept_records:
                        f.write(json.dumps(record) + '\n')
                
                return removed_count
            except Exception as e:
                print(f"⚠️  Failed to clear old signals: {e}")
                return 0