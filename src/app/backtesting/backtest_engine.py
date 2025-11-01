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
            config: Configuration dict (can include 'enabled_strategies' list)
        """
        self.config = config or {}
        self.client = KrakenClient()
        self.strategy_manager = StrategyManager(config.get("strategy_config", {}))

        # If specific strategies are selected, disable the others
        enabled_strategies = config.get("enabled_strategies")
        if enabled_strategies:
            # Get all strategy names
            all_strategies = ["sentiment", "technical", "volume"]

            # Disable strategies not in the enabled list
            for strategy_name in all_strategies:
                if strategy_name not in enabled_strategies:
                    self.strategy_manager.disable_strategy(strategy_name)
                else:
                    self.strategy_manager.enable_strategy(strategy_name)

    def _interval_minutes_to_string(self, interval_minutes: int) -> str:
        """
        Convert interval in minutes to string format for database lookup.

        Args:
            interval_minutes: Interval in minutes (1, 5, 15, 30, 60, 240, 1440, etc.)

        Returns:
            Interval string (e.g., "5m", "1h", "1d")
        """
        if interval_minutes < 60:
            return f"{interval_minutes}m"
        elif interval_minutes < 1440:
            hours = interval_minutes // 60
            return f"{hours}h"
        else:
            days = interval_minutes // 1440
            return f"{days}d"

    def fetch_historical_data(
        self,
        symbol: str,
        interval_minutes: int = 60,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical OHLC data from database.

        Args:
            symbol: Trading pair (e.g., "BTCUSD")
            interval_minutes: Candle interval in minutes (1, 5, 15, 30, 60, 240, 1440)
            days_back: How many days of history to fetch

        Returns:
            List of candle dicts with keys: timestamp, open, high, low, close, volume
        """
        from app.database.connection import get_db
        from app.database.repositories import HistoricalOHLCVRepository

        logging.info(f"[Backtest] Loading {days_back} days of {interval_minutes}min data for {symbol} from database")

        # Calculate date range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)

        # Convert interval to string format
        interval_str = self._interval_minutes_to_string(interval_minutes)

        # Load from database
        all_candles = []
        try:
            with get_db() as db:
                repo = HistoricalOHLCVRepository(db)
                candles = repo.get_range(
                    symbol=symbol,
                    start_time=start_time,
                    end_time=end_time,
                    interval=interval_str
                )

                # Convert database models to dict format expected by backtest
                for candle in candles:
                    all_candles.append({
                        "timestamp": candle.timestamp,
                        "open": float(candle.open),
                        "high": float(candle.high),
                        "low": float(candle.low),
                        "close": float(candle.close),
                        "volume": float(candle.volume)
                    })

        except Exception as e:
            logging.error(f"[Backtest] Error loading data from database: {e}")
            return []

        logging.info(f"[Backtest] Loaded {len(all_candles)} candles for {symbol} from database")
        return all_candles

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

        # Initialize current_prices in case we have no data
        current_prices = {}

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
                    context = {
                        "headlines": [],  # No news in backtest for now
                        "price": price,
                        "volume": current_volumes.get(symbol, 0),
                        "price_history": price_history,
                        "volume_history": volume_history
                    }

                    signal, confidence, reason, signal_id = self.strategy_manager.get_signal(
                        symbol=normalized_symbol,
                        context=context
                    )

                    # Execute trades based on signal
                    portfolio_value = portfolio.get_portfolio_value(current_prices)
                    position_size_usd = portfolio_value * position_size_pct

                    # Use min_confidence from config, default to 0.5
                    min_confidence = self.config.get("min_confidence", 0.5)

                    if signal == "BUY" and confidence > min_confidence:
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
