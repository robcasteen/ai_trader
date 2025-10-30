"""
Tests for TechnicalStrategy.
"""

import pytest
from app.strategies.technical_strategy import TechnicalStrategy


@pytest.fixture
def technical_strategy():
    return TechnicalStrategy()


class TestTechnicalStrategy:
    def test_initialization(self, technical_strategy):
        """Test technical strategy initialization."""
        assert technical_strategy.name == "technical"
        assert technical_strategy.enabled is True
        assert technical_strategy.weight == 1.0
    
    def test_no_price_data(self, technical_strategy):
        """Test behavior with no price data."""
        context = {}
        
        signal, confidence, reason, signal_id = technical_strategy.get_signal("BTC/USD", context)
        
        assert signal == "HOLD"
        assert confidence == 0.0
        assert "No price data" in reason
    
    def test_insufficient_history(self, technical_strategy):
        """Test with insufficient price history."""
        context = {
            'price': 50000,
            'price_history': [49000, 49500]  # Too short
        }
        
        signal, confidence, reason, signal_id = technical_strategy.get_signal("BTC/USD", context)
        
        assert signal == "HOLD"
        assert "Insufficient price history" in reason
    
    def test_bullish_sma_signal(self, technical_strategy):
        """Test bullish SMA crossover."""
        # Create uptrend: prices increasing
        price_history = [45000 + i*100 for i in range(50)]
        current_price = 50000
        
        context = {
            'price': current_price,
            'price_history': price_history
        }
        
        signal, confidence, reason, signal_id = technical_strategy.get_signal("BTC/USD", context)
        
        assert signal in ["BUY", "HOLD"]  # Could be BUY or HOLD depending on aggregation
        assert "Technical:" in reason
    
    def test_bearish_sma_signal(self, technical_strategy):
        """Test bearish SMA crossover."""
        # Create downtrend: prices decreasing
        price_history = [55000 - i*100 for i in range(50)]
        current_price = 45000
        
        context = {
            'price': current_price,
            'price_history': price_history
        }
        
        signal, confidence, reason, signal_id = technical_strategy.get_signal("BTC/USD", context)
        
        assert signal in ["SELL", "HOLD"]
        assert "Technical:" in reason
    
    def test_rsi_oversold(self, technical_strategy):
        """Test RSI oversold condition."""
        # Create strong downtrend for oversold RSI
        price_history = [50000 - i*500 for i in range(20)]
        
        signal, confidence = technical_strategy._rsi_signal(price_history)
        
        assert signal == "BUY"
        assert confidence > 0.5
    
    def test_rsi_overbought(self, technical_strategy):
        """Test RSI overbought condition."""
        # Create strong uptrend for overbought RSI
        price_history = [40000 + i*500 for i in range(20)]
        
        signal, confidence = technical_strategy._rsi_signal(price_history)
        
        assert signal == "SELL"
        assert confidence > 0.5
    
    def test_momentum_bullish(self, technical_strategy):
        """Test bullish momentum."""
        price_history = [48000, 48500, 49000, 49500, 50000]
        current_price = 51500  # >3% increase from 5 periods ago
        
        signal, confidence = technical_strategy._momentum_signal(current_price, price_history)
        
        assert signal == "BUY"
        assert confidence == 0.6
    
    def test_momentum_bearish(self, technical_strategy):
        """Test bearish momentum."""
        price_history = [52000, 51500, 51000, 50500, 50000]
        current_price = 48500  # >3% decrease
        
        signal, confidence = technical_strategy._momentum_signal(current_price, price_history)
        
        assert signal == "SELL"
        assert confidence == 0.6
