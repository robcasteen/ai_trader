import os
import krakenex
from dotenv import load_dotenv

load_dotenv()


class KrakenClient:
    def __init__(self):
        self.api = krakenex.API(
            key=os.getenv("KRAKEN_API_KEY"), secret=os.getenv("KRAKEN_API_SECRET")
        )

    def get_price(self, symbol):
        try:
            result = self.api.query_public("Ticker", {"pair": symbol})
            pair_data = result["result"]
            key = next(iter(pair_data))
            return float(pair_data[key]["c"][0])
        except Exception:
            return 0.0

    def get_balance(self, asset="ZUSD"):
        try:
            result = self.api.query_private("Balance")
            return float(result["result"].get(asset, 0))
        except Exception:
            return 0.0

    def get_tickers(self):
        try:
            result = self.api.query_public("Ticker", {"pair": "all"})
            data = result["result"]
            formatted = {}
            for k, v in data.items():
                formatted[k] = {"price": float(v["c"][0]), "volume": float(v["v"][1])}
            return formatted
        except Exception:
            return {}
