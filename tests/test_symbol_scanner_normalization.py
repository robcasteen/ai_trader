"""
Test that symbol_scanner normalizes Kraken symbols to canonical format.
"""
import pytest
from unittest.mock import Mock, patch


class TestSymbolScannerNormalization:
    """Test that get_top_symbols returns canonical symbols."""
    
    def test_kraken_xbtcusd_normalized_to_btcusd(self):
        """Test that Kraken's XBTCUSD is normalized to BTCUSD."""
        # Mock KrakenClient to return Kraken format
        mock_tickers = {
            "XBTCUSD": {"price": 50000.0, "volume": 1000000.0},
            "XETHUSD": {"price": 3000.0, "volume": 500000.0},
        }
        
        with patch("app.logic.symbol_scanner.KrakenClient") as MockClient:
            mock_client = Mock()
            mock_client.get_tickers.return_value = mock_tickers
            MockClient.return_value = mock_client
            
            from app.logic.symbol_scanner import get_top_symbols
            
            symbols = get_top_symbols(limit=2)
            
            # Should return canonical format, not Kraken format
            assert "BTCUSD" in symbols
            assert "ETHUSD" in symbols
            assert "XBTCUSD" not in symbols
            assert "XETHUSD" not in symbols
    
    def test_mixed_kraken_formats_all_normalized(self):
        """Test that all Kraken formats are normalized."""
        mock_tickers = {
            "XBTCUSD": {"price": 50000.0, "volume": 1000000.0},
            "SOLUSD": {"price": 100.0, "volume": 100000.0},
            "XRPUSD": {"price": 2.0, "volume": 50000.0},
            "DOGEUSD": {"price": 0.20, "volume": 25000.0},
        }
        
        with patch("app.logic.symbol_scanner.KrakenClient") as MockClient:
            mock_client = Mock()
            mock_client.get_tickers.return_value = mock_tickers
            MockClient.return_value = mock_client
            
            from app.logic.symbol_scanner import get_top_symbols
            
            symbols = get_top_symbols(limit=10)
            
            # All should be canonical
            assert "BTCUSD" in symbols
            assert "SOLUSD" in symbols
            assert "XRPUSD" in symbols
            assert "DOGEUSD" in symbols
            
    def test_symbols_still_sorted_by_volume(self):
        """Test that symbols are still sorted by volume after normalization."""
        mock_tickers = {
            "XBTCUSD": {"price": 50000.0, "volume": 1000000.0},  # Highest
            "SOLUSD": {"price": 100.0, "volume": 500000.0},      # Second
            "XRPUSD": {"price": 2.0, "volume": 100000.0},        # Third
        }
        
        with patch("app.logic.symbol_scanner.KrakenClient") as MockClient:
            mock_client = Mock()
            mock_client.get_tickers.return_value = mock_tickers
            MockClient.return_value = mock_client
            
            from app.logic.symbol_scanner import get_top_symbols
            
            symbols = get_top_symbols(limit=10)
            
            # Should be sorted by volume
            assert symbols.index("BTCUSD") < symbols.index("SOLUSD")
            assert symbols.index("SOLUSD") < symbols.index("XRPUSD")
