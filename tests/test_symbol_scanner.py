"""
Unit tests for symbol_scanner module.

Tests cover:
- Symbol filtering (USD-based, non-Z prefixed)
- Volume-based sorting
- Limit enforcement
- Error handling
"""

import pytest
from unittest.mock import Mock, patch
from app.logic.symbol_scanner import get_top_symbols


class TestGetTopSymbols:
    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_basic_filtering_and_sorting(self, mock_client_class):
        """Test basic symbol filtering and volume sorting."""
        mock_client = Mock()
        mock_client.get_tickers.return_value = {
            "XXBTZUSD": {"price": 50000, "volume": 1000},
            "XETHZUSD": {"price": 3000, "volume": 500},
            "SOLUSD": {"price": 100, "volume": 2000},
            "ADAUSD": {"price": 0.5, "volume": 300},
            "ZUSDEUR": {"price": 1.1, "volume": 5000},  # Should be filtered (starts with Z)
        }
        mock_client_class.return_value = mock_client
        
        result = get_top_symbols(limit=10)
        
        # Should exclude ZUSDEUR
        assert "ZUSDEUR" not in result
        
        # Should be sorted by volume (highest first)
        assert result[0] == "SOLUSD"  # volume 2000
        assert result[1] == "XXBTZUSD"  # volume 1000
        assert result[2] == "XETHZUSD"  # volume 500
        assert result[3] == "ADAUSD"  # volume 300

    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_limit_enforcement(self, mock_client_class):
        """Test that limit parameter is respected."""
        mock_client = Mock()
        tickers = {
            f"SYM{i}USD": {"price": 100, "volume": 1000 - i}
            for i in range(20)
        }
        mock_client.get_tickers.return_value = tickers
        mock_client_class.return_value = mock_client
        
        result = get_top_symbols(limit=5)
        
        assert len(result) == 5

    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_default_limit(self, mock_client_class):
        """Test default limit of 10."""
        mock_client = Mock()
        tickers = {
            f"SYM{i}USD": {"price": 100, "volume": 1000 - i}
            for i in range(20)
        }
        mock_client.get_tickers.return_value = tickers
        mock_client_class.return_value = mock_client
        
        result = get_top_symbols()
        
        assert len(result) == 10

    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_only_usd_symbols(self, mock_client_class):
        """Test that only USD-based symbols are returned."""
        mock_client = Mock()
        mock_client.get_tickers.return_value = {
            "BTCUSD": {"price": 50000, "volume": 1000},
            "BTCEUR": {"price": 45000, "volume": 2000},
            "ETHGBP": {"price": 2500, "volume": 1500},
            "ETHUSD": {"price": 3000, "volume": 500},
        }
        mock_client_class.return_value = mock_client
        
        result = get_top_symbols(limit=10)
        
        assert "BTCUSD" in result
        assert "ETHUSD" in result
        assert "BTCEUR" not in result
        assert "ETHGBP" not in result

    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_filters_z_prefix_symbols(self, mock_client_class):
        """Test that Z-prefixed symbols are filtered."""
        mock_client = Mock()
        mock_client.get_tickers.return_value = {
            "BTCUSD": {"price": 50000, "volume": 1000},
            "ZUSDBTC": {"price": 0.00002, "volume": 5000},
            "ZEURUSD": {"price": 1.1, "volume": 3000},
        }
        mock_client_class.return_value = mock_client
        
        result = get_top_symbols(limit=10)
        
        assert "BTCUSD" in result
        assert "ZUSDBTC" not in result
        assert "ZEURUSD" not in result

    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_empty_tickers(self, mock_client_class):
        """Test handling of empty ticker data."""
        mock_client = Mock()
        mock_client.get_tickers.return_value = {}
        mock_client_class.return_value = mock_client
        
        result = get_top_symbols(limit=10)
        
        assert result == []

    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_missing_volume_data(self, mock_client_class):
        """Test handling of missing volume data."""
        mock_client = Mock()
        mock_client.get_tickers.return_value = {
            "BTCUSD": {"price": 50000},  # No volume
            "ETHUSD": {"price": 3000, "volume": 500},
        }
        mock_client_class.return_value = mock_client
        
        result = get_top_symbols(limit=10)
        
        # Should handle missing volume gracefully (defaults to 0)
        assert len(result) == 2

    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_volume_sorting_descending(self, mock_client_class):
        """Test that symbols are sorted by volume in descending order."""
        mock_client = Mock()
        mock_client.get_tickers.return_value = {
            "SYMBOL1USD": {"price": 100, "volume": 100},
            "SYMBOL2USD": {"price": 100, "volume": 500},
            "SYMBOL3USD": {"price": 100, "volume": 300},
            "SYMBOL4USD": {"price": 100, "volume": 700},
        }
        mock_client_class.return_value = mock_client
        
        result = get_top_symbols(limit=10)
        
        # Verify descending order
        assert result[0] == "SYMBOL4USD"  # 700
        assert result[1] == "SYMBOL2USD"  # 500
        assert result[2] == "SYMBOL3USD"  # 300
        assert result[3] == "SYMBOL1USD"  # 100

    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_fewer_symbols_than_limit(self, mock_client_class):
        """Test when available symbols are fewer than limit."""
        mock_client = Mock()
        mock_client.get_tickers.return_value = {
            "BTCUSD": {"price": 50000, "volume": 1000},
            "ETHUSD": {"price": 3000, "volume": 500},
        }
        mock_client_class.return_value = mock_client
        
        result = get_top_symbols(limit=10)
        
        assert len(result) == 2