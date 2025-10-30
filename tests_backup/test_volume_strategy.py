"""
Tests for VolumeStrategy.
"""

import pytest
from app.strategies.volume_strategy import VolumeStrategy


@pytest.fixture
def volume_strategy():
    return VolumeStrategy()


class TestVolumeStrategy:
    def test_initialization(self, volume_strategy):
        """Test volume strategy initialization."""
        assert volume_strategy.name == "volume"
        assert volume_strategy.enabled is True
        assert volume_strategy.weight == 0.8
    
    def test_no_volume_data(self, volume_strategy):
        """Test behavior with no volume data."""
        context = {}
        
        signal, confidence, reason, signal_id = volume_strategy.get_signal("BTC/USD", context)
        
        assert signal == "HOLD"
        assert confidence == 0.0
        assert "No volume data" in reason
    
    def test_volume_spike_detection(self, volume_strategy):
        """Test volume spike detection."""
        volume_history = [1000] * 20
        current_volume = 2500  # 2.5x average
        
        signal, confidence, reason = volume_strategy._volume_spike_signal(
            current_volume, volume_history
        )
        
        assert signal == "HOLD"
        assert confidence == 0.7
        assert "spike" in reason.lower()
    
    def test_bullish_divergence(self, volume_strategy):
        """Test bullish volume-price divergence (price up + volume up)."""
        price_history = [48000, 48500, 49000, 49500, 50000, 50500, 51000, 51500, 52000, 52500]
        volume_history = [1000, 1000, 1000, 1000, 1000, 1500, 1600, 1700, 1800, 1900]
        current_price = 53000
        current_volume = 2000
        
        signal, confidence, reason = volume_strategy._volume_price_divergence(
            current_price, current_volume, price_history, volume_history
        )
        
        assert signal == "BUY"
        assert confidence > 0.5
        assert "bullish" in reason.lower()
    
    def test_bearish_divergence(self, volume_strategy):
        """Test bearish volume-price divergence (price down + volume up)."""
        price_history = [52000, 51500, 51000, 50500, 50000, 49500, 49000, 48500, 48000, 47500]
        volume_history = [1000, 1000, 1000, 1000, 1000, 1500, 1600, 1700, 1800, 1900]
        current_price = 47000
        current_volume = 2000
        
        signal, confidence, reason = volume_strategy._volume_price_divergence(
            current_price, current_volume, price_history, volume_history
        )
        
        assert signal == "SELL"
        assert confidence > 0.5
        assert "bearish" in reason.lower()
    
    def test_obv_rising(self, volume_strategy):
        """Test rising OBV (accumulation)."""
        price_history = [48000, 48500, 49000, 49500, 50000, 50500]
        volume_history = [1000, 1100, 1200, 1300, 1400, 1500]
        
        signal, confidence, reason = volume_strategy._obv_signal(
            price_history, volume_history
        )
        
        assert signal == "BUY"
        assert "accumulation" in reason.lower() or "rising" in reason.lower()
    
    def test_obv_falling(self, volume_strategy):
        """Test falling OBV (distribution)."""
        price_history = [52000, 51500, 51000, 50500, 50000, 49500]
        volume_history = [1500, 1400, 1300, 1200, 1100, 1000]
        
        signal, confidence, reason = volume_strategy._obv_signal(
            price_history, volume_history
        )
        
        assert signal == "SELL"
        assert "distribution" in reason.lower() or "falling" in reason.lower()
