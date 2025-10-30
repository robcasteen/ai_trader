"""
Test that signals are properly linked to trades via signal_id.
This ensures the "executed" indicator works in the dashboard.
"""

import pytest
from app.strategies.strategy_manager import StrategyManager
from app.logic.paper_trader import PaperTrader
from app.database.connection import get_db
from app.database.repositories import SignalRepository, TradeRepository


class TestSignalToTradeLinking:
    """Test that signal_id is properly returned and linked to trades."""

    def test_strategy_manager_returns_signal_id(self):
        """Strategy manager should return signal_id as 4th element of tuple."""
        manager = StrategyManager({'min_confidence': 0.5})
        context = {
            'headlines': ['Bitcoin surges to new all-time high'],
            'price': 50000.0,
            'volume': 1000000,
            'price_history': [49000, 49500, 50000],
            'volume_history': [900000, 950000, 1000000]
        }

        signal, confidence, reason, signal_id = manager.get_signal('BTC/USD', context)

        # Should return signal_id
        assert signal_id is not None, "signal_id should not be None"
        assert isinstance(signal_id, int), "signal_id should be an integer"

        # Verify signal was saved to database
        with get_db() as db:
            repo = SignalRepository(db)
            saved_signal = repo.get_by_id(signal_id)
            assert saved_signal is not None, f"Signal ID {signal_id} should exist in database"
            assert saved_signal.symbol == 'BTCUSD'

    def test_trade_links_to_signal(self):
        """Trades should be linked to the signal that triggered them."""
        # Create a signal
        manager = StrategyManager({'min_confidence': 0.5})
        context = {
            'headlines': ['Bitcoin surges past resistance levels'],
            'price': 51000.0,
            'volume': 1000000,
            'price_history': [50000, 50500, 51000],
            'volume_history': [900000, 950000, 1000000]
        }

        signal, confidence, reason, signal_id = manager.get_signal('BTC/USD', context)
        assert signal_id is not None

        # Execute a trade with this signal_id
        trader = PaperTrader()
        trade_dict = trader.execute_trade(
            symbol='BTCUSD',
            action='BUY',
            price=51000.0,
            balance=1000.0,
            reason=reason,
            amount=0.01,
            signal_id=signal_id
        )

        assert trade_dict is not None
        assert trade_dict['action'] == 'buy'
        assert trade_dict['symbol'] == 'BTCUSD'

        # Find the trade in database (it was just created, should be most recent)
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = trade_repo.get_all(test_mode=False)
            # Get most recent trade
            latest_trade = max(trades, key=lambda t: t.id)

            assert latest_trade is not None
            assert latest_trade.signal_id == signal_id, f"Trade should link to signal ID {signal_id}"

    def test_dashboard_shows_executed_indicator(self):
        """Dashboard should mark signals as executed when they have linked trades."""
        # Create signal and execute trade
        manager = StrategyManager({'min_confidence': 0.5})
        context = {
            'headlines': ['Ethereum breaks resistance'],
            'price': 4000.0,
            'volume': 500000,
            'price_history': [3900, 3950, 4000],
            'volume_history': [450000, 475000, 500000]
        }

        signal, confidence, reason, signal_id = manager.get_signal('ETH/USD', context)
        assert signal_id is not None

        trader = PaperTrader()
        trader.execute_trade(
            symbol='ETHUSD',
            action='BUY',
            price=4000.0,
            balance=1000.0,
            reason=reason,
            amount=0.01,
            signal_id=signal_id
        )

        # Verify signal shows as executed
        with get_db() as db:
            trade_repo = TradeRepository(db)
            signal_repo = SignalRepository(db)

            # Get executed signal IDs (non-test mode trades)
            all_trades = trade_repo.get_all(test_mode=False)
            executed_signal_ids = {t.signal_id for t in all_trades if t.signal_id}

            assert signal_id in executed_signal_ids, "Signal should be marked as executed"

            # Verify signal exists
            signal_model = signal_repo.get_by_id(signal_id)
            assert signal_model is not None
            assert signal_model.id in executed_signal_ids
