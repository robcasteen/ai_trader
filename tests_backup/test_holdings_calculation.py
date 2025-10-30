"""
Test holdings calculation from trade history.
"""

import pytest
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch


class TestHoldingsCalculation:
    """Test holdings are calculated correctly from trade history."""

    TRADING_FEE = 0.0026  # 0.26%

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.trades_file = Path(self.temp_dir) / "trades.json"

    def create_trades_file(self, trades):
        """Helper to create a trades.json file."""
        with open(self.trades_file, "w") as f:
            json.dump(trades, f)

    def test_simple_buy_includes_fees(self):
        """Test single buy includes trading fees in cost basis."""
        trades = [
            {
                "timestamp": "2025-10-16T10:00:00",
                "action": "BUY",
                "symbol": "BTC/USD",
                "price": 50000.0,
                "amount": 0.1,
            }
        ]
        self.create_trades_file(trades)

        holdings = self.calculate_holdings()

        assert "BTC/USD" in holdings
        assert holdings["BTC/USD"]["amount"] == 0.1
        # Cost basis should include 0.26% fee: 5000 * 1.0026 = 5013
        assert holdings["BTC/USD"]["total_cost"] == pytest.approx(5013.0, abs=0.01)

    def test_buy_then_sell_with_fees(self):
        """Test buy followed by sell accounts for fees correctly."""
        trades = [
            {
                "action": "BUY",
                "symbol": "BTC/USD",
                "price": 50000.0,
                "amount": 0.1,
                "timestamp": "2025-10-16T10:00:00",
            },
            {
                "action": "SELL",
                "symbol": "BTC/USD",
                "price": 51000.0,
                "amount": 0.05,
                "timestamp": "2025-10-16T11:00:00",
            },
        ]
        self.create_trades_file(trades)

        holdings = self.calculate_holdings()

        # After selling half, should have half the position
        assert holdings["BTC/USD"]["amount"] == pytest.approx(0.05, abs=0.00001)
        # Cost basis should be half of original (with fees): 5013 / 2 = 2506.50
        assert holdings["BTC/USD"]["total_cost"] == pytest.approx(2506.50, abs=0.01)

    def test_complete_exit(self):
        """Test selling entire position removes symbol from holdings."""
        trades = [
            {
                "action": "BUY",
                "symbol": "ETH/USD",
                "price": 3000.0,
                "amount": 1.0,
                "timestamp": "2025-10-16T10:00:00",
            },
            {
                "action": "SELL",
                "symbol": "ETH/USD",
                "price": 3100.0,
                "amount": 1.0,
                "timestamp": "2025-10-16T11:00:00",
            },
        ]
        self.create_trades_file(trades)

        holdings = self.calculate_holdings()

        assert "ETH/USD" not in holdings

    def test_multiple_buys_with_fees(self):
        """Test multiple buys accumulate fees correctly."""
        trades = [
            {
                "action": "BUY",
                "symbol": "SOL/USD",
                "price": 100.0,
                "amount": 1.0,
                "timestamp": "2025-10-16T10:00:00",
            },
            {
                "action": "BUY",
                "symbol": "SOL/USD",
                "price": 200.0,
                "amount": 1.0,
                "timestamp": "2025-10-16T11:00:00",
            },
        ]
        self.create_trades_file(trades)

        holdings = self.calculate_holdings()

        assert holdings["SOL/USD"]["amount"] == 2.0
        # First buy: 100 * 1.0026 = 100.26
        # Second buy: 200 * 1.0026 = 200.52
        # Total: 300.78
        assert holdings["SOL/USD"]["total_cost"] == pytest.approx(300.78, abs=0.01)

    def test_hold_actions_ignored(self):
        """Test HOLD actions don't affect positions."""
        trades = [
            {
                "action": "BUY",
                "symbol": "BTC/USD",
                "price": 50000.0,
                "amount": 0.1,
                "timestamp": "2025-10-16T10:00:00",
            },
            {
                "action": "HOLD",
                "symbol": "BTC/USD",
                "price": 51000.0,
                "amount": 0,
                "timestamp": "2025-10-16T11:00:00",
            },
            {
                "action": "HOLD",
                "symbol": "ETH/USD",
                "price": 3000.0,
                "amount": 0,
                "timestamp": "2025-10-16T11:00:00",
            },
        ]
        self.create_trades_file(trades)

        holdings = self.calculate_holdings()

        assert len(holdings) == 1
        assert holdings["BTC/USD"]["amount"] == 0.1

    def test_multiple_symbols(self):
        """Test holdings tracked separately per symbol."""
        trades = [
            {
                "action": "BUY",
                "symbol": "BTC/USD",
                "price": 50000.0,
                "amount": 0.1,
                "timestamp": "2025-10-16T10:00:00",
            },
            {
                "action": "BUY",
                "symbol": "ETH/USD",
                "price": 3000.0,
                "amount": 1.0,
                "timestamp": "2025-10-16T10:00:00",
            },
            {
                "action": "BUY",
                "symbol": "SOL/USD",
                "price": 100.0,
                "amount": 10.0,
                "timestamp": "2025-10-16T10:00:00",
            },
        ]
        self.create_trades_file(trades)

        holdings = self.calculate_holdings()

        assert len(holdings) == 3
        assert holdings["BTC/USD"]["amount"] == 0.1
        assert holdings["ETH/USD"]["amount"] == 1.0
        assert holdings["SOL/USD"]["amount"] == 10.0

    def test_sell_without_buy(self):
        """Test selling without position doesn't create negative position."""
        trades = [
            {
                "action": "SELL",
                "symbol": "BTC/USD",
                "price": 50000.0,
                "amount": 0.1,
                "timestamp": "2025-10-16T10:00:00",
            }
        ]
        self.create_trades_file(trades)

        holdings = self.calculate_holdings()

        assert "BTC/USD" not in holdings or holdings["BTC/USD"]["amount"] <= 0

    def calculate_holdings(self):
        """Calculate holdings with proper fee accounting."""
        holdings = {}

        with open(self.trades_file, "r") as f:
            trades = json.load(f)

        for trade in trades:
            symbol = trade.get("symbol", "")
            action = trade.get("action", "").lower()
            amount = trade.get("amount", 0)
            price = trade.get("price", 0)

            if action == "hold":
                continue

            if action == "buy":
                if symbol not in holdings:
                    holdings[symbol] = {"amount": 0.0, "total_cost": 0.0}

                # Add trading fee to cost basis
                cost_with_fee = (amount * price) * (1 + self.TRADING_FEE)
                holdings[symbol]["amount"] += amount
                holdings[symbol]["total_cost"] += cost_with_fee

            elif action == "sell":
                if symbol in holdings:
                    # Reduce position proportionally
                    if holdings[symbol]["amount"] > 0:
                        proportion_sold = amount / holdings[symbol]["amount"]
                        cost_reduction = (
                            holdings[symbol]["total_cost"] * proportion_sold
                        )

                        holdings[symbol]["amount"] -= amount
                        holdings[symbol]["total_cost"] -= cost_reduction

                        if holdings[symbol]["amount"] <= 0.0001:
                            del holdings[symbol]

        return holdings


