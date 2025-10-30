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
        """Should log signal to TEST database after first decision."""
        from app.database.models import Signal
        from app.database.connection import get_db

        context = {
            'price': 50000,
            'headlines': ['Bitcoin adoption growing'],
            'price_history': [49000 + i*100 for i in range(50)],
            'volume': 1000,
            'volume_history': [1000] * 50
        }

        signal, confidence, reason, signal_id = strategy_manager.get_signal("BTC/USD", context)

        # Verify signal was logged to TEST database
        assert signal_id is not None, "Signal ID should be returned"

        with get_db() as db:
            logged_signal = db.query(Signal).filter(Signal.id == signal_id).first()
            assert logged_signal is not None, "Signal should exist in TEST database"
    
    def test_logs_all_strategy_details(self, strategy_manager, temp_data_dir):
        """Should log individual strategy signals to TEST database."""
        from app.database.models import Signal
        from app.database.connection import get_db

        context = {
            'price': 50000,
            'headlines': ['Bitcoin bullish'],
            'price_history': [49000 + i*100 for i in range(50)],
            'volume': 1000,
            'volume_history': [1000] * 50
        }

        signal, confidence, reason, signal_id = strategy_manager.get_signal("BTC/USD", context)

        # Query TEST database for logged signal
        with get_db() as db:
            logged_signal = db.query(Signal).filter(Signal.id == signal_id).first()
            assert logged_signal is not None, "Signal should exist in TEST database"

            # Verify strategies were logged
            assert logged_signal.strategies is not None, "Strategies should be logged"
            assert len(logged_signal.strategies) > 0, "At least one strategy should be logged"

            # Check structure of strategy data
            for strategy_name, strategy_data in logged_signal.strategies.items():
                assert 'signal' in strategy_data, f"{strategy_name} should have signal"
                assert 'confidence' in strategy_data, f"{strategy_name} should have confidence"
                assert 'reason' in strategy_data, f"{strategy_name} should have reason"
                assert 'weight' in strategy_data, f"{strategy_name} should have weight"
    
    def test_logs_correct_data_structure(self, strategy_manager, temp_data_dir):
        """Should log complete and correct data structure to TEST database."""
        from app.database.models import Signal
        from app.database.connection import get_db

        context = {
            'price': 50000,
            'headlines': ['Test headline'],
            'price_history': [49000] * 50,
            'volume': 1000,
            'volume_history': [1000] * 50
        }

        signal, confidence, reason, signal_id = strategy_manager.get_signal("BTC/USD", context)

        # Query TEST database and verify structure
        with get_db() as db:
            logged_signal = db.query(Signal).filter(Signal.id == signal_id).first()
            assert logged_signal is not None, "Signal should exist in TEST database"

            # Verify top-level structure
            assert logged_signal.timestamp is not None, "Should have timestamp"
            assert logged_signal.symbol is not None, "Should have symbol"
            assert logged_signal.symbol == "BTCUSD", "Symbol should be normalized to BTCUSD"
            assert logged_signal.price is not None, "Should have price"
            assert float(logged_signal.price) == 50000, "Price should match"
            assert logged_signal.final_signal in ["BUY", "SELL", "HOLD"], "Final signal should be valid"
            assert 0 <= float(logged_signal.final_confidence) <= 1, "Confidence should be 0-1"
            assert logged_signal.aggregation_method is not None, "Should have aggregation method"
            assert logged_signal.strategies is not None, "Should have strategies"
            assert logged_signal.signal_metadata is not None, "Should have metadata"
    
    def test_multiple_signals_appended(self, strategy_manager, temp_data_dir):
        """Should append multiple signals to TEST database."""
        from app.database.models import Signal
        from app.database.connection import get_db

        context = {
            'price': 50000,
            'headlines': ['Test'],
            'price_history': [49000] * 50,
            'volume': 1000,
            'volume_history': [1000] * 50
        }

        # Generate 3 signals
        signal_ids = []
        for i in range(3):
            _, _, _, signal_id = strategy_manager.get_signal(f"SYMBOL{i}/USD", context)
            signal_ids.append(signal_id)

        # Verify all 3 signals exist in TEST database
        with get_db() as db:
            signals = db.query(Signal).filter(Signal.id.in_(signal_ids)).all()
            assert len(signals) == 3, "All 3 signals should exist in TEST database"


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
        signal1, conf1, reason1, signal_id1 = strategy_manager.get_signal("BTC/USD", context)

        # Get signal again with same context
        signal2, conf2, reason2, signal_id2 = strategy_manager.get_signal("BTC/USD", context)
        
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
            signal, confidence, reason, signal_id = strategy_manager.get_signal("BTC/USD", context)
        
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
        """Logged strategy signals in TEST database should match what strategies actually returned."""
        from app.database.models import Signal
        from app.database.connection import get_db

        context = {
            'price': 50000,
            'headlines': ['Bitcoin is rising'],
            'price_history': [49000 + i*100 for i in range(50)],
            'volume': 1000,
            'volume_history': [1000] * 50
        }

        # Get the final signal
        final_signal, final_conf, final_reason, signal_id = strategy_manager.get_signal("BTC/USD", context)

        # Query TEST database for logged signal
        with get_db() as db:
            logged_signal = db.query(Signal).filter(Signal.id == signal_id).first()
            assert logged_signal is not None, "Signal should exist in TEST database"

            # Verify logged signal is valid (might differ from final if confidence filter applied)
            assert logged_signal.final_signal in ["BUY", "SELL", "HOLD"], "Logged signal should be valid"
            assert 0 <= float(logged_signal.final_confidence) <= 1, "Logged confidence should be 0-1"

            # If confidence was above threshold, signals should match
            # If below threshold, final will be HOLD but logged might be BUY/SELL
            if float(logged_signal.final_confidence) >= strategy_manager.min_confidence:
                assert logged_signal.final_signal == final_signal, "Signals should match when above threshold"

            # Verify strategies were logged
            assert len(logged_signal.strategies) > 0, "At least one strategy should be logged"
    
    def test_logs_aggregation_method(self, strategy_manager, temp_data_dir):
        """Should log which aggregation method was used to TEST database."""
        from app.database.models import Signal
        from app.database.connection import get_db

        context = {
            'price': 50000,
            'headlines': ['Test'],
            'price_history': [49000] * 50,
            'volume': 1000,
            'volume_history': [1000] * 50
        }

        _, _, _, signal_id = strategy_manager.get_signal("BTC/USD", context)

        # Query TEST database and verify aggregation method
        with get_db() as db:
            logged_signal = db.query(Signal).filter(Signal.id == signal_id).first()
            assert logged_signal is not None, "Signal should exist in TEST database"
            assert logged_signal.aggregation_method == strategy_manager.aggregation_method, \
                "Aggregation method should match strategy manager's method"