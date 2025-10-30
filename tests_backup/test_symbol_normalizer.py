"""Tests for symbol normalization utilities."""

import pytest
from app.utils.symbol_normalizer import (
    normalize_symbol,
    to_display_format,
    to_kraken_format,
    extract_base_symbol,
    is_valid_symbol,
    get_all_canonical_symbols,
)


class TestNormalizeSymbol:
    def test_bitcoin_variations(self):
        variations = ["BTC", "BITCOIN", "BTC/USD", "BTCUSD", "XBT", "XBTCUSD", "XXBTZUSD"]
        for var in variations:
            assert normalize_symbol(var) == "BTCUSD", f"Failed for {var}"
    
    def test_ethereum_variations(self):
        variations = ["ETH", "ETHEREUM", "ETH/USD", "ETHUSD", "XETH", "XETHUSD"]
        for var in variations:
            assert normalize_symbol(var) == "ETHUSD", f"Failed for {var}"
    
    def test_case_insensitive(self):
        assert normalize_symbol("btc") == "BTCUSD"
        assert normalize_symbol("BTC") == "BTCUSD"
        assert normalize_symbol("bitcoin") == "BTCUSD"
    
    def test_whitespace_handling(self):
        assert normalize_symbol("  BTC  ") == "BTCUSD"
    
    def test_unknown_symbol_raises_error(self):
        with pytest.raises(ValueError, match="Unknown symbol"):
            normalize_symbol("UNKNOWN")
    
    def test_empty_symbol_raises_error(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_symbol("")


class TestDisplayFormat:
    def test_btc_display(self):
        assert to_display_format("BTCUSD") == "BTC/USD"
    
    def test_unknown_symbol_returns_unchanged(self):
        assert to_display_format("UNKNOWN") == "UNKNOWN"


class TestKrakenFormat:
    def test_btc_kraken_format(self):
        assert to_kraken_format("BTCUSD") == "XBTCUSD"
    
    def test_newer_coins_no_x_prefix(self):
        assert to_kraken_format("SOLUSD") == "SOLUSD"


class TestExtractBaseSymbol:
    def test_extract_btc(self):
        assert extract_base_symbol("BTCUSD") == "BTC"
    
    def test_extract_eth(self):
        assert extract_base_symbol("ETHUSD") == "ETH"


class TestIsValidSymbol:
    def test_valid_symbols(self):
        assert is_valid_symbol("BTC") is True
        assert is_valid_symbol("XBTCUSD") is True
    
    def test_invalid_symbols(self):
        assert is_valid_symbol("UNKNOWN") is False


class TestGetAllCanonicalSymbols:
    def test_returns_list(self):
        symbols = get_all_canonical_symbols()
        assert isinstance(symbols, list)
    
    def test_contains_expected_symbols(self):
        symbols = get_all_canonical_symbols()
        assert "BTCUSD" in symbols
        assert "ETHUSD" in symbols
