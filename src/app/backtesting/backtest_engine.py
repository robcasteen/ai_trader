"""
Backtesting Engine - Run strategies on historical data to evaluate performance.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging

from app.strategies.strategy_manager import StrategyManager
from app.client.kraken import KrakenClient
from app.utils.symbol_normalizer import normalize_symbol


class BacktestPortfolio:
    """Simulates a trading portfolio for backtesting."""

    def __init__(self, initial_capital: float = 10000.0, fee_rate: float = 0.0026):
        """
        Initialize portfolio.

        Args:
            initial_capital: Starting cash in USD
            fee_rate: Trading fee percentage (0.26% for Kraken)
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, float] = {}  # symbol -> quantity
        self.fee_rate = fee_rate

        # Track history
        self.trades: List[Dict[str, Any]] = []
        self.portfolio_values: List[Dict[str, Any]] = []

    def buy(self, symbol: str, price: float, amount: float, timestamp: datetime) -> bool:
        """Execute a buy order."""
        cost = price * amount
        fee = cost * self.fee_rate
        total_cost = cost + fee

        if total_cost > self.cash:
            return False  # Insufficient funds

        self.cash -= total_cost
        self.positions[symbol] = self.positions.get(symbol, 0) + amount

        self.trades.append({
            "timestamp": timestamp,
            "action": "BUY",
            "symbol": symbol,
            "price": price,
            "amount": amount,
            "fee": fee,
            "total_cost": total_cost
        })

        return True

    def sell(self, symbol: str, price: float, amount: float, timestamp: datetime) -> bool:
        """Execute a sell order."""
        if symbol not in self.positions or self.positions[symbol] < amount:
            return False  # Insufficient holdings

        proceeds = price * amount
        fee = proceeds * self.fee_rate
        net_proceeds = proceeds - fee

        self.cash += net_proceeds
        self.positions[symbol] -= amount

        # Remove position if at or near zero (account for floating point precision)
        if self.positions[symbol] < 0.0001:
            del self.positions[symbol]

        self.trades.append({
            "timestamp": timestamp,
            "action": "SELL",
            "symbol": symbol,
            "price": price,
            "amount": amount,
            "fee": fee,
            "net_proceeds": net_proceeds
        })

        return True

    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        """Calculate total portfolio value."""
        holdings_value = sum(
            self.positions.get(symbol, 0) * prices.get(symbol, 0)
            for symbol in self.positions
        )
        return self.cash + holdings_value

    def record_value(self, timestamp: datetime, prices: Dict[str, float]):
        """Record portfolio value snapshot."""
        value = self.get_portfolio_value(prices)
        self.portfolio_values.append({
            "timestamp": timestamp,
            "cash": self.cash,
            "holdings_value": value - self.cash,
            "total_value": value
        })


