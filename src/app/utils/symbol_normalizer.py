"""
Symbol normalization utilities for consistent symbol handling across the application.

Canonical format: BTCUSD, ETHUSD, SOLUSD (no slashes, no X prefix)
"""

# Mapping of all known symbol variations to canonical format
SYMBOL_MAPPINGS = {
    # Bitcoin variations
    "BTC": "BTCUSD",
    "BITCOIN": "BTCUSD",
    "BTC/USD": "BTCUSD",
    "BTCUSD": "BTCUSD",
    "XBT": "BTCUSD",
    "XBTUSD": "BTCUSD",
    "XBTCUSD": "BTCUSD",
    "XXBTZUSD": "BTCUSD",
    
    # Ethereum variations
    "ETH": "ETHUSD",
    "ETHEREUM": "ETHUSD",
    "ETH/USD": "ETHUSD",
    "ETHUSD": "ETHUSD",
    "XETH": "ETHUSD",
    "XETHUSD": "ETHUSD",
    
    # Solana variations
    "SOL": "SOLUSD",
    "SOLANA": "SOLUSD",
    "SOL/USD": "SOLUSD",
    "SOLUSD": "SOLUSD",
    
    # XRP (Ripple) variations
    "XRP": "XRPUSD",
    "RIPPLE": "XRPUSD",
    "XRP/USD": "XRPUSD",
    "XRPUSD": "XRPUSD",
    "XXRPZUSD": "XRPUSD",
    
    # Dogecoin variations
    "DOGE": "DOGEUSD",
    "DOGECOIN": "DOGEUSD",
    "DOGE/USD": "DOGEUSD",
    "DOGEUSD": "DOGEUSD",
    "XDOGZUSD": "DOGEUSD",
    
    # Cardano variations
    "ADA": "ADAUSD",
    "CARDANO": "ADAUSD",
    "ADA/USD": "ADAUSD",
    "ADAUSD": "ADAUSD",
    
    # Polkadot variations
    "DOT": "DOTUSD",
    "POLKADOT": "DOTUSD",
    "DOT/USD": "DOTUSD",
    "DOTUSD": "DOTUSD",
    
    # Chainlink variations
    "LINK": "LINKUSD",
    "CHAINLINK": "LINKUSD",
    "LINK/USD": "LINKUSD",
    "LINKUSD": "LINKUSD",
    
    # Uniswap variations
    "UNI": "UNIUSD",
    "UNISWAP": "UNIUSD",
    "UNI/USD": "UNIUSD",
    "UNIUSD": "UNIUSD",
    
    # Shiba Inu variations
    "SHIB": "SHIBUSD",
    "SHIBA": "SHIBUSD",
    "SHIB/USD": "SHIBUSD",
    "SHIBUSD": "SHIBUSD",
    
    # Litecoin variations
    "LTC": "LTCUSD",
    "LITECOIN": "LTCUSD",
    "LTC/USD": "LTCUSD",
    "LTCUSD": "LTCUSD",
    "XLTCZUSD": "LTCUSD",
    
    # Stellar variations
    "XLM": "XLMUSD",
    "STELLAR": "XLMUSD",
    "XLM/USD": "XLMUSD",
    "XLMUSD": "XLMUSD",
    "XXLMZUSD": "XLMUSD",
    
    # Cosmos variations
    "ATOM": "ATOMUSD",
    "COSMOS": "ATOMUSD",
    "ATOM/USD": "ATOMUSD",
    "ATOMUSD": "ATOMUSD",
    
    # Aave variations
    "AAVE": "AAVEUSD",
    "AAVE/USD": "AAVEUSD",
    "AAVEUSD": "AAVEUSD",
    
    # Polygon variations
    "MATIC": "MATICUSD",
    "POLYGON": "MATICUSD",
    "MATIC/USD": "MATICUSD",
    "MATICUSD": "MATICUSD",
    
    # Avalanche variations
    "AVAX": "AVAXUSD",
    "AVALANCHE": "AVAXUSD",
    "AVAX/USD": "AVAXUSD",
    "AVAXUSD": "AVAXUSD",
}

# Reverse mapping: canonical -> display format
DISPLAY_FORMAT = {
    "BTCUSD": "BTC/USD",
    "ETHUSD": "ETH/USD",
    "SOLUSD": "SOL/USD",
    "XRPUSD": "XRP/USD",
    "DOGEUSD": "DOGE/USD",
    "ADAUSD": "ADA/USD",
    "DOTUSD": "DOT/USD",
    "LINKUSD": "LINK/USD",
    "UNIUSD": "UNI/USD",
    "SHIBUSD": "SHIB/USD",
    "LTCUSD": "LTC/USD",
    "XLMUSD": "XLM/USD",
    "ATOMUSD": "ATOM/USD",
    "AAVEUSD": "AAVE/USD",
    "MATICUSD": "MATIC/USD",
    "AVAXUSD": "AVAX/USD",
}


def normalize_symbol(symbol: str) -> str:
    """
    Convert any symbol variation to canonical format.
    
    Args:
        symbol: Any symbol format (BTC, BTC/USD, XBTCUSD, etc.)
        
    Returns:
        Canonical symbol (BTCUSD, ETHUSD, etc.)
        
    Raises:
        ValueError: If symbol is not recognized
    """
    if not symbol:
        raise ValueError("Symbol cannot be empty")
    
    symbol_upper = symbol.upper().strip()
    
    if symbol_upper in SYMBOL_MAPPINGS:
        return SYMBOL_MAPPINGS[symbol_upper]
    
    if symbol_upper.endswith("USDT"):
        base = symbol_upper[:-4]
        candidate = f"{base}USD"
        if candidate in SYMBOL_MAPPINGS:
            return SYMBOL_MAPPINGS[candidate]
    
    raise ValueError(f"Unknown symbol: {symbol}. Add it to SYMBOL_MAPPINGS.")


def to_display_format(canonical_symbol: str) -> str:
    """Convert canonical symbol to human-readable display format."""
    return DISPLAY_FORMAT.get(canonical_symbol, canonical_symbol)


def to_kraken_format(canonical_symbol: str) -> str:
    """Convert canonical symbol to Kraken API format."""
    kraken_map = {
        "BTCUSD": "XBTCUSD",
        "ETHUSD": "XETHUSD",
        "SOLUSD": "SOLUSD",
        "XRPUSD": "XRPUSD",
        "DOGEUSD": "DOGEUSD",
        "ADAUSD": "ADAUSD",
        "DOTUSD": "DOTUSD",
        "LINKUSD": "LINKUSD",
        "UNIUSD": "UNIUSD",
        "SHIBUSD": "SHIBUSD",
        "LTCUSD": "LTCUSD",
        "XLMUSD": "XLMUSD",
        "ATOMUSD": "ATOMUSD",
        "AAVEUSD": "AAVEUSD",
        "MATICUSD": "MATICUSD",
        "AVAXUSD": "AVAXUSD",
    }
    return kraken_map.get(canonical_symbol, canonical_symbol)


def extract_base_symbol(canonical_symbol: str) -> str:
    """Extract the base currency from canonical symbol."""
    if canonical_symbol.endswith("USD"):
        return canonical_symbol[:-3]
    return canonical_symbol


def is_valid_symbol(symbol: str) -> bool:
    """Check if a symbol can be normalized."""
    try:
        normalize_symbol(symbol)
        return True
    except ValueError:
        return False


def get_all_canonical_symbols() -> list[str]:
    """Get list of all supported canonical symbols."""
    return list(set(SYMBOL_MAPPINGS.values()))
