"""
Unit tests for SentimentSignal.

Tests cover:
- Fallback keyword-based sentiment detection
- Single headline GPT analysis
- Multi-headline consolidation
- Error handling and fallback behavior
"""

import pytest
import json
from unittest.mock import patch, Mock, MagicMock
from app.logic.sentiment import SentimentSignal


@pytest.fixture
def sentiment_model():
    """Fixture providing a SentimentSignal instance."""
    return SentimentSignal()


class TestFallbackParse:
    def test_positive_keywords(self, sentiment_model):
        """Test detection of positive sentiment keywords."""
        headlines = [
            "Bitcoin surges to new all-time high",
            "ETH soars after major partnership",
            "Bullish rally continues for crypto",
            "Record high adoption of blockchain",
        ]

        for headline in headlines:
            result = sentiment_model._fallback_parse(headline)
            assert result is not None
            signal, reason = result
            assert signal == "BUY"
            assert "positive" in reason.lower()

    def test_negative_keywords(self, sentiment_model):
        """Test detection of negative sentiment keywords."""
        headlines = [
            "Bitcoin plunges after lawsuit",
            "Market collapse due to hack",
            "Bearish drop in crypto prices",
            "Exchange ban causes decline",
        ]

        for headline in headlines:
            result = sentiment_model._fallback_parse(headline)
            assert result is not None
            signal, reason = result
            assert signal == "SELL"
            assert "negative" in reason.lower()

    def test_neutral_headline(self, sentiment_model):
        """Test neutral headlines return None."""
        neutral_headlines = [
            "Bitcoin price remains stable",
            "Crypto market analysis for today",
            "Expert discusses blockchain technology",
        ]

        for headline in neutral_headlines:
            result = sentiment_model._fallback_parse(headline)
            assert result is None

    def test_case_insensitive(self, sentiment_model):
        """Test keyword matching is case-insensitive."""
        result = sentiment_model._fallback_parse("BITCOIN SURGES")
        assert result is not None
        assert result[0] == "BUY"


class TestGetSignal:
    def test_get_signal_gpt_success(self, sentiment_model):
        """Test successful GPT signal generation."""
        with patch.object(sentiment_model, "client") as mock_client:
            mock_response = Mock()
            mock_response.choices = [
                Mock(
                    message=Mock(content='{"signal": "BUY", "reason": "Positive news"}')
                )
            ]
            mock_client.chat.completions.create.return_value = mock_response

            signal, reason = sentiment_model.get_signal(
                "Neutral crypto update", "BTC/USD"
            )

            assert signal == "BUY"
            assert reason == "Positive news"

    def test_get_signal_fallback_triggers_first(self, sentiment_model):
        """Test fallback triggers before GPT for obvious signals."""
        signal, reason = sentiment_model.get_signal(
            "Bitcoin surges to record high", "BTC/USD"
        )

        assert signal == "BUY"
        assert "positive" in reason.lower()

    def test_get_signal_gpt_error(self, sentiment_model):
        """Test error handling when GPT fails."""
        with patch.object(sentiment_model, "client") as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("API timeout")

            signal, reason = sentiment_model.get_signal("Some neutral news", "BTC/USD")

            assert signal == "HOLD"
            assert "error" in reason.lower()

    def test_get_signal_invalid_json(self, sentiment_model):
        """Test handling of invalid JSON from GPT."""
        with patch.object(sentiment_model, "client") as mock_client:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="invalid json"))]
            mock_client.chat.completions.create.return_value = mock_response

            signal, reason = sentiment_model.get_signal("Neutral news", "BTC/USD")

            assert signal == "HOLD"
            assert "error" in reason.lower()

    def test_get_signal_invalid_signal_value(self, sentiment_model):
        """Test normalization of invalid signal values."""
        with patch.object(sentiment_model, "client") as mock_client:
            mock_response = Mock()
            mock_response.choices = [
                Mock(message=Mock(content='{"signal": "INVALID", "reason": "test"}'))
            ]
            mock_client.chat.completions.create.return_value = mock_response

            signal, reason = sentiment_model.get_signal("News", "BTC/USD")

            assert signal == "HOLD"


class TestGetSignals:
    def test_get_signals_empty_list(self, sentiment_model):
        """Test multi-headline with empty list."""
        signal, reason = sentiment_model.get_signals([], "BTC/USD")

        assert signal == "HOLD"
        assert "No headlines" in reason

    def test_get_signals_fallback_sell_priority(self, sentiment_model):
        """Test SELL takes priority in fallback hits."""
        headlines = [
            "Bitcoin surges",  # BUY
            "Market collapses",  # SELL
        ]

        signal, reason = sentiment_model.get_signals(headlines, "BTC/USD")

        assert signal == "SELL"
        assert "negative" in reason.lower()

    def test_get_signals_fallback_buy_over_hold(self, sentiment_model):
        """Test BUY takes priority over HOLD."""
        headlines = [
            "Bitcoin surges",  # BUY
            "Some neutral news",  # No signal
        ]

        signal, reason = sentiment_model.get_signals(headlines, "BTC/USD")

        assert signal == "BUY"

    def test_get_signals_gpt_consolidation(self, sentiment_model):
        """Test GPT consolidation of multiple neutral headlines."""
        with patch.object(sentiment_model, "client") as mock_client:
            mock_response = Mock()
            mock_response.choices = [
                Mock(
                    message=Mock(
                        content='{"signal": "HOLD", "reason": "Mixed sentiment"}'
                    )
                )
            ]
            mock_client.chat.completions.create.return_value = mock_response

            headlines = [
                "Bitcoin price update",
                "Crypto market analysis",
                "Blockchain technology news",
            ]

            signal, reason = sentiment_model.get_signals(headlines, "BTC/USD")

            assert signal == "HOLD"
            assert reason == "Mixed sentiment"

    def test_get_signals_gpt_error(self, sentiment_model):
        """Test error handling in multi-headline consolidation."""
        with patch.object(sentiment_model, "client") as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("API error")

            headlines = ["News 1", "News 2"]
            signal, reason = sentiment_model.get_signals(headlines, "BTC/USD")

            assert signal == "HOLD"
            assert "error" in reason.lower()
