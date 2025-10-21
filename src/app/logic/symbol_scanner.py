"""
Symbol scanner for identifying top trading pairs.
Configurable to use priority symbols or volume-based sorting.
"""

from app.client.kraken import KrakenClient
from app.utils.symbol_normalizer import normalize_symbol

# Default priority symbols (major cryptocurrencies)
DEFAULT_PRIORITY_SYMBOLS = [
    "XXBTZUSD",  # Bitcoin
    "XETHZUSD",  # Ethereum  
    "XXRPZUSD",  # Ripple
    "ADAUSD",    # Cardano
    "SOLUSD",    # Solana
    "DOTUSD",    # Polkadot
    "LINKUSD",   # Chainlink
    "UNIUSD",    # Uniswap
    "DOGEUSD",   # Dogecoin
    "SHIBUSD",   # Shiba Inu
]


def get_top_symbols(limit=10, priority_symbols=None):
    """
    Get top trading symbols from Kraken.
    
    Args:
        limit: Maximum number of symbols to return
        priority_symbols: List of Kraken symbol names to prioritize.
                         If None, uses DEFAULT_PRIORITY_SYMBOLS.
                         If empty list [], uses volume-based sorting.
    
    Returns:
        List of normalized symbols (e.g., ["BTCUSD", "ETHUSD", ...])
    """
    client = KrakenClient()
    tickers = client.get_tickers()
    
    # Determine which symbols to use
    if priority_symbols is None:
        # Use default priority list
        symbols = DEFAULT_PRIORITY_SYMBOLS
    elif priority_symbols == []:
        # Empty list means fall back to volume sorting
        usd_symbols = [s for s in tickers if s.endswith("USD") 
                      and s not in ["ZUSD", "USDTZUSD", "USDCUSD"]]
        symbols = sorted(usd_symbols, 
                        key=lambda s: float(tickers[s].get("volume", 0)), 
                        reverse=True)
    else:
        # Use custom priority list
        symbols = priority_symbols
    
    # Normalize and filter
    normalized_symbols = []
    for symbol in symbols[:limit]:
        try:
            canonical = normalize_symbol(symbol)
            normalized_symbols.append(canonical)
        except ValueError:
            # Skip unknown symbols (not in normalizer)
            continue
    
    return normalized_symbols