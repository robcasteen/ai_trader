"""
Unit tests for KrakenClient.

Tests cover:
- Price fetching with valid/invalid symbols
- Balance retrieval 
- Ticker data aggregation
- Error handling for API failures
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.client.kraken import KrakenClient


@pytest.fixture
def kraken_client():
    """Fixture providing a KrakenClient instance with mocked API."""
    with patch('app.client.kraken.krakenex.API') as mock_api_class:
        client = KrakenClient()
        client.api = Mock()
        yield client


class TestGetPrice:
    def test_get_price_success(self, kraken_client):
        """Test successful price retrieval."""
        kraken_client.api.query_public.return_value = {
            "result": {
                "XXBTZUSD": {"c": ["50000.00", "1.5"]}
            }
        }
        
        price = kraken_client.get_price("BTC/USD")
        assert price == 50000.0
        kraken_client.api.query_public.assert_called_once_with(
            "Ticker", {"pair": "BTC/USD"}
        )

    def test_get_price_api_error(self, kraken_client):
        """Test price retrieval when API raises exception."""
        kraken_client.api.query_public.side_effect = Exception("API error")
        
        price = kraken_client.get_price("BTC/USD")
        assert price == 0.0

    def test_get_price_malformed_response(self, kraken_client):
        """Test price retrieval with malformed API response."""
        kraken_client.api.query_public.return_value = {"result": {}}
        
        price = kraken_client.get_price("BTC/USD")
        assert price == 0.0

    def test_get_price_invalid_float(self, kraken_client):
        """Test price retrieval when price cannot be converted to float."""
        kraken_client.api.query_public.return_value = {
            "result": {"XXBTZUSD": {"c": ["invalid", "1.5"]}}
        }
        
        price = kraken_client.get_price("BTC/USD")
        assert price == 0.0


class TestGetBalance:
    def test_get_balance_success(self, kraken_client):
        """Test successful balance retrieval."""
        kraken_client.api.query_private.return_value = {
            "result": {"ZUSD": "10000.50"}
        }
        
        balance = kraken_client.get_balance("ZUSD")
        assert balance == 10000.50
        kraken_client.api.query_private.assert_called_once_with("Balance")

    def test_get_balance_asset_not_found(self, kraken_client):
        """Test balance retrieval for non-existent asset."""
        kraken_client.api.query_private.return_value = {
            "result": {"ZUSD": "1000"}
        }
        
        balance = kraken_client.get_balance("ZEUR")
        assert balance == 0.0

    def test_get_balance_api_error(self, kraken_client):
        """Test balance retrieval when API raises exception."""
        kraken_client.api.query_private.side_effect = Exception("Auth error")
        
        balance = kraken_client.get_balance("ZUSD")
        assert balance == 0.0

    def test_get_balance_default_asset(self, kraken_client):
        """Test balance retrieval with default ZUSD asset."""
        kraken_client.api.query_private.return_value = {
            "result": {"ZUSD": "5000"}
        }
        
        balance = kraken_client.get_balance()
        assert balance == 5000.0


class TestGetTickers:
    def test_get_tickers_success(self, kraken_client):
        """Test successful ticker data retrieval."""
        kraken_client.api.query_public.return_value = {
            "result": {
                "XXBTZUSD": {"c": ["50000", "1"], "v": ["10", "100"]},
                "XETHZUSD": {"c": ["3000", "2"], "v": ["20", "200"]}
            }
        }
        
        tickers = kraken_client.get_tickers()
        
        assert len(tickers) == 2
        assert tickers["XXBTZUSD"]["price"] == 50000.0
        assert tickers["XXBTZUSD"]["volume"] == 100.0
        assert tickers["XETHZUSD"]["price"] == 3000.0
        assert tickers["XETHZUSD"]["volume"] == 200.0

    def test_get_tickers_empty_result(self, kraken_client):
        """Test ticker retrieval with empty result."""
        kraken_client.api.query_public.return_value = {"result": {}}
        
        tickers = kraken_client.get_tickers()
        assert tickers == {}

    def test_get_tickers_api_error(self, kraken_client):
        """Test ticker retrieval when API raises exception."""
        kraken_client.api.query_public.side_effect = Exception("Network error")
        
        tickers = kraken_client.get_tickers()
        assert tickers == {}

    def test_get_tickers_invalid_data(self, kraken_client):
        """Test ticker retrieval with invalid numeric data."""
        kraken_client.api.query_public.return_value = {
            "result": {
                "XXBTZUSD": {"c": ["invalid", "1"], "v": ["10", "bad"]}
            }
        }
        
        # Should return empty dict due to conversion error
        tickers = kraken_client.get_tickers()
        assert tickers == {}