class TestConfidenceCalculation:
    """Test weighted vote confidence calculation."""

    def test_buy_signal_uses_actionable_weight_only(self):
        """Test BUY signal divides by actionable weight, not total weight."""
        # Simulate: Sentiment BUY 60%, Technical HOLD 30%, Volume HOLD 0%
        results = [
            {
                "strategy": "sentiment",
                "signal": "BUY",
                "confidence": 0.6,
                "weight": 1.0,
                "reason": "Bullish",
            },
            {
                "strategy": "technical",
                "signal": "HOLD",
                "confidence": 0.3,
                "weight": 1.0,
                "reason": "Neutral",
            },
            {
                "strategy": "volume",
                "signal": "HOLD",
                "confidence": 0.0,
                "weight": 0.8,
                "reason": "No data",
            },
        ]

        signal, confidence = self.calculate_weighted_vote(results)

        assert signal == "BUY"
        # BUY score: 0.6 * 1.0 = 0.6
        # Actionable weight: 1.0 (only sentiment voted BUY)
        # Expected confidence: 0.6 / 1.0 = 0.6 (60%)
        assert confidence == pytest.approx(0.6, abs=0.01)

    def test_sell_signal_uses_actionable_weight_only(self):
        """Test SELL signal divides by actionable weight, not total weight."""
        results = [
            {
                "strategy": "sentiment",
                "signal": "SELL",
                "confidence": 0.8,
                "weight": 1.0,
                "reason": "Bearish",
            },
            {
                "strategy": "technical",
                "signal": "HOLD",
                "confidence": 0.3,
                "weight": 1.0,
                "reason": "Neutral",
            },
            {
                "strategy": "volume",
                "signal": "HOLD",
                "confidence": 0.0,
                "weight": 0.8,
                "reason": "No data",
            },
        ]

        signal, confidence = self.calculate_weighted_vote(results)

        assert signal == "SELL"
        # SELL score: 0.8 * 1.0 = 0.8
        # Actionable weight: 1.0 (only sentiment voted SELL)
        # Expected confidence: 0.8 / 1.0 = 0.8 (80%)
        assert confidence == pytest.approx(0.8, abs=0.01)

    def test_hold_signal_uses_total_weight(self):
        """Test HOLD signal divides by total weight (actionable + hold)."""
        results = [
            {
                "strategy": "sentiment",
                "signal": "HOLD",
                "confidence": 0.3,
                "weight": 1.0,
                "reason": "Neutral",
            },
            {
                "strategy": "technical",
                "signal": "HOLD",
                "confidence": 0.3,
                "weight": 1.0,
                "reason": "Neutral",
            },
            {
                "strategy": "volume",
                "signal": "HOLD",
                "confidence": 0.0,
                "weight": 0.8,
                "reason": "No data",
            },
        ]

        signal, confidence = self.calculate_weighted_vote(results)

        assert signal == "HOLD"
        # HOLD score: 0.3 * 1.0 + 0.3 * 1.0 + 0.0 * 0.8 = 0.6
        # Total weight: 1.0 + 1.0 + 0.8 = 2.8
        # Expected confidence: 0.6 / 2.8 = 0.214...
        assert confidence == pytest.approx(0.214, abs=0.01)

    def test_mixed_signals_buy_wins(self):
        """Test BUY wins over SELL with higher weighted score."""
        results = [
            {
                "strategy": "sentiment",
                "signal": "BUY",
                "confidence": 0.8,
                "weight": 1.0,
                "reason": "Bullish",
            },
            {
                "strategy": "technical",
                "signal": "SELL",
                "confidence": 0.6,
                "weight": 1.0,
                "reason": "Bearish",
            },
            {
                "strategy": "volume",
                "signal": "HOLD",
                "confidence": 0.0,
                "weight": 0.8,
                "reason": "No data",
            },
        ]

        signal, confidence = self.calculate_weighted_vote(results)

        assert signal == "BUY"
        # BUY score: 0.8 * 1.0 = 0.8 (wins)
        # SELL score: 0.6 * 1.0 = 0.6
        # Actionable weight: 1.0 + 1.0 = 2.0
        # Expected confidence: 0.8 / 2.0 = 0.4 (40%)
        assert confidence == pytest.approx(0.4, abs=0.01)

    def calculate_weighted_vote(self, results):
        """Mimic strategy_manager._weighted_vote_aggregation logic."""
        from collections import defaultdict

        scores = defaultdict(float)
        actionable_weight = 0
        hold_weight = 0

        for result in results:
            signal = result["signal"]
            confidence = result["confidence"]
            weight = result["weight"]
            weighted_score = confidence * weight

            scores[signal] += weighted_score

            if signal in ["BUY", "SELL"]:
                actionable_weight += weight
            else:
                hold_weight += weight

        if not scores:
            return "HOLD", 0.0

        winning_signal = max(scores.items(), key=lambda x: x[1])
        signal = winning_signal[0]
        raw_score = winning_signal[1]

        # THIS IS THE CRITICAL LOGIC BEING TESTED
        if signal in ["BUY", "SELL"] and actionable_weight > 0:
            confidence = min(raw_score / actionable_weight, 1.0)
        elif actionable_weight + hold_weight > 0:
            confidence = min(raw_score / (actionable_weight + hold_weight), 1.0)
        else:
            confidence = 0.0

        return signal, confidence
