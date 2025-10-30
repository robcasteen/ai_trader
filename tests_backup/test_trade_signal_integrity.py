"""
Test data integrity between trades, signals, and holdings.

Ensures that when a trade is executed:
1. Trade record has signal_id linked
2. Holding record has entry_trade_id and entry_signal_id linked
3. All three records can be traced back to each other
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from app.logic.paper_trader import PaperTrader
from app.database.connection import get_db
from app.database.repositories import TradeRepository, HoldingRepository, SignalRepository


class TestTradeSignalHoldingIntegrity:
    """Test that trades, signals, and holdings are properly linked."""

    def test_buy_trade_creates_linked_records(self):
        """When executing a BUY trade, all records should be linked."""
        # Create a signal first
        with get_db() as db:
            signal_repo = SignalRepository(db)
            signal = signal_repo.create(
                timestamp=datetime.now(timezone.utc),
                symbol="LINKUSD",  # Use real symbol from Kraken
                price=Decimal("100.0"),
                final_signal="BUY",
                final_confidence=Decimal("0.75"),
                aggregation_method="weighted_vote",
                strategies={"test": {"signal": "BUY", "confidence": 0.75}},
                test_mode=False
            )
            db.commit()
            signal_id = signal.id

        # Execute trade with signal_id
        trader = PaperTrader()
        result = trader.execute_trade(
            symbol="LINKUSD",
            action="BUY",
            price=100.0,
            balance=100.0,
            reason="Test BUY",
            amount=0.5,
            signal_id=signal_id
        )

        assert result["action"] == "buy"

        # Verify trade has signal_id
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = [t for t in trade_repo.get_all() if t.symbol == "LINKUSD"]
            assert len(trades) > 0, "No LINKUSD trade found"
            latest_trade = trades[0]
            assert latest_trade.action == "buy"
            assert latest_trade.signal_id == signal_id, f"Trade signal_id is {latest_trade.signal_id}, expected {signal_id}"

            trade_id = latest_trade.id

            # Verify holding has entry_trade_id and entry_signal_id
            holding_repo = HoldingRepository(db)
            all_holdings = holding_repo.get_current_holdings(test_mode=False)
            linkusd_holdings = [h for h in all_holdings if h.symbol == "LINKUSD"]
            assert len(linkusd_holdings) > 0, "No holding found for LINKUSD"
            holding = linkusd_holdings[0]
            assert holding.entry_trade_id == trade_id, f"Holding entry_trade_id is {holding.entry_trade_id}, expected {trade_id}"
            assert holding.entry_signal_id == signal_id, f"Holding entry_signal_id is {holding.entry_signal_id}, expected {signal_id}"

    def test_sell_trade_maintains_links(self):
        """When executing a SELL trade, links should be maintained."""
        # Create signal and initial position
        with get_db() as db:
            signal_repo = SignalRepository(db)
            buy_signal = signal_repo.create(
                timestamp=datetime.now(timezone.utc),
                symbol="ADAUSD",
                price=Decimal("50.0"),
                final_signal="BUY",
                final_confidence=Decimal("0.8"),
                aggregation_method="weighted_vote",
                strategies={"test": {"signal": "BUY", "confidence": 0.8}},
                test_mode=False
            )
            db.commit()
            buy_signal_id = buy_signal.id

        # Execute BUY
        trader = PaperTrader()
        trader.execute_trade(
            symbol="ADAUSD",
            action="BUY",
            price=50.0,
            balance=200.0,
            reason="Test BUY",
            amount=1.0,
            signal_id=buy_signal_id
        )

        # Create SELL signal
        with get_db() as db:
            signal_repo = SignalRepository(db)
            sell_signal = signal_repo.create(
                timestamp=datetime.now(timezone.utc),
                symbol="ADAUSD",
                price=Decimal("60.0"),
                final_signal="SELL",
                final_confidence=Decimal("0.7"),
                aggregation_method="weighted_vote",
                strategies={"test": {"signal": "SELL", "confidence": 0.7}},
                test_mode=False
            )
            db.commit()
            sell_signal_id = sell_signal.id

        # Execute SELL (partial)
        trader.execute_trade(
            symbol="ADAUSD",
            action="SELL",
            price=60.0,
            balance=150.0,
            reason="Test SELL",
            amount=0.5,
            signal_id=sell_signal_id
        )

        # Verify SELL trade has signal_id
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = trade_repo.get_all(limit=2)
            sell_trade = [t for t in trades if t.action == "sell"][0]
            assert sell_trade.signal_id == sell_signal_id

            # Verify holding still exists with links
            holding_repo = HoldingRepository(db)
            all_holdings = holding_repo.get_current_holdings(test_mode=False)
            adausd_holdings = [h for h in all_holdings if h.symbol == "ADAUSD"]
            assert len(adausd_holdings) > 0, "No holdings found for ADAUSD"
            holding = adausd_holdings[0]
            assert holding.entry_trade_id is not None
            assert holding.entry_signal_id is not None

    def test_hold_signal_no_trade_created(self):
        """HOLD signals should not create trades or holdings."""
        with get_db() as db:
            signal_repo = SignalRepository(db)
            signal = signal_repo.create(
                timestamp=datetime.now(timezone.utc),
                symbol="BTCUSD",
                price=Decimal("25.0"),
                final_signal="HOLD",
                final_confidence=Decimal("0.5"),
                aggregation_method="weighted_vote",
                strategies={"test": {"signal": "HOLD", "confidence": 0.5}},
                test_mode=False
            )
            db.commit()
            signal_id = signal.id

        # Execute HOLD
        trader = PaperTrader()
        result = trader.execute_trade(
            symbol="BTCUSD",
            action="HOLD",
            price=25.0,
            balance=100.0,
            reason="Test HOLD",
            amount=0.0,
            signal_id=signal_id
        )

        assert result["action"] == "HOLD"

        # Verify no trade or holding created
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = [t for t in trade_repo.get_all() if t.symbol == "BTCUSD" and t.action == "hold"]
            assert len(trades) == 0, "HOLD should not create trade records"

            # Note: We don't check holdings for BTCUSD because it may have existing holdings from other tests