class BacktestEngine:
    """Main backtesting engine."""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize backtest engine.

        Args:
            config: Configuration dict
        """
        self.config = config or {}
        self.client = KrakenClient()
        self.strategy_manager = StrategyManager(config.get("strategy_config", {}))

    def fetch_historical_data(
        self,
        symbol: str,
        interval_minutes: int = 60,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical OHLC data from Kraken.

        Args:
            symbol: Trading pair (e.g., "XXBTZUSD")
            interval_minutes: Candle interval in minutes (1, 5, 15, 30, 60, 240, 1440)
            days_back: How many days of history to fetch

        Returns:
            List of candle dicts with keys: timestamp, open, high, low, close, volume
        """
        logging.info(f"[Backtest] Fetching {days_back} days of {interval_minutes}min data for {symbol}")

        # Kraken returns max 720 candles per request
        # Calculate how many requests we need
        candles_per_day = (24 * 60) // interval_minutes
        total_candles_needed = candles_per_day * days_back
        max_candles_per_request = 720

        all_candles = []
        since = None

        # Fetch in chunks
        while len(all_candles) < total_candles_needed:
            ohlc_data = self.client.get_ohlc(symbol, interval=interval_minutes, since=since)

            if not ohlc_data:
                break

            for candle in ohlc_data:
                # Format: [timestamp, open, high, low, close, vwap, volume, count]
                all_candles.append({
                    "timestamp": datetime.fromtimestamp(int(candle[0])),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "vwap": float(candle[5]),
                    "volume": float(candle[6])
                })

            # Update 'since' for next request
            if ohlc_data:
                since = int(ohlc_data[-1][0]) + 1

            # Stop if we got less than max candles (means we hit the limit)
            if len(ohlc_data) < max_candles_per_request:
                break

        logging.info(f"[Backtest] Fetched {len(all_candles)} candles for {symbol}")
        return all_candles[-total_candles_needed:]  # Return most recent N candles

    def run_backtest(
        self,
        symbols: List[str],
        days_back: int = 30,
        interval_minutes: int = 60,
        initial_capital: float = 10000.0,
        position_size_pct: float = 0.03  # 3% of portfolio per trade
    ) -> Dict[str, Any]:
        """
        Run backtest on historical data.

        Args:
            symbols: List of symbols to trade
            days_back: How many days to backtest
            interval_minutes: Candle interval
            initial_capital: Starting capital
            position_size_pct: Percentage of portfolio to risk per trade

        Returns:
            Backtest results dict with performance metrics
        """
        logging.info(f"[Backtest] Starting backtest: {len(symbols)} symbols, {days_back} days")

        # Initialize portfolio
        portfolio = BacktestPortfolio(initial_capital=initial_capital)

        # Fetch historical data for all symbols
        historical_data: Dict[str, List[Dict]] = {}
        for symbol in symbols:
            try:
                historical_data[symbol] = self.fetch_historical_data(
                    symbol, interval_minutes, days_back
                )
            except Exception as e:
                logging.error(f"[Backtest] Failed to fetch data for {symbol}: {e}")

        if not historical_data:
            return {"error": "No historical data fetched"}

        # Get all unique timestamps across all symbols
        all_timestamps = sorted(set(
            candle["timestamp"]
            for candles in historical_data.values()
            for candle in candles
        ))

        logging.info(f"[Backtest] Simulating {len(all_timestamps)} time steps")

        # Replay history
        for i, timestamp in enumerate(all_timestamps):
            # Get current prices
            current_prices = {}
            current_volumes = {}

            for symbol, candles in historical_data.items():
                # Find candle at this timestamp
                candle = next((c for c in candles if c["timestamp"] == timestamp), None)
                if candle:
                    current_prices[symbol] = candle["close"]
                    current_volumes[symbol] = candle["volume"]

            # Record portfolio value
            portfolio.record_value(timestamp, current_prices)

            # For each symbol, check if we should trade
            for symbol in symbols:
                if symbol not in current_prices:
                    continue

                price = current_prices[symbol]
                normalized_symbol = normalize_symbol(symbol)

                # Build historical price/volume arrays for strategies
                # (strategies need recent history to make decisions)
                symbol_candles = historical_data[symbol]
                current_idx = next(
                    (idx for idx, c in enumerate(symbol_candles) if c["timestamp"] == timestamp),
                    None
                )

                if current_idx is None or current_idx < 50:
                    continue  # Need at least 50 candles of history

                # Get recent prices and volumes
                recent_candles = symbol_candles[max(0, current_idx-100):current_idx+1]
                price_history = [c["close"] for c in recent_candles]
                volume_history = [c["volume"] for c in recent_candles]

                # Generate signal from strategies
                try:
                    signal_result = self.strategy_manager.generate_signal(
                        symbol=normalized_symbol,
                        price=price,
                        price_history=price_history,
                        volume_history=volume_history,
                        news_headlines=[]  # No news in backtest for now
                    )

                    signal = signal_result.get("final_signal")
                    confidence = signal_result.get("final_confidence", 0)

                    # Execute trades based on signal
                    portfolio_value = portfolio.get_portfolio_value(current_prices)
                    position_size_usd = portfolio_value * position_size_pct

                    if signal == "BUY" and confidence > 0.2:
                        amount = position_size_usd / price
                        portfolio.buy(symbol, price, amount, timestamp)

                    elif signal == "SELL" and symbol in portfolio.positions:
                        # Sell entire position
                        amount = portfolio.positions[symbol]
                        portfolio.sell(symbol, price, amount, timestamp)

                except Exception as e:
                    logging.error(f"[Backtest] Error generating signal for {symbol}: {e}")

        # Calculate final metrics
        final_value = portfolio.get_portfolio_value(current_prices)
        total_return = (final_value - initial_capital) / initial_capital
        total_return_pct = total_return * 100

        # Calculate metrics
        results = {
            "initial_capital": initial_capital,
            "final_value": final_value,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "total_trades": len(portfolio.trades),
            "portfolio_values": portfolio.portfolio_values,
            "trades": portfolio.trades,
            "symbols": symbols,
            "days_back": days_back,
            "interval_minutes": interval_minutes,
        }

        # Calculate additional metrics
        if portfolio.trades:
            winning_trades = [
                t for t in portfolio.trades
                if t["action"] == "SELL" and self._is_winning_trade(t, portfolio.trades)
            ]
            results["win_rate"] = len(winning_trades) / (len(portfolio.trades) / 2)  # Divide by 2 (buy+sell = 1 trade)

        logging.info(f"[Backtest] Complete! Return: {total_return_pct:.2f}% ({len(portfolio.trades)} trades)")

        return results

    def _is_winning_trade(self, sell_trade: Dict, all_trades: List[Dict]) -> bool:
        """Check if a sell trade was profitable."""
        symbol = sell_trade["symbol"]
        sell_time = sell_trade["timestamp"]

        # Find corresponding buy
        for trade in reversed(all_trades):
            if (trade["symbol"] == symbol and
                trade["action"] == "BUY" and
                trade["timestamp"] < sell_time):
                return sell_trade["price"] > trade["price"]

        return False
