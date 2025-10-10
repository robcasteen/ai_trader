import json
from collections import defaultdict
from pathlib import Path


class InvalidTradeSequenceError(Exception):
    """Raised when an invalid trade sequence is detected (e.g., sell before buy)."""
    pass


# Ensure logs dir is consistent relative to project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = PROJECT_ROOT / "logs"
TRADES_FILE = LOGS_DIR / "trades.json"


class PerformanceTracker:
    def __init__(self):
        self.trades_file = TRADES_FILE

    def _load_trades(self):
        """Load trades.json, return list of trades or empty list if missing/invalid."""
        if not self.trades_file.exists():
            return []
        try:
            with open(self.trades_file, "r") as f:
                trades = json.load(f)
            if not isinstance(trades, list):
                return []
            return trades
        except Exception:
            return []

    def get_performance_summary(self, trades=None):
        """
        Compute performance metrics from trades.
        - Every buy/sell counts as a trade (no fractional trades).
        - Requires every sell to have a matching buy (no short selling).
        - Throws InvalidTradeSequenceError for invalid sequences.
        Returns:
            dict with:
              symbols: {symbol: {pnl, trades, wins, losses, win_rate}}
              total_pnl, total_trades, win_rate
        """
        trades = trades if trades is not None else self._load_trades()
        if not trades:
            return {
                "symbols": {},
                "total_pnl": 0.0,
                "total_trades": 0,
                "win_rate": None,
            }

        open_positions = defaultdict(list)  # symbol -> list of (price, amount)
        stats = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0, "losses": 0})

        for trade in sorted(trades, key=lambda t: t.get("timestamp", "")):
            symbol = trade.get("symbol")
            action = trade.get("action")
            try:
                price = float(trade.get("price", 0))
                amount = float(trade.get("amount", 0))
            except (TypeError, ValueError):
                continue

            if not symbol or amount <= 0:
                continue

            if action == "buy":
                open_positions[symbol].append((price, amount))
                stats[symbol]["trades"] += 1

            elif action == "sell":
                if symbol not in open_positions or not open_positions[symbol]:
                    raise InvalidTradeSequenceError(
                        f"Sell before buy detected for {symbol}"
                    )

                remaining = amount
                pnl = 0.0
                while remaining > 0 and open_positions[symbol]:
                    buy_price, buy_amount = open_positions[symbol][0]
                    if buy_amount <= remaining:
                        trade_amount = buy_amount
                        pnl += (price - buy_price) * trade_amount
                        open_positions[symbol].pop(0)
                        remaining -= trade_amount
                    else:
                        trade_amount = remaining
                        pnl += (price - buy_price) * trade_amount
                        open_positions[symbol][0] = (buy_price, buy_amount - trade_amount)
                        remaining = 0

                if remaining > 0:
                    raise InvalidTradeSequenceError(
                        f"Oversell detected for {symbol}: sold {amount}, available {amount - remaining}"
                    )

                stats[symbol]["pnl"] += pnl
                stats[symbol]["trades"] += 1
                if pnl >= 0:
                    stats[symbol]["wins"] += 1
                else:
                    stats[symbol]["losses"] += 1

        total_pnl = sum(s["pnl"] for s in stats.values())
        total_trades = sum(s["trades"] for s in stats.values())
        total_wins = sum(s["wins"] for s in stats.values())
        total_losses = sum(s["losses"] for s in stats.values())

        win_rate = None
        if total_wins + total_losses > 0:
            win_rate = total_wins / (total_wins + total_losses)

        # Add per-symbol win_rate for consistency
        symbols_out = {}
        for sym, s in stats.items():
            sym_wr = None
            if s["wins"] + s["losses"] > 0:
                sym_wr = s["wins"] / (s["wins"] + s["losses"])
            symbols_out[sym] = {
                "pnl": s["pnl"],
                "trades": s["trades"],
                "wins": s["wins"],
                "losses": s["losses"],
                "win_rate": sym_wr,
            }

        return {
            "symbols": symbols_out,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "win_rate": win_rate,
        }


# singleton instance
performance_tracker = PerformanceTracker()
