import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # /src
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TRADES_FILE = LOGS_DIR / "trades.json"


class PaperTrader:
    def __init__(self):
        self.trades_file = TRADES_FILE
        if not self.trades_file.exists():
            with open(self.trades_file, "w") as f:
                json.dump([], f)

    def execute_trade(self, symbol, action, price, balance, reason, amount=0.01):
        """
        Simulate a trade and append it to trades.json.
        - symbol: e.g., "BTC/USD"
        - action: "buy" or "sell"
        - price: float
        - balance: current USD balance (not enforced strictly yet)
        - reason: explanation string
        - amount: trade size (default 0.01 BTC)
        """
        trade = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "symbol": symbol,
            "price": price,
            "amount": amount,
            "value": round(amount * price, 2),
            "reason": reason,
        }

        # Load existing trades
        trades = []
        if self.trades_file.exists():
            with open(self.trades_file, "r") as f:
                try:
                    trades = json.load(f)
                except json.JSONDecodeError:
                    trades = []

        # Append new trade
        trades.append(trade)

        # Write back
        with open(self.trades_file, "w") as f:
            json.dump(trades, f, indent=2)

        return trade
