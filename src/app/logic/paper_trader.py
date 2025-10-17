import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TRADES_FILE = LOGS_DIR / "trades.json"
HOLDINGS_FILE = LOGS_DIR / "holdings.json"


class PaperTrader:
    def __init__(self):
        self.trades_file = TRADES_FILE
        self.holdings_file = HOLDINGS_FILE
        
        if not self.trades_file.exists():
            with open(self.trades_file, "w") as f:
                json.dump([], f)
        
        if not self.holdings_file.exists():
            with open(self.holdings_file, "w") as f:
                json.dump({}, f)


    def get_holdings(self):
        """Get current holdings/positions."""
        try:
            with open(self.holdings_file, "r") as f:
                return json.load(f)
        except:
            return {}
    
    def update_holdings(self, symbol, action, amount, price):
        """Update holdings based on trade action."""
        holdings = self.get_holdings()
        
        if action.upper() == "BUY":
            if symbol in holdings:
                # Average up position
                old_amount = holdings[symbol]["amount"]
                old_avg_price = holdings[symbol]["avg_price"]
                new_amount = old_amount + amount
                new_avg_price = ((old_amount * old_avg_price) + (amount * price)) / new_amount
                
                holdings[symbol] = {
                    "amount": new_amount,
                    "avg_price": new_avg_price,
                    "current_price": price,
                    "market_value": new_amount * price,
                    "cost_basis": new_amount * new_avg_price,
                    "unrealized_pnl": (new_amount * price) - (new_amount * new_avg_price)
                }
            else:
                # New position
                holdings[symbol] = {
                    "amount": amount,
                    "avg_price": price,
                    "current_price": price,
                    "market_value": amount * price,
                    "cost_basis": amount * price,
                    "unrealized_pnl": 0.0
                }
        
        elif action.upper() == "SELL":
            if symbol in holdings:
                holdings[symbol]["amount"] -= amount
                
                # If position closed, remove it
                if holdings[symbol]["amount"] <= 0.0001:
                    del holdings[symbol]
                else:
                    # Recalculate values
                    holdings[symbol]["market_value"] = holdings[symbol]["amount"] * price
                    holdings[symbol]["current_price"] = price
                    holdings[symbol]["cost_basis"] = holdings[symbol]["amount"] * holdings[symbol]["avg_price"]
                    holdings[symbol]["unrealized_pnl"] = holdings[symbol]["market_value"] - holdings[symbol]["cost_basis"]
        
        # Save updated holdings
        with open(self.holdings_file, "w") as f:
            json.dump(holdings, f, indent=2)

    def execute_trade(self, symbol, action, price, balance, reason, amount=0.01):
        """
        Simulate a trade with Kraken fees.
        - Taker fee: 0.26% applied to all trades
        - Fees reduce the effective value for both buys and sells
        
        For BUY: You pay price + fee
        For SELL: You receive price - fee
        """
        # Calculate gross value
        gross_value = amount * price
        
        # Apply 0.26% taker fee (always reduces net proceeds)
        fee_rate = 0.0026
        fee = gross_value * fee_rate
        
        # Net value calculation (fee always reduces what you get/pay)
        # BUY: Total cost = gross_value + fee (you pay MORE)
        # SELL: Total proceeds = gross_value - fee (you receive LESS)
        if action.lower() == "buy":
            net_value = gross_value + fee  # Cost includes fee
        else:  # sell
            net_value = gross_value - fee  # Proceeds minus fee
        
        trade = {
            "timestamp": datetime.now().isoformat(),
            "action": action.lower(),
            "symbol": symbol,
            "price": price,
            "amount": amount,
            "gross_value": round(gross_value, 2),
            "fee": round(fee, 2),
            "net_value": round(net_value, 2),
            "reason": reason,
            "value": round(net_value, 2),  # Backwards compatibility
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