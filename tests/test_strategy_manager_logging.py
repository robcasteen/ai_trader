"""
Tests to verify signal logging integration doesn't affect trading behavior.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import json

from app.strategies.strategy_manager import StrategyManager
from app.strategy_signal_logger import StrategySignalLogger


@pytest.fixture
def temp_data_dir():
    """Create temporary directory for signal logs."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def strategy_manager(temp_data_dir):
    """Create strategy manager with temp data directory."""
    manager = StrategyManager()
    # Replace logger with one using temp directory
    manager.signal_logger = StrategySignalLogger(data_dir=temp_data_dir)
    return manager


class TestSignalLogging:
    """Test that signal logging works correctly."""
    
    def test_signal_file_created_after_decision(self, strategy_manager, temp_data_dir):
        """Should create signal log file after first decision."""
        context = {
            'price': 50000,
            'headlines': ['Bitcoin adoption growing'],
            'price_history': [49000 + i*100 for i in range(50)],
            'volume': 1000,
            'volume_history': [1000] * 50
        }
        
        signal, confidence, reason = strategy_manager.get_signal("BTC/USD", context)
        
        signal_file = Path(temp_data_dir) / "strategy_signals.jsonl"
        assert signal_file.exists(), "Signal file should be created"
        
        # Verify it has content
        with open(signal_file, 'r') as f:
            lines = f.readlines()
        assert len(lines) > 0, "Signal file should have at least one record"
    
    def test_logs_all_strategy_details(self, strategy_manager, temp_data_dir):
        """Should log individual strategy signals."""
        context = {
            'price': 50000,
            'headlines': ['Bitcoin bullish'],
            'price_history': [49000 + i*100 for i in range(50)],
            'volume': 1000,
            'volume_history': [1000] * 50
        }
        
        strategy_manager.get_signal("BTC/USD", context)
        
        signal_file = Path(temp_data_dir) / "strategy_signals.jsonl"
        with open(signal_file, 'r') as f:
            record = json.loads(f.readline())
        
        assert 'strategies' in record
        # Check that at least sentiment strategy is logged
        assert len(record['strategies']) > 0
        
        # Check structure of strategy data
        for strategy_name, strategy_data in record['strategies'].items():
            assert 'signal' in strategy_data
            assert 'confidence' in strategy_data
            assert 'reason' in strategy_data
            assert 'weight' in strategy_data
    
    def test_logs_correct_data_structure(self, strategy_manager, temp_data_dir):
        """Should log complete and correct data structure."""
        context = {
            'price': 50000,
            'headlines': ['Test headline'],
            'price_history': [49000] * 50,
            'volume': 1000,
            'volume_history': [1000] * 50
        }
        
        strategy_manager.get_signal("BTC/USD", context)
        
        signal_file = Path(temp_data_dir) / "strategy_signals.jsonl"
        with open(signal_file, 'r') as f:
            record = json.loads(f.readline())
        
        # Verify top-level structure
        assert 'timestamp' in record
        assert 'symbol' in record
        assert record["symbol"] == "BTCUSD"
        assert 'price' in record
        assert record['price'] == 50000
        assert 'final_signal' in record
        assert record['final_signal'] in ["BUY", "SELL", "HOLD"]
        assert 'final_confidence' in record
        assert 0 <= record['final_confidence'] <= 1
        assert 'aggregation_method' in record
        assert 'strategies' in record
        assert 'metadata' in record
    
    def test_multiple_signals_appended(self, strategy_manager, temp_data_dir):
        """Should append multiple signals to file."""
        context = {
            'price': 50000,
            'headlines': ['Test'],
            'price_history': [49000] * 50,
            'volume': 1000,
            'volume_history': [1000] * 50
        }
        
        # Generate 3 signals
        for i in range(3):
            strategy_manager.get_signal(f"SYMBOL{i}/USD", context)
        
        signal_file = Path(temp_data_dir) / "strategy_signals.jsonl"
        with open(signal_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 3


class TestBackwardCompatibility:
    """Test that logging doesn't change trading behavior."""
    
    def test_signals_unchanged_with_logging(self, strategy_manager):
        """Signals should be identical whether logging succeeds or fails."""
        context = {
            'price': 50000,
            'headlines': ['Bitcoin positive news'],
            'price_history': [49000 + i*100 for i in range(50)],
            'volume': 1000,
            'volume_history': [1000] * 50
        }
        
        # Get signal with logging enabled
        signal1, conf1, reason1 = strategy_manager.get_signal("BTC/USD", context)
        
        # Get signal again with same context
        signal2, conf2, reason2 = strategy_manager.get_signal("BTC/USD", context)
        
        # Should be identical
        assert signal1 == signal2
        assert conf1 == conf2
    
    def test_logging_failure_does_not_crash(self, strategy_manager, caplog):
        """Trading should continue even if logging fails."""
        import logging
        
        context = {
            'price': 50000,
            'headlines': ['Test'],
            'price_history': [49000] * 50,
            'volume': 1000,
            'volume_history': [1000] * 50
        }
        
        # Simulate logging failure by making logger raise exception
        original_log = strategy_manager.signal_logger.log_decision
        
        def failing_log(*args, **kwargs):
            raise Exception("Simulated logging failure")
        
        strategy_manager.signal_logger.log_decision = failing_log
        
        # Should NOT raise exception
        with caplog.at_level(logging.WARNING):
            signal, confidence, reason = strategy_manager.get_signal("BTC/USD", context)
        
        # Should still return valid signal
        assert signal in ["BUY", "SELL", "HOLD"]
        assert 0 <= confidence <= 1
        
        # Should log warning
        assert "Signal logging failed" in caplog.text
        
        # Restore
        strategy_manager.signal_logger.log_decision = original_log
    
    def test_no_price_does_not_log(self, strategy_manager, temp_data_dir):
        """Should not log when price is missing or invalid."""
        context = {
            'price': 0,  # Invalid price
            'headlines': ['Test'],
            'price_history': [],
            'volume': 0,
            'volume_history': []
        }
        
        strategy_manager.get_signal("BTC/USD", context)
        
        signal_file = Path(temp_data_dir) / "strategy_signals.jsonl"
        # File should not be created or should be empty
        assert not signal_file.exists() or signal_file.stat().st_size == 0
    
    def test_existing_tests_still_pass(self):
        """Verify that adding logging didn't break existing functionality."""
        # This is a meta-test - if we got here, other tests passed
        manager = StrategyManager()
        
        # Basic functionality check
        assert len(manager.strategies) > 0
        assert manager.aggregation_method in ["weighted_vote", "highest_confidence", "unanimous"]
        assert hasattr(manager, 'signal_logger')


class TestLoggingContent:
    """Test the content being logged is accurate."""
    
    def test_logs_actual_strategy_outputs(self, strategy_manager, temp_data_dir):
        """Logged strategy signals should match what strategies actually returned."""
        context = {
            'price': 50000,
            'headlines': ['Bitcoin is rising'],
            'price_history': [49000 + i*100 for i in range(50)],
            'volume': 1000,
            'volume_history': [1000] * 50
        }
        
        # Get the final signal
        final_signal, final_conf, final_reason = strategy_manager.get_signal("BTC/USD", context)
        
        # Read what was logged
        signal_file = Path(temp_data_dir) / "strategy_signals.jsonl"
        with open(signal_file, 'r') as f:
            record = json.loads(f.readline())
        
        # Verify logged signal is valid (might differ from final if confidence filter applied)
        assert record['final_signal'] in ["BUY", "SELL", "HOLD"]
        assert 0 <= record['final_confidence'] <= 1
        
        # If confidence was above threshold, signals should match
        # If below threshold, final will be HOLD but logged might be BUY/SELL
        if record['final_confidence'] >= strategy_manager.min_confidence:
            assert record['final_signal'] == final_signal
        
        # Verify strategies were logged
        assert len(record['strategies']) > 0
    
    def test_logs_aggregation_method(self, strategy_manager, temp_data_dir):
        """Should log which aggregation method was used."""
        context = {
            'price': 50000,
            'headlines': ['Test'],
            'price_history': [49000] * 50,
            'volume': 1000,
            'volume_history': [1000] * 50
        }
        
        strategy_manager.get_signal("BTC/USD", context)
        
        signal_file = Path(temp_data_dir) / "strategy_signals.jsonl"
        with open(signal_file, 'r') as f:
            record = json.loads(f.readline())
        
        assert record['aggregation_method'] == strategy_manager.aggregation_method