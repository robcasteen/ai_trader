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

    def get_balance(self, asset=None):
        """
        Get balance from Kraken.

        Args:
            asset: If specified, returns float for that single asset. If None, returns full dict.

        Returns:
            dict or float depending on asset parameter
        """
        try:
            result = self.api.query_private("Balance")
            balances = result.get("result", {})

            import logging
            logging.info(f"[KrakenClient] Balance API response keys: {list(balances.keys())}")
            logging.info(f"[KrakenClient] Full balances: {balances}")

            if asset:
                # Try multiple USD key variations
                for key in [asset, "USD", "ZUSD", "USDT", "USDC"]:
                    if key in balances:
                        value = float(balances[key])
                        logging.info(f"[KrakenClient] Found balance under key '{key}': ${value:.2f}")
                        return value
                logging.warning(f"[KrakenClient] No USD balance found. Requested: {asset}")
                return 0.0
            else:
                # Return full dict (for dashboard)
                return balances
        except Exception as e:
            import logging
            logging.error(f"[KrakenClient] Balance error: {e}")
            return 0.0 if asset else {}

    def get_tickers(self):
        try:
            result = self.api.query_public("Ticker")
            data = result["result"]
            formatted = {}
            for k, v in data.items():
                formatted[k] = {"price": float(v["c"][0]), "volume": float(v["v"][1])}
            return formatted
        except Exception:
            return {}

    def get_ohlc(self, symbol, interval=1, since=None):
        """
        Get OHLC (candlestick) data from Kraken.

        Args:
            symbol: Trading pair (e.g., "XXBTZUSD" or "BTCUSD")
            interval: Timeframe in minutes (1, 5, 15, 30, 60, 240, 1440, 10080, 21600)
            since: Return data since given timestamp (optional)

        Returns:
            List of OHLC data points: [timestamp, open, high, low, close, vwap, volume, count]
        """
        try:
            params = {"pair": symbol, "interval": interval}
            if since:
                params["since"] = since

            result = self.api.query_public("OHLC", params)

            if result.get("error"):
                import logging
                logging.error(f"[KrakenClient] OHLC error: {result['error']}")
                return []

            data = result.get("result", {})
            # Get the pair key (Kraken returns the normalized pair name)
            pair_key = next((k for k in data.keys() if k != "last"), None)

            if not pair_key:
                return []

            ohlc_data = data[pair_key]

            # Format: [timestamp, open, high, low, close, vwap, volume, count]
            return ohlc_data

        except Exception as e:
            import logging
            logging.error(f"[KrakenClient] Failed to fetch OHLC for {symbol}: {e}")
            return []
