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


# Global singleton
data_collector = DataCollector()
