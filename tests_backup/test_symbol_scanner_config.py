"""
Tests for configurable symbol scanner priority.
"""

import pytest
from unittest.mock import patch, Mock
from app.logic.symbol_scanner import get_top_symbols, DEFAULT_PRIORITY_SYMBOLS


class TestSymbolScannerConfig:
    """Test configurable priority symbols in scanner."""
    
    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_uses_default_priority_when_none_provided(self, mock_client):
        """When no priority_symbols provided, should use DEFAULT_PRIORITY_SYMBOLS."""
        mock_tickers = {
            "XXBTZUSD": {"volume": 1000},
            "XETHZUSD": {"volume": 900},
            "SHIBUSD": {"volume": 800},
            "MOGUSD": {"volume": 999999999},  # High volume memecoin
        }
        mock_client.return_value.get_tickers.return_value = mock_tickers
        
        result = get_top_symbols(limit=3)
        
        # Should return priority symbols (BTC, ETH, SHIB), not MOG despite volume
        assert "BTCUSD" in result
        assert "ETHUSD" in result
        # MOG not in normalizer, so won't appear
        assert "MOGUSD" not in result
    
    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_uses_custom_priority_when_provided(self, mock_client):
        """When priority_symbols provided, should use those."""
        mock_tickers = {
            "ADAUSD": {"volume": 500},
            "SOLUSD": {"volume": 400},
            "XXBTZUSD": {"volume": 1000},
        }
        mock_client.return_value.get_tickers.return_value = mock_tickers
        
        # Custom priority: only ADA and SOL
        custom_priority = ["ADAUSD", "SOLUSD"]
        result = get_top_symbols(limit=5, priority_symbols=custom_priority)
        
        assert "ADAUSD" in result
        assert "SOLUSD" in result
        # BTC not in priority list, so shouldn't appear even with higher volume
        assert "BTCUSD" not in result
    
    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_empty_priority_list_uses_volume_sorting(self, mock_client):
        """When priority_symbols=[], should fall back to volume sorting."""
        mock_tickers = {
            "SHIBUSD": {"volume": 1000},  # Highest volume, in normalizer
            "ADAUSD": {"volume": 900},
            "SOLUSD": {"volume": 800},
        }
        mock_client.return_value.get_tickers.return_value = mock_tickers
        
        # Empty list means "use volume sorting"
        result = get_top_symbols(limit=3, priority_symbols=[])
        
        # Should be sorted by volume
        assert result[0] == "SHIBUSD"
        assert result[1] == "ADAUSD"
        assert result[2] == "SOLUSD"
    
    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_skips_unknown_symbols_in_priority_list(self, mock_client):
        """Unknown symbols in priority list should be skipped."""
        mock_tickers = {
            "ADAUSD": {"volume": 500},
            "FAKEUSD": {"volume": 1000},  # Not in normalizer
        }
        mock_client.return_value.get_tickers.return_value = mock_tickers
        
        custom_priority = ["FAKEUSD", "ADAUSD"]
        result = get_top_symbols(limit=5, priority_symbols=custom_priority)
        
        # FAKEUSD should be skipped (not in normalizer)
        assert "FAKEUSD" not in result
        assert "ADAUSD" in result
    
    @patch('app.logic.symbol_scanner.KrakenClient')
    def test_respects_limit_parameter(self, mock_client):
        """Should respect limit even with priority list."""
        mock_tickers = {
            "XXBTZUSD": {"volume": 1000},
            "XETHZUSD": {"volume": 900},
            "ADAUSD": {"volume": 800},
            "SOLUSD": {"volume": 700},
        }
        mock_client.return_value.get_tickers.return_value = mock_tickers
        
        result = get_top_symbols(limit=2)
        
        # Should only return 2 symbols even though more are available
        assert len(result) <= 2
    
    def test_default_priority_symbols_exist(self):
        """DEFAULT_PRIORITY_SYMBOLS should be defined and non-empty."""
        assert DEFAULT_PRIORITY_SYMBOLS is not None
        assert len(DEFAULT_PRIORITY_SYMBOLS) > 0
        assert isinstance(DEFAULT_PRIORITY_SYMBOLS, list)
        
        # Should contain major cryptos
        assert any('BTC' in s or 'XBT' in s for s in DEFAULT_PRIORITY_SYMBOLS)
        assert any('ETH' in s for s in DEFAULT_PRIORITY_SYMBOLS)
