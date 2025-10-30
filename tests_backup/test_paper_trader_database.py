"""
Tests for PaperTrader database integration - verifying trades write to database.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch
from app.logic.paper_trader import PaperTrader
from app.database.connection import get_db
from app.database.repositories import TradeRepository
from app.database.models import Trade, Holding


class TestPaperTraderDatabaseIntegration:
    """Test that PaperTrader writes to database correctly."""

    @pytest.fixture
    def clean_database(self):
        """Clean test database before each test."""
        with get_db() as db:
            # Clear all trades and holdings (order matters - holdings reference trades)
            db.query(Holding).delete()
            db.query(Trade).delete()
            db.commit()

    @pytest.fixture
    def paper_trader(self):
        """Create a PaperTrader instance."""
        return PaperTrader()

    def test_buy_trade_writes_to_database(self, paper_trader, clean_database):
        """Test that a BUY trade is written to the database."""
        symbol = "BTCUSD"
        price = 50000.0
        balance = 10000.0
        reason = "Test buy signal"

        # Execute BUY trade
        result = paper_trader.execute_trade(
            symbol=symbol,
            action="BUY",
            price=price,
            balance=balance,
            reason=reason,
            amount=0.1
        )

        # Verify trade was executed (returns trade dict)
        assert result["action"] == "buy"
        assert result["symbol"] == "BTCUSD"  # Canonical format
        assert result["price"] == price

        # Verify trade is in database
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = trade_repo.get_all()

            assert len(trades) == 1
            trade = trades[0]
            assert trade.action == "buy"
            assert trade.symbol == "BTCUSD"  # Canonical format
            assert float(trade.price) == price
            assert float(trade.amount) == 0.1
            assert trade.reason == reason
            assert float(trade.fee) > 0  # Fee should be charged
            assert trade.test_mode is False

    def test_sell_trade_writes_to_database(self, paper_trader, clean_database):
        """Test that a SELL trade is written to the database."""
        symbol = "ETHUSD"
        price = 3000.0
        balance = 10000.0
        reason = "Test sell signal"

        # First buy to have holdings
        paper_trader.execute_trade(
            symbol=symbol,
            action="BUY",
            price=2900.0,
            balance=balance,
            reason="Setup buy",
            amount=1.0
        )

        # Now sell
        result = paper_trader.execute_trade(
            symbol=symbol,
            action="SELL",
            price=price,
            balance=balance,
            reason=reason,
            amount=1.0
        )

        # Verify sell was executed
        assert result["action"] == "sell"
        assert result["symbol"] == "ETHUSD"

        # Verify both trades are in database
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = trade_repo.get_all()

            assert len(trades) == 2

            # Check sell trade (trades ordered by timestamp DESC - newest first)
            sell_trade = trades[0]  # Most recent = SELL
            buy_trade = trades[1]   # Second most recent = BUY

            assert sell_trade.action == "sell"
            assert sell_trade.symbol == "ETHUSD"
            assert float(sell_trade.price) == price
            assert float(sell_trade.amount) == 1.0
            assert sell_trade.reason == reason

            assert buy_trade.action == "buy"
            assert buy_trade.symbol == "ETHUSD"

    def test_hold_action_does_not_write_to_database(self, paper_trader, clean_database):
        """Test that a HOLD action does NOT write to database."""
        symbol = "SOLUSD"
        price = 100.0
        balance = 10000.0
        reason = "Confidence too low"

        # Execute HOLD
        result = paper_trader.execute_trade(
            symbol=symbol,
            action="HOLD",
            price=price,
            balance=balance,
            reason=reason,
            amount=0.0
        )

        # Verify hold returns correct format
        assert result["action"] == "HOLD"
        assert result["symbol"] == "SOLUSD"
        assert result["success"] is True
        assert "message" in result

        # Verify HOLD does NOT write to database
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = trade_repo.get_all()

            assert len(trades) == 0  # No trades should be recorded

    def test_multiple_trades_all_in_database(self, paper_trader, clean_database):
        """Test that multiple BUY/SELL trades are all written to database."""
        trades_to_execute = [
            ("BTCUSD", "BUY", 50000.0, 0.1, "Signal 1"),
            ("ETHUSD", "BUY", 3000.0, 1.0, "Signal 2"),
            ("BTCUSD", "SELL", 51000.0, 0.1, "Signal 3"),
        ]

        balance = 10000.0

        # Execute all trades
        for symbol, action, price, amount, reason in trades_to_execute:
            paper_trader.execute_trade(
                symbol=symbol,
                action=action,
                price=price,
                balance=balance,
                reason=reason,
                amount=amount
            )

        # Verify all trades are in database (HOLD not included)
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = trade_repo.get_all()

            assert len(trades) == 3

            # Verify each trade (ordered by timestamp DESC - newest first)
            assert trades[0].symbol == "BTCUSD"
            assert trades[0].action == "sell"  # Most recent

            assert trades[1].symbol == "ETHUSD"
            assert trades[1].action == "buy"

            assert trades[2].symbol == "BTCUSD"
            assert trades[2].action == "buy"  # Oldest

    def test_trade_has_utc_timestamp(self, paper_trader, clean_database):
        """Test that trades have UTC timezone aware timestamp."""
        paper_trader.execute_trade(
            symbol="BTCUSD",
            action="BUY",
            price=50000.0,
            balance=10000.0,
            reason="Test timestamp",
            amount=0.1
        )

        # Verify timestamp
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = trade_repo.get_all()

            assert len(trades) == 1
            trade = trades[0]

            # Trade timestamp should be recent and timezone aware
            assert trade.timestamp is not None
            # Allow for some test execution time
            time_diff = datetime.now(timezone.utc) - trade.timestamp.replace(tzinfo=timezone.utc)
            assert time_diff.total_seconds() < 5  # Within 5 seconds

    def test_trade_fee_calculation_saved_correctly(self, paper_trader, clean_database):
        """Test that fees are calculated and saved correctly."""
        symbol = "BTCUSD"
        price = 10000.0
        amount = 1.0
        expected_gross = price * amount  # 10000
        expected_fee = expected_gross * 0.0026  # 26.0
        expected_net = expected_gross + expected_fee  # 10026.0 (BUY adds fee)

        paper_trader.execute_trade(
            symbol=symbol,
            action="BUY",
            price=price,
            balance=20000.0,
            reason="Test fees",
            amount=amount
        )

        # Verify fee calculation in database
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = trade_repo.get_all()

            assert len(trades) == 1
            trade = trades[0]

            assert float(trade.gross_value) == expected_gross
            assert float(trade.fee) == expected_fee
            assert float(trade.net_value) == expected_net

    def test_database_write_failure_is_logged(self, paper_trader, clean_database, caplog):
        """Test that database write failures are logged but don't crash."""
        with patch('app.logic.paper_trader.get_db') as mock_get_db:
            # Simulate database error
            mock_get_db.side_effect = Exception("Database connection failed")

            # Execute trade - should not crash
            result = paper_trader.execute_trade(
                symbol="BTCUSD",
                action="BUY",
                price=50000.0,
                balance=10000.0,
                reason="Test error handling",
                amount=0.1
            )

            # Trade should still return result (graceful degradation)
            assert result["action"] == "buy"

            # Verify error was logged
            assert "Failed to save trade to database" in caplog.text

    def test_symbol_normalization_in_database(self, paper_trader, clean_database):
        """Test that symbols are normalized to canonical format when saving to database."""
        # Test both formats - all should normalize to BTCUSD (canonical)
        symbols_to_test = [
            ("BTCUSD", "BTCUSD"),
            ("BTC/USD", "BTCUSD"),
        ]

        for input_symbol, expected_symbol in symbols_to_test:
            # Clean database for each test
            with get_db() as db:
                db.query(Trade).delete()
                db.commit()

            paper_trader.execute_trade(
                symbol=input_symbol,
                action="BUY",
                price=50000.0,
                balance=10000.0,
                reason="Test normalization",
                amount=0.1
            )

            # Verify symbol is normalized in database
            with get_db() as db:
                trade_repo = TradeRepository(db)
                trades = trade_repo.get_all()

                assert len(trades) == 1
                assert trades[0].symbol == expected_symbol

    def test_successful_buy_and_sell_updates_database(self, paper_trader, clean_database):
        """Test that a successful BUY followed by SELL both write to database."""
        symbol = "BTCUSD"

        # BUY
        buy_result = paper_trader.execute_trade(
            symbol=symbol,
            action="BUY",
            price=50000.0,
            balance=10000.0,
            reason="Test buy",
            amount=0.1
        )

        assert buy_result["action"] == "buy"

        # SELL
        sell_result = paper_trader.execute_trade(
            symbol=symbol,
            action="SELL",
            price=51000.0,
            balance=10000.0,
            reason="Test sell",
            amount=0.1
        )

        assert sell_result["action"] == "sell"

        # Verify both in database
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = trade_repo.get_all()

            assert len(trades) == 2
            # Ordered DESC - newest first
            assert trades[0].action == "sell"
            assert trades[1].action == "buy"
