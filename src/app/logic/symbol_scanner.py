from app.client.kraken import KrakenClient


def get_top_symbols(limit=10):
    client = KrakenClient()
    tickers = client.get_tickers()

    # Filter for USD-based crypto symbols
    symbols = [s for s in tickers if s.endswith("USD") and not s.startswith("Z")]

    # Sort by 24h volume
    sorted_symbols = sorted(
        symbols, key=lambda sym: float(tickers[sym].get("volume", 0)), reverse=True
    )

    return sorted_symbols[:limit]
