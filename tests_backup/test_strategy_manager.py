"""
Tests for StrategyManager.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from app.strategies.strategy_manager import StrategyManager
from app.strategies.base_strategy import BaseStrategy


class MockStrategy(BaseStrategy):
    """Mock strategy for testing."""
    
    def __init__(self, name, signal="BUY", confidence=0.8):
        super().__init__(name)
        self.mock_signal = signal
        self.mock_confidence = confidence
    
    def get_signal(self, symbol, context):
        return self.mock_signal, self.mock_confidence, f"{self.name} signal"


@pytest.fixture
def strategy_manager():
    return StrategyManager(config={'use_technical': False, 'use_volume': False})


class TestStrategyManager:
    def test_initialization(self, strategy_manager):
        """Test strategy manager initialization."""
        assert len(strategy_manager.strategies) >= 1  # At least sentiment
        assert strategy_manager.min_confidence == 0.5
        assert strategy_manager.aggregation_method == 'weighted_vote'
    
    def test_add_strategy(self, strategy_manager):
        """Test adding a custom strategy."""
        custom = MockStrategy("custom", "BUY", 0.9)
        initial_count = len(strategy_manager.strategies)
        
        strategy_manager.add_strategy(custom)
        
        assert len(strategy_manager.strategies) == initial_count + 1
    
    def test_remove_strategy(self, strategy_manager):
        """Test removing a strategy."""
        custom = MockStrategy("custom")
        strategy_manager.add_strategy(custom)
        initial_count = len(strategy_manager.strategies)
        
        strategy_manager.remove_strategy("custom")
        
        assert len(strategy_manager.strategies) == initial_count - 1
    
    def test_enable_disable_strategy(self, strategy_manager):
        """Test enabling and disabling strategies."""
        # Add a test strategy
        test_strategy = MockStrategy("test")
        strategy_manager.add_strategy(test_strategy)
        
        assert test_strategy.enabled is True
        
        strategy_manager.disable_strategy("test")
        assert test_strategy.enabled is False
        
        strategy_manager.enable_strategy("test")
        assert test_strategy.enabled is True
    
    def test_weighted_vote_all_buy(self, strategy_manager):
        """Test weighted vote when all strategies say BUY."""
        # Clear existing strategies
        strategy_manager.strategies = []
        
        # Add mock strategies all saying BUY
        strategy_manager.add_strategy(MockStrategy("s1", "BUY", 0.8))
        strategy_manager.add_strategy(MockStrategy("s2", "BUY", 0.7))
        strategy_manager.add_strategy(MockStrategy("s3", "BUY", 0.9))
        
        context = {'headlines': [], 'price': 50000}
        signal, confidence, reason, signal_id = strategy_manager.get_signal("BTC/USD", context)

        assert signal == "BUY"
        assert confidence > 0.5
    
    def test_weighted_vote_mixed(self, strategy_manager):
        """Test weighted vote with mixed signals."""
        strategy_manager.strategies = []
        
        strategy_manager.add_strategy(MockStrategy("s1", "BUY", 0.8))
        strategy_manager.add_strategy(MockStrategy("s2", "SELL", 0.7))
        strategy_manager.add_strategy(MockStrategy("s3", "BUY", 0.9))
        
        context = {'headlines': [], 'price': 50000}
        signal, confidence, reason, signal_id = strategy_manager.get_signal("BTC/USD", context)

        # BUY should win (2 votes with higher confidence)
        assert signal == "BUY"
    
    def test_confidence_threshold(self, strategy_manager):
        """Test minimum confidence threshold filtering."""
        strategy_manager.strategies = []
        strategy_manager.min_confidence = 0.7
        
        # Add strategies with low confidence
        strategy_manager.add_strategy(MockStrategy("s1", "BUY", 0.5))
        strategy_manager.add_strategy(MockStrategy("s2", "BUY", 0.4))
        
        context = {'headlines': [], 'price': 50000}
        signal, confidence, reason, signal_id = strategy_manager.get_signal("BTC/USD", context)
        
        # Should convert to HOLD due to low confidence
        assert signal == "HOLD"
        assert "Low confidence" in reason
    
    def test_highest_confidence_aggregation(self, strategy_manager):
        """Test highest confidence aggregation method."""
        strategy_manager.strategies = []
        strategy_manager.aggregation_method = 'highest_confidence'
        
        strategy_manager.add_strategy(MockStrategy("s1", "BUY", 0.6))
        strategy_manager.add_strategy(MockStrategy("s2", "SELL", 0.9))  # Highest
        strategy_manager.add_strategy(MockStrategy("s3", "HOLD", 0.5))
        
        context = {'headlines': [], 'price': 50000}
        signal, confidence, reason, signal_id = strategy_manager.get_signal("BTC/USD", context)
        
        # Should pick SELL (highest confidence)
        assert signal == "SELL"
        assert "Highest confidence" in reason
    
    def test_unanimous_aggregation_agree(self, strategy_manager):
        """Test unanimous aggregation when all agree."""
        strategy_manager.strategies = []
        strategy_manager.aggregation_method = 'unanimous'
        
        strategy_manager.add_strategy(MockStrategy("s1", "BUY", 0.7))
        strategy_manager.add_strategy(MockStrategy("s2", "BUY", 0.8))
        strategy_manager.add_strategy(MockStrategy("s3", "BUY", 0.9))
        
        context = {'headlines': [], 'price': 50000}
        signal, confidence, reason, signal_id = strategy_manager.get_signal("BTC/USD", context)
        
        assert signal == "BUY"
        assert "All strategies agree" in reason
    
    def test_unanimous_aggregation_disagree(self, strategy_manager):
        """Test unanimous aggregation when strategies disagree."""
        strategy_manager.strategies = []
        strategy_manager.aggregation_method = 'unanimous'
        
        strategy_manager.add_strategy(MockStrategy("s1", "BUY", 0.8))
        strategy_manager.add_strategy(MockStrategy("s2", "SELL", 0.7))
        strategy_manager.add_strategy(MockStrategy("s3", "BUY", 0.9))
        
        context = {'headlines': [], 'price': 50000}
        signal, confidence, reason, signal_id = strategy_manager.get_signal("BTC/USD", context)
        
        # Should default to HOLD when disagreement
        assert signal == "HOLD"
        assert "disagree" in reason.lower()
    
    def test_get_strategy_summary(self, strategy_manager):
        """Test getting strategy summary."""
        summary = strategy_manager.get_strategy_summary()
        
        assert 'total_strategies' in summary
        assert 'enabled_strategies' in summary
        assert 'strategies' in summary
        assert 'config' in summary
        assert isinstance(summary['strategies'], list)
    
    def test_update_config(self, strategy_manager):
        """Test updating configuration."""
        new_config = {
            'min_confidence': 0.7,
            'aggregation_method': 'highest_confidence',
            'strategy_weights': {'sentiment': 1.5}
        }
        
        strategy_manager.update_config(new_config)
        
        assert strategy_manager.min_confidence == 0.7
        assert strategy_manager.aggregation_method == 'highest_confidence'


class TestStrategyManagerSymbolNormalization:
    """Test that strategy manager normalizes symbols before logging."""
    
    def test_signals_logged_with_normalized_symbols(self, sample_context):
        """Test that signals are logged with canonical symbol format."""
        config = {
            "use_technical": True,
            "use_volume": True,
            "use_sentiment": True,
            "logs_dir": "tests/test_logs"
        }
        manager = StrategyManager(config)
        
        # Pass in Kraken format
        result = manager.get_signal("XXBTZUSD", sample_context)
        
        # Logger should receive normalized format
        # Check the last logged signal
        import json
        log_file = Path("tests/test_logs/strategy_signals.jsonl")
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()
                last_signal = json.loads(lines[-1])
                # Should be normalized to BTCUSD, not XXBTZUSD
                assert last_signal["symbol"] == "BTCUSD"
    
    def test_mixed_symbol_formats_all_normalized(self, sample_context):
        """Test that various input formats all normalize correctly."""
        config = {"logs_dir": "tests/test_logs"}
        manager = StrategyManager(config)
        
        test_cases = [
            ("BTC/USD", "BTCUSD"),
            ("XXBTZUSD", "BTCUSD"),
            ("bitcoin", "BTCUSD"),
            ("ETH/USD", "ETHUSD"),
            ("XETHZUSD", "ETHUSD"),
        ]
        
        for input_symbol, expected_normalized in test_cases:
            manager.get_signal(input_symbol, sample_context)
            
            # Verify logged symbol is normalized
            import json
            log_file = Path("tests/test_logs/strategy_signals.jsonl")
            with open(log_file, 'r') as f:
                lines = f.readlines()
                last_signal = json.loads(lines[-1])
                assert last_signal["symbol"] == expected_normalized, \
                    f"Input {input_symbol} should normalize to {expected_normalized}"


@pytest.fixture
def sample_context():
    """Fixture providing sample market context for testing."""
    return {
        "price": 50000.0,
        "volume": 1000000,
        "price_history": [49000, 49500, 50000],
        "volume_history": [900000, 950000, 1000000],
        "headlines": ["Test headline"]
    }
