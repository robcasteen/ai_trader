"""
Tests for BaseStrategy abstract class.
"""

import pytest
from app.strategies.base_strategy import BaseStrategy


class ConcreteStrategy(BaseStrategy):
    """Concrete implementation for testing."""
    
    def get_signal(self, symbol, context):
        return "BUY", 0.8, "Test signal"


class TestBaseStrategy:
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = ConcreteStrategy("test_strategy")
        
        assert strategy.name == "test_strategy"
        assert strategy.enabled is True
        assert strategy.weight == 1.0
    
    def test_enable_disable(self):
        """Test enabling and disabling strategy."""
        strategy = ConcreteStrategy("test")
        
        assert strategy.enabled is True
        
        strategy.disable()
        assert strategy.enabled is False
        
        strategy.enable()
        assert strategy.enabled is True
    
    def test_abstract_method_enforcement(self):
        """Test that BaseStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseStrategy("test")
