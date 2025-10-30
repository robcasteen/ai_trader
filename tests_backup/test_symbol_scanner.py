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

@pytest.fixture
def mock_kraken_client():
    """Mock KrakenClient for testing"""
    with patch('app.logic.symbol_scanner.KrakenClient') as mock:
        yield mock
# tests/test_symbol_scanner.py

class TestGetTopSymbols:
    def test_basic_filtering_and_sorting(self, mock_kraken_client):
        """Test that symbols are filtered, sorted by volume, and normalized"""
        mock_tickers = {
            "XXBTZUSD": {"volume": 1000},  # BTC - highest volume
            "XETHZUSD": {"volume": 800},   # ETH
            "XXRPZUSD": {"volume": 600},   # XRP
            "ZUSDXXBT": {"volume": 500},   # Reverse pair - should be filtered
            "ZEURXETH": {"volume": 400},   # EUR pair - should be filtered
        }
        mock_kraken_client.return_value.get_tickers.return_value = mock_tickers
        
        result = get_top_symbols(priority_symbols=[], limit=3)
        
        # Should return normalized symbols, sorted by volume
        assert len(result) == 3
        assert result[0] == "BTCUSD"   # Normalized from XXBTZUSD
        assert result[1] == "ETHUSD"   # Normalized from XETHZUSD
        assert result[2] == "XRPUSD"   # Normalized from XXRPZUSD

    def test_limit_enforcement(self, mock_kraken_client):
        """Test that limit parameter works correctly"""
        mock_tickers = {
            "XXBTZUSD": {"volume": 1000},
            "XETHZUSD": {"volume": 900},
            "XSOLUSDT": {"volume": 800},  # Note: USDT not USD - will be filtered
            "XXRPZUSD": {"volume": 700},
            "ADAUSD": {"volume": 600},
            "DOTUSD": {"volume": 500},
            "LINKUSD": {"volume": 400},
        }
        mock_kraken_client.return_value.get_tickers.return_value = mock_tickers
        
        result = get_top_symbols(priority_symbols=[], limit=5)
        
        assert len(result) == 5
        assert result[0] == "BTCUSD"
        assert result[4] == "DOTUSD"

    def test_default_limit(self, mock_kraken_client):
        """Test default limit of 10 symbols"""
        # Create 15 valid USD symbols
        mock_tickers = {
            "XXBTZUSD": {"volume": 1500},
            "XETHZUSD": {"volume": 1400},
            "XXRPZUSD": {"volume": 1300},
            "ADAUSD": {"volume": 1200},
            "SOLUSD": {"volume": 1100},
            "DOTUSD": {"volume": 1000},
            "LINKUSD": {"volume": 900},
            "UNIUSD": {"volume": 800},
            "DOGEUSD": {"volume": 700},
            "MATICUSD": {"volume": 600},
            "AVAXUSD": {"volume": 500},
            "ATOMUSD": {"volume": 400},
            "LTCUSD": {"volume": 300},
            "XLMUSD": {"volume": 200},
            "AAVEUSD": {"volume": 100},
        }
        mock_kraken_client.return_value.get_tickers.return_value = mock_tickers
        
        result = get_top_symbols()  # Should default to 10
        
        assert len(result) == 10
        assert result[0] == "BTCUSD"
        assert len(result) == 10  # Check limit works

    def test_volume_sorting_descending(self, mock_kraken_client):
        """Test that symbols are sorted by volume in descending order"""
        mock_tickers = {
            "ADAUSD": {"volume": 500},     # Should be 3rd
            "XXBTZUSD": {"volume": 1000},  # Should be 1st (highest)
            "XETHZUSD": {"volume": 750},   # Should be 2nd
            "LINKUSD": {"volume": 250},    # Should be 4th (lowest)
        }
        mock_kraken_client.return_value.get_tickers.return_value = mock_tickers
        
        result = get_top_symbols(priority_symbols=[], limit=4)
        
        assert len(result) == 4
        assert result[0] == "BTCUSD"   # 1000 volume
        assert result[1] == "ETHUSD"   # 750 volume
        assert result[2] == "ADAUSD"   # 500 volume
        assert result[3] == "LINKUSD"  # 250 volume