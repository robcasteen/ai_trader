"""
Real-time market data collector with in-memory storage.
Polls Kraken every 60s, stores last 100 data points per symbol.
"""

import time
import logging
from collections import defaultdict, deque
from threading import Thread, Lock
from datetime import datetime
from app.client.kraken import KrakenClient
from app.logic.symbol_scanner import DEFAULT_PRIORITY_SYMBOLS
from app.utils.symbol_normalizer import normalize_symbol


class DataCollector:
    def __init__(self, max_history=100, poll_interval=60):
        self.client = KrakenClient()
        self.max_history = max_history
        self.poll_interval = poll_interval
        
        # Thread-safe storage: symbol -> deque of (timestamp, price, volume)
        self.price_history = defaultdict(lambda: deque(maxlen=max_history))
        self.volume_history = defaultdict(lambda: deque(maxlen=max_history))
        self.lock = Lock()
        
        self.running = False
        self.thread = None
    
    def start(self):
        """Start background collection thread."""
        if self.running:
            return

        # Backfill historical data before starting continuous collection
        logging.info("[DataCollector] Backfilling historical data from exchange...")
        self._backfill_history()

        self.running = True
        self.thread = Thread(target=self._collect_loop, daemon=True)
        self.thread.start()
        logging.info("[DataCollector] Started background collection")
    
    def stop(self):
        """Stop collection thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logging.info("[DataCollector] Stopped")
    
    def _collect_loop(self):
        """Background loop: fetch data every poll_interval seconds."""
        while self.running:
            try:
                self._collect_snapshot()
            except Exception as e:
                logging.error(f"[DataCollector] Error: {e}")
            
            time.sleep(self.poll_interval)
    
    def _collect_snapshot(self):
        """Fetch current prices/volumes for all symbols."""
        tickers = self.client.get_tickers()
        timestamp = datetime.now()
        
        with self.lock:
            for symbol, data in tickers.items():
                # Only track USD pairs
                if not symbol.endswith("USD"):
                    continue
                
                price = data.get("price", 0)
                volume = data.get("volume", 0)
                
                if price > 0:
                    self.price_history[symbol].append(price)
                    self.volume_history[symbol].append(volume)
        
        logging.info(f"[DataCollector] Updated {len(tickers)} symbols")
    
    def get_price_history(self, symbol, limit=None):
        """Get price history for symbol (most recent first)."""
        with self.lock:
            history = list(self.price_history.get(symbol, []))
            if limit:
                history = history[-limit:]
            return history
    
    def get_volume_history(self, symbol, limit=None):
        """Get volume history for symbol."""
        with self.lock:
            history = list(self.volume_history.get(symbol, []))
            if limit:
                history = history[-limit:]
            return history
    
    def get_current_price(self, symbol):
        """Get most recent price (fallback to API if no history)."""
        with self.lock:
            history = self.price_history.get(symbol, [])
            if history:
                return history[-1]
        
        # Fallback to live API call
        return self.client.get_price(symbol)
    
    def get_stats(self):
        """Get collection statistics."""
        with self.lock:
            return {
                "symbols_tracked": len(self.price_history),
                "avg_data_points": sum(len(h) for h in self.price_history.values()) / max(len(self.price_history), 1)
            }

    def _backfill_history(self):
        """Backfill historical OHLC data from exchange for priority symbols."""
        # Use the same priority symbols as the scanner
        symbols_to_backfill = DEFAULT_PRIORITY_SYMBOLS

        for symbol in symbols_to_backfill:
            try:
                # Fetch 1-minute candles (up to max_history candles)
                ohlc_data = self.client.get_ohlc(symbol, interval=1)

                if not ohlc_data:
                    logging.warning(f"[DataCollector] No OHLC data for {symbol}")
                    continue

                # Extract prices and volumes from OHLC data
                # Format: [timestamp, open, high, low, close, vwap, volume, count]
                prices = []
                volumes = []

                for candle in ohlc_data[-self.max_history:]:  # Get last max_history candles
                    close_price = float(candle[4])  # Close price
                    volume = float(candle[6])       # Volume
                    prices.append(close_price)
                    volumes.append(volume)

                # Store in deques under both Kraken format and normalized format
                with self.lock:
                    self.price_history[symbol] = deque(prices, maxlen=self.max_history)
                    self.volume_history[symbol] = deque(volumes, maxlen=self.max_history)

                    # Also store under normalized symbol for strategies
                    try:
                        normalized = normalize_symbol(symbol)
                        if normalized != symbol:
                            self.price_history[normalized] = deque(prices, maxlen=self.max_history)
                            self.volume_history[normalized] = deque(volumes, maxlen=self.max_history)
                    except ValueError:
                        pass  # Symbol normalization failed, skip normalized storage

                logging.info(f"[DataCollector] Backfilled {len(prices)} data points for {symbol}")

            except Exception as e:
                logging.error(f"[DataCollector] Failed to backfill {symbol}: {e}")


# Global singleton
data_collector = DataCollector()
