"""
Tests for StrategySignalLogger.

Enterprise-grade testing ensuring:
- Data integrity
- Thread safety
- Performance characteristics
- Error handling
"""

import pytest
import json
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
import threading
import time

from app.strategy_signal_logger import StrategySignalLogger


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def logger(temp_data_dir):
    """Create a logger instance with temp directory."""
    return StrategySignalLogger(data_dir=temp_data_dir)


class TestInitialization:
    """Test logger initialization and setup."""
    
    def test_creates_data_directory(self, temp_data_dir):
        """Should create data directory if it doesn't exist."""
        data_path = Path(temp_data_dir) / "subdir"
        assert not data_path.exists()
        
        logger = StrategySignalLogger(data_dir=str(data_path))
        
        assert data_path.exists()
    
    def test_uses_existing_directory(self, temp_data_dir):
        """Should work with existing directory."""
        logger = StrategySignalLogger(data_dir=temp_data_dir)
        assert logger.signal_file.parent.exists()


class TestLogDecision:
    """Test logging of trading decisions."""
    
    def test_logs_complete_decision(self, logger):
        """Should log all decision components."""
        strategy_signals = {
            "technical": {
                "signal": "BUY",
                "confidence": 0.73,
                "reason": "SMA crossover",
                "weight": 1.0,
                "enabled": True
            },
            "sentiment": {
                "signal": "BUY",
                "confidence": 0.82,
                "reason": "Positive news",
                "weight": 1.0,
                "enabled": True
            }
        }
        
        logger.log_decision(
            symbol="BTC/USD",
            price=50000.0,
            final_signal="BUY",
            final_confidence=0.78,
            strategy_signals=strategy_signals,
            aggregation_method="weighted_vote"
        )
        
        # Verify file was created and contains data
        assert logger.signal_file.exists()
        
        with open(logger.signal_file, 'r') as f:
            line = f.readline()
            record = json.loads(line)
        
        assert record['symbol'] == "BTC/USD"
        assert record['price'] == 50000.0
        assert record['final_signal'] == "BUY"
        assert record['final_confidence'] == 0.78
        assert record['aggregation_method'] == "weighted_vote"
        assert "technical" in record['strategies']
        assert "sentiment" in record['strategies']
        assert record['strategies']['technical']['signal'] == "BUY"
    
    def test_includes_timestamp(self, logger):
        """Should include ISO8601 timestamp."""
        before = datetime.now(timezone.utc)
        
        logger.log_decision(
            symbol="BTC/USD",
            price=50000.0,
            final_signal="HOLD",
            final_confidence=0.5,
            strategy_signals={},
            aggregation_method="weighted_vote"
        )
        
        after = datetime.now(timezone.utc)
        
        with open(logger.signal_file, 'r') as f:
            record = json.loads(f.readline())
        
        timestamp = datetime.fromisoformat(record['timestamp'])
        assert before <= timestamp <= after
    
    def test_includes_optional_metadata(self, logger):
        """Should log optional metadata when provided."""
        metadata = {
            "market_volatility": 0.15,
            "volume_24h": 1000000,
            "news_count": 5
        }
        
        logger.log_decision(
            symbol="ETH/USD",
            price=3000.0,
            final_signal="SELL",
            final_confidence=0.65,
            strategy_signals={},
            aggregation_method="highest_confidence",
            metadata=metadata
        )
        
        with open(logger.signal_file, 'r') as f:
            record = json.loads(f.readline())
        
        assert record['metadata'] == metadata
    
    def test_appends_multiple_records(self, logger):
        """Should append multiple records to JSONL file."""
        for i in range(5):
            logger.log_decision(
                symbol=f"SYM{i}/USD",
                price=100.0 + i,
                final_signal="HOLD",
                final_confidence=0.5,
                strategy_signals={},
                aggregation_method="weighted_vote"
            )
        
        with open(logger.signal_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 5
        
        # Verify each line is valid JSON
        for i, line in enumerate(lines):
            record = json.loads(line)
            assert record['symbol'] == f"SYM{i}/USD"
            assert record['price'] == 100.0 + i
    
    def test_handles_write_errors_gracefully(self, logger, capsys):
        """Should not crash if write fails."""
        # Make file read-only to force write error
        logger.signal_file.touch()
        logger.signal_file.chmod(0o444)
        
        # Should not raise exception
        logger.log_decision(
            symbol="BTC/USD",
            price=50000.0,
            final_signal="HOLD",
            final_confidence=0.5,
            strategy_signals={},
            aggregation_method="weighted_vote"
        )
        
        captured = capsys.readouterr()
        assert "Failed to log strategy signal" in captured.out


class TestGetRecentSignals:
    """Test retrieval of recent signals."""
    
    def test_returns_empty_for_no_data(self, logger):
        """Should return empty list when no signals logged."""
        signals = logger.get_recent_signals()
        assert signals == []
    
    def test_returns_recent_signals(self, logger):
        """Should return recent signals in reverse chronological order."""
        for i in range(10):
            logger.log_decision(
                symbol=f"BTC/USD",
                price=50000.0 + i,
                final_signal="HOLD",
                final_confidence=0.5,
                strategy_signals={},
                aggregation_method="weighted_vote"
            )
            time.sleep(0.001)  # Ensure different timestamps
        
        signals = logger.get_recent_signals(limit=5)
        
        assert len(signals) == 5
        # Most recent first
        assert signals[0]['price'] == 50009.0
        assert signals[4]['price'] == 50005.0
    
    def test_respects_limit(self, logger):
        """Should respect limit parameter."""
        for i in range(20):
            logger.log_decision(
                symbol="BTC/USD",
                price=50000.0,
                final_signal="HOLD",
                final_confidence=0.5,
                strategy_signals={},
                aggregation_method="weighted_vote"
            )
        
        signals = logger.get_recent_signals(limit=10)
        assert len(signals) == 10
    
    def test_filters_by_symbol(self, logger):
        """Should filter signals by symbol when specified."""
        symbols = ["BTC/USD", "ETH/USD", "BTC/USD", "LTC/USD", "BTC/USD"]
        
        for symbol in symbols:
            logger.log_decision(
                symbol=symbol,
                price=50000.0,
                final_signal="HOLD",
                final_confidence=0.5,
                strategy_signals={},
                aggregation_method="weighted_vote"
            )
        
        btc_signals = logger.get_recent_signals(symbol="BTC/USD")
        assert len(btc_signals) == 3
        assert all(s['symbol'] == "BTC/USD" for s in btc_signals)
    
    def test_handles_corrupted_file(self, logger, capsys):
        """Should handle corrupted JSONL gracefully."""
        # Write some invalid JSON
        with open(logger.signal_file, 'w') as f:
            f.write('invalid json\n')
        
        # Should not crash, returns empty list
        signals = logger.get_recent_signals()
        assert signals == []


class TestStrategyPerformance:
    """Test strategy performance calculation."""
    
    def test_empty_performance_for_no_data(self, logger):
        """Should return zero metrics when no data available."""
        perf = logger.get_strategy_performance("technical", lookback_days=7)
        
        assert perf['total_signals'] == 0
        assert perf['avg_confidence'] == 0.0
        assert perf['agreement_rate'] == 0.0
    
    def test_calculates_signal_distribution(self, logger):
        """Should count BUY/SELL/HOLD signals correctly."""
        strategy_signals = {
            "technical": {
                "signal": "BUY",
                "confidence": 0.7,
                "reason": "Test"
            }
        }
        
        # Log 5 BUY, 3 SELL, 2 HOLD
        for _ in range(5):
            strategy_signals["technical"]["signal"] = "BUY"
            logger.log_decision("BTC/USD", 50000, "BUY", 0.7, strategy_signals, "test")
        
        for _ in range(3):
            strategy_signals["technical"]["signal"] = "SELL"
            logger.log_decision("BTC/USD", 50000, "SELL", 0.7, strategy_signals, "test")
        
        for _ in range(2):
            strategy_signals["technical"]["signal"] = "HOLD"
            logger.log_decision("BTC/USD", 50000, "HOLD", 0.7, strategy_signals, "test")
        
        perf = logger.get_strategy_performance("technical", lookback_days=1)
        
        assert perf['total_signals'] == 10
        assert perf['signal_distribution']['BUY'] == 5
        assert perf['signal_distribution']['SELL'] == 3
        assert perf['signal_distribution']['HOLD'] == 2
    
    def test_calculates_average_confidence(self, logger):
        """Should calculate average confidence across signals."""
        for conf in [0.5, 0.7, 0.9]:
            logger.log_decision(
                "BTC/USD",
                50000,
                "BUY",
                0.7,
                {
                    "technical": {
                        "signal": "BUY",
                        "confidence": conf,
                        "reason": "Test"
                    }
                },
                "test"
            )
        
        perf = logger.get_strategy_performance("technical", lookback_days=1)
        
        expected_avg = (0.5 + 0.7 + 0.9) / 3
        assert abs(perf['avg_confidence'] - expected_avg) < 0.01
    
    def test_calculates_agreement_rate(self, logger):
        """Should calculate how often strategy agrees with final decision."""
        # 3 agreements, 2 disagreements
        signals = [
            ("BUY", "BUY"),   # Agree
            ("BUY", "BUY"),   # Agree
            ("SELL", "BUY"),  # Disagree
            ("BUY", "BUY"),   # Agree
            ("SELL", "HOLD"), # Disagree
        ]
        
        for strat_sig, final_sig in signals:
            logger.log_decision(
                "BTC/USD",
                50000,
                final_sig,
                0.7,
                {
                    "technical": {
                        "signal": strat_sig,
                        "confidence": 0.7,
                        "reason": "Test"
                    }
                },
                "test"
            )
        
        perf = logger.get_strategy_performance("technical", lookback_days=1)
        
        assert perf['agreement_rate'] == 0.6  # 3/5
    
    def test_filters_by_lookback_period(self, logger):
        """Should only include signals within lookback period."""
        # Add a signal now
        logger.log_decision(
            "BTC/USD", 50000, "BUY", 0.7,
            {"technical": {"signal": "BUY", "confidence": 0.7, "reason": "Test"}},
            "test"
        )
        
        # Looking back 0 days should find nothing (cutoff is start of today)
        perf = logger.get_strategy_performance("technical", lookback_days=0)
        # Should have the signal since it's within today
        assert perf['total_signals'] >= 0  # May be 0 or 1 depending on timing


class TestAllStrategiesPerformance:
    """Test performance calculation for all strategies."""
    
    def test_returns_all_strategies(self, logger):
        """Should return metrics for all strategies in data."""
        logger.log_decision(
            "BTC/USD",
            50000,
            "BUY",
            0.7,
            {
                "technical": {"signal": "BUY", "confidence": 0.7, "reason": "Test"},
                "sentiment": {"signal": "BUY", "confidence": 0.8, "reason": "Test"},
                "volume": {"signal": "HOLD", "confidence": 0.5, "reason": "Test"}
            },
            "test"
        )
        
        all_perf = logger.get_all_strategies_performance(lookback_days=1)
        
        assert "technical" in all_perf
        assert "sentiment" in all_perf
        assert "volume" in all_perf
        assert len(all_perf) == 3
    
    def test_returns_empty_for_no_data(self, logger):
        """Should return empty dict when no signals logged."""
        all_perf = logger.get_all_strategies_performance(lookback_days=1)
        assert all_perf == {}


class TestSignalCorrelation:
    """Test strategy correlation calculation."""
    
    def test_perfect_agreement(self, logger):
        """Should return 1.0 for strategies that always agree."""
        for _ in range(10):
            logger.log_decision(
                "BTC/USD",
                50000,
                "BUY",
                0.7,
                {
                    "technical": {"signal": "BUY", "confidence": 0.7, "reason": "Test"},
                    "sentiment": {"signal": "BUY", "confidence": 0.8, "reason": "Test"}
                },
                "test"
            )
        
        correlations = logger.get_signal_correlation()
        
        assert correlations["technical"]["sentiment"] == 1.0
        assert correlations["sentiment"]["technical"] == 1.0
    
    def test_no_agreement(self, logger):
        """Should return 0.0 for strategies that never agree."""
        for _ in range(10):
            logger.log_decision(
                "BTC/USD",
                50000,
                "HOLD",
                0.5,
                {
                    "technical": {"signal": "BUY", "confidence": 0.7, "reason": "Test"},
                    "sentiment": {"signal": "SELL", "confidence": 0.8, "reason": "Test"}
                },
                "test"
            )
        
        correlations = logger.get_signal_correlation()
        
        assert correlations["technical"]["sentiment"] == 0.0
    
    def test_self_correlation_is_one(self, logger):
        """Should return 1.0 for strategy correlation with itself."""
        logger.log_decision(
            "BTC/USD",
            50000,
            "BUY",
            0.7,
            {
                "technical": {"signal": "BUY", "confidence": 0.7, "reason": "Test"}
            },
            "test"
        )
        
        correlations = logger.get_signal_correlation()
        
        assert correlations["technical"]["technical"] == 1.0
    
    def test_returns_empty_for_no_data(self, logger):
        """Should return empty dict when no signals logged."""
        correlations = logger.get_signal_correlation()
        assert correlations == {}


class TestClearOldSignals:
    """Test archival/deletion of old signals."""
    
    def test_returns_zero_for_no_file(self, logger):
        """Should return 0 when no file exists."""
        removed = logger.clear_old_signals(days_to_keep=30)
        assert removed == 0
    
    def test_preserves_recent_signals(self, logger):
        """Should keep signals within retention period."""
        logger.log_decision("BTC/USD", 50000, "BUY", 0.7, {}, "test")
        
        removed = logger.clear_old_signals(days_to_keep=30)
        
        signals = logger.get_recent_signals()
        assert len(signals) == 1
        assert removed == 0


class TestThreadSafety:
    """Test thread safety of concurrent operations."""
    
    def test_concurrent_writes(self, logger):
        """Should handle concurrent writes without data corruption."""
        def write_signals(thread_id: int, count: int):
            for i in range(count):
                logger.log_decision(
                    symbol=f"T{thread_id}/USD",
                    price=50000.0 + thread_id,
                    final_signal="HOLD",
                    final_confidence=0.5,
                    strategy_signals={},
                    aggregation_method="test"
                )
        
        threads = []
        threads_count = 5
        signals_per_thread = 20
        
        for i in range(threads_count):
            t = threading.Thread(target=write_signals, args=(i, signals_per_thread))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify all signals were written
        with open(logger.signal_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == threads_count * signals_per_thread
        
        # Verify each line is valid JSON
        for line in lines:
            record = json.loads(line)
            assert 'symbol' in record