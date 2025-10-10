"""
Tests for SentimentStrategy.
"""

import pytest
from unittest.mock import Mock, patch
from app.strategies.sentiment_strategy import SentimentStrategy


@pytest.fixture
def sentiment_strategy():
    return SentimentStrategy()


class TestSentimentStrategy:
    def test_initialization(self, sentiment_strategy):
        """Test sentiment strategy initialization."""
        assert sentiment_strategy.name == "sentiment"
        assert sentiment_strategy.enabled is True
        assert sentiment_strategy.weight == 1.0
    
    def test_no_headlines(self, sentiment_strategy):
        """Test behavior with no headlines."""
        context = {'headlines': []}
        
        signal, confidence, reason = sentiment_strategy.get_signal("BTC/USD", context)
        
        assert signal == "HOLD"
        assert confidence == 0.0
        assert "No news headlines" in reason
    
    def test_single_headline_buy(self, sentiment_strategy):
        """Test single headline resulting in BUY."""
        context = {'headlines': ["Bitcoin surges to all-time high"]}
        
        signal, confidence, reason = sentiment_strategy.get_signal("BTC/USD", context)
        
        assert signal == "BUY"
        assert confidence > 0.5
        assert "Sentiment:" in reason
    
    def test_single_headline_sell(self, sentiment_strategy):
        """Test single headline resulting in SELL."""
        context = {'headlines': ["Bitcoin collapses amid regulatory concerns"]}
        
        signal, confidence, reason = sentiment_strategy.get_signal("BTC/USD", context)
        
        assert signal == "SELL"
        assert confidence > 0.5
        assert "Sentiment:" in reason
    
    def test_multiple_headlines(self, sentiment_strategy):
        """Test multiple headlines aggregation."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"signal": "BUY", "reason": "Positive overall"}'))
        ]
        mock_client.chat.completions.create.return_value = mock_response
        sentiment_strategy.sentiment_model._client = mock_client
        
        context = {'headlines': ["News 1", "News 2", "News 3"]}
        
        signal, confidence, reason = sentiment_strategy.get_signal("BTC/USD", context)
        
        assert signal == "BUY"
        assert confidence > 0.0
        assert "Sentiment:" in reason
    
    def test_confidence_scoring_strong_positive(self, sentiment_strategy):
        """Test high confidence for strong positive keywords."""
        confidence = sentiment_strategy._signal_to_confidence("BUY", "Bitcoin surges to record high")
        assert confidence == 0.8
    
    def test_confidence_scoring_weak_positive(self, sentiment_strategy):
        """Test lower confidence for weak positive."""
        confidence = sentiment_strategy._signal_to_confidence("BUY", "Some positive news")
        assert confidence == 0.6
    
    def test_confidence_scoring_hold(self, sentiment_strategy):
        """Test low confidence for HOLD."""
        confidence = sentiment_strategy._signal_to_confidence("HOLD", "Neutral news")
        assert confidence == 0.3
