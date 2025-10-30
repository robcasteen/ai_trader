"""
Historical Data Fetcher for Backtesting.

Fetches OHLCV data from Kraken API and caches it in the database for backtesting.
Supports incremental fetching (only new candles since last fetch).
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.client.kraken import KrakenClient
from app.database.repositories import HistoricalOHLCVRepository


class HistoricalDataFetcher:
    """Fetches and caches historical OHLCV data from Kraken."""

    # Interval mapping: our format -> Kraken's format (minutes)
    INTERVAL_MAP = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
        "1w": 10080,
        "15d": 21600
    }

    def __init__(self, session: Session):
        """
        Initialize the fetcher.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.repo = HistoricalOHLCVRepository(session)
        self.kraken = KrakenClient()

    def fetch_and_cache(
        self,
        symbol: str,
        interval: str = "5m",
        days_back: int = 90
    ) -> int:
        """
        Fetch historical OHLCV data from Kraken and cache in database.

        Uses incremental fetching: only fetches data after the most recent
        cached timestamp to avoid duplicates.

        Args:
            symbol: Trading pair (e.g., "BTCUSD")
            interval: Candle interval ("5m", "1h", "1d")
            days_back: How many days of history to fetch (if no cache exists)

        Returns:
            Number of candles fetched and cached
        """
        try:
            # Convert interval to Kraken format
            kraken_interval = self._interval_to_minutes(interval)
            if kraken_interval is None:
                logging.error(f"[HistoricalData] Invalid interval: {interval}")
                return 0

            # Check for existing data to enable incremental fetch
            latest_timestamp = self.repo.get_latest_timestamp(symbol, interval)

            if latest_timestamp:
                # We have existing data - only fetch new candles
                # Convert to Unix timestamp for Kraken API
                since = int(latest_timestamp.timestamp())
                logging.info(
                    f"[HistoricalData] Incremental fetch for {symbol} "
                    f"since {latest_timestamp}"
                )
            else:
                # No existing data - fetch full history
                since = None
                logging.info(
                    f"[HistoricalData] Full fetch for {symbol} "
                    f"({days_back} days back)"
                )

            # Fetch from Kraken
            ohlc_data = self.kraken.get_ohlc(
                symbol=symbol,
                interval=kraken_interval,
                since=since
            )

            if not ohlc_data:
                logging.warning(
                    f"[HistoricalData] No data returned from Kraken for {symbol}"
                )
                return 0

            # Parse and cache the data
            candles_cached = 0
            for candle in ohlc_data:
                try:
                    # Kraken OHLC format: [timestamp, open, high, low, close, vwap, volume, count]
                    timestamp = datetime.fromtimestamp(int(candle[0]), tz=timezone.utc)
                    open_price = Decimal(str(candle[1]))
                    high = Decimal(str(candle[2]))
                    low = Decimal(str(candle[3]))
                    close = Decimal(str(candle[4]))
                    volume = Decimal(str(candle[6]))  # Index 6 is volume

                    # Upsert to database
                    self.repo.upsert(
                        symbol=symbol,
                        timestamp=timestamp.replace(tzinfo=None),  # Store as naive UTC
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=volume,
                        interval=interval,
                        source="kraken"
                    )

                    candles_cached += 1

                except (IndexError, ValueError, TypeError) as e:
                    logging.error(
                        f"[HistoricalData] Failed to parse candle: {candle}. "
                        f"Error: {e}"
                    )
                    continue

            logging.info(
                f"[HistoricalData] Cached {candles_cached} candles for "
                f"{symbol} ({interval})"
            )

            # Commit the transaction
            self.session.commit()

            return candles_cached

        except Exception as e:
            logging.error(
                f"[HistoricalData] Error fetching data for {symbol}: {e}",
                exc_info=True
            )
            self.session.rollback()
            return 0

    def _interval_to_minutes(self, interval: str) -> Optional[int]:
        """
        Convert our interval format to Kraken's format (minutes).

        Args:
            interval: Our format ("5m", "1h", "1d")

        Returns:
            Kraken interval in minutes, or None if invalid
        """
        return self.INTERVAL_MAP.get(interval)

    def get_available_data_range(
        self,
        symbol: str,
        interval: str = "5m"
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """
        Get the date range of available cached data.

        Args:
            symbol: Trading pair
            interval: Candle interval

        Returns:
            Tuple of (earliest_timestamp, latest_timestamp) or (None, None)
        """
        try:
            with self.session.no_autoflush:
                candles = self.repo.get_by_symbol(symbol, interval, limit=1)
                if not candles:
                    return (None, None)

                # Get first candle
                first = self.session.query(self.repo.session.query(
                    self.repo.session.query(HistoricalOHLCV).filter(
                        symbol=symbol, interval=interval
                    ).order_by(HistoricalOHLCV.timestamp).first()
                ))

                # Get last candle
                latest = self.repo.get_latest_timestamp(symbol, interval)

                return (first.timestamp if first else None, latest)

        except Exception as e:
            logging.error(f"[HistoricalData] Error getting data range: {e}")
            return (None, None)
