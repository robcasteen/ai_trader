from app.client.kraken import KrakenClient
from app.utils.symbol_normalizer import normalize_symbol


def get_top_symbols(limit=10):
    client = KrakenClient()
    tickers = client.get_tickers()
    
    # Filter for USD-based crypto symbols
    symbols = [s for s in tickers if s.endswith("USD") and not s.startswith("Z")]
    
    # Sort by 24h volume
    sorted_symbols = sorted(
        symbols, key=lambda sym: float(tickers[sym].get("volume", 0)), reverse=True
    )
    
    # Normalize to canonical format (XBTCUSD -> BTCUSD)
    normalized_symbols = []
    for symbol in sorted_symbols[:limit]:
        try:
            canonical = normalize_symbol(symbol)
            normalized_symbols.append(canonical)
        except ValueError:
            # Skip unknown symbols
            continue
    
    return normalized_symbols
