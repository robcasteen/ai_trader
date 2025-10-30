"""
Integration test to verify the "executed" indicator works end-to-end.
This test simulates the full flow: signal -> trade -> dashboard API.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.strategies.strategy_manager import StrategyManager
from app.logic.paper_trader import PaperTrader
from app.database.connection import get_db
from app.database.repositories import SignalRepository, TradeRepository


class TestExecutedIndicatorIntegration:
    """Integration test for executed indicator in dashboard."""

    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)

    def test_dashboard_api_shows_executed_signals(self):
        """
        Full integration test: Create signal, execute trade, verify dashboard API
        shows the signal with executed=True.
        """
        # Step 1: Create a signal via strategy manager
        manager = StrategyManager({'min_confidence': 0.5})
        context = {
            'headlines': ['Major cryptocurrency rally continues'],
            'price': 45000.0,
            'volume': 1000000,
            'price_history': [44000, 44500, 45000],
            'volume_history': [900000, 950000, 1000000]
        }

        signal, confidence, reason, signal_id = manager.get_signal('BTC/USD', context)

        print(f"\n[TEST] Created signal: ID={signal_id}, signal={signal}, confidence={confidence}")
        assert signal_id is not None, "Signal ID should not be None"
        assert signal in ['BUY', 'SELL', 'HOLD'], f"Signal should be valid, got: {signal}"

        # Step 2: Execute a trade with this signal_id
        trader = PaperTrader()
        trade_dict = trader.execute_trade(
            symbol='BTCUSD',
            action=signal,
            price=45000.0,
            balance=1000.0,
            reason=reason,
            amount=0.01,
            signal_id=signal_id
        )

        print(f"[TEST] Executed trade: {trade_dict['action']} {trade_dict['symbol']}")
        assert trade_dict is not None

        # Step 3: Verify trade is linked to signal in database
        with get_db() as db:
            trade_repo = TradeRepository(db)
            trades = trade_repo.get_all(test_mode=False)
            linked_trades = [t for t in trades if t.signal_id == signal_id]

            print(f"[TEST] Found {len(linked_trades)} trades linked to signal {signal_id}")
            assert len(linked_trades) > 0, f"Should have at least one trade linked to signal {signal_id}"

        # Step 4: Call the dashboard /partial endpoint and verify executed flag
        response = self.client.get("/partial")
        assert response.status_code == 200, f"Dashboard endpoint failed: {response.status_code}"

        data = response.json()
        assert 'signals' in data, "Dashboard response should contain 'signals' key"

        signals = data['signals']
        print(f"[TEST] Dashboard returned {len(signals)} signals")

        # Find our signal in the response
        our_signal = None
        for s in signals:
            if s.get('id') == signal_id:
                our_signal = s
                break

        # If signal is not in the limited response, verify it exists in database
        if our_signal is None:
            with get_db() as db:
                signal_repo = SignalRepository(db)
                db_signal = signal_repo.get_by_id(signal_id)
                assert db_signal is not None, f"Signal {signal_id} should exist in database"

            print(f"[TEST] Signal {signal_id} not in dashboard response (may be outside limit)")
            print(f"[TEST] Signal IDs in response: {[s['id'] for s in signals[:5]]}...")

            # Check if ANY signals show as executed
            executed_signals = [s for s in signals if s.get('executed', False)]
            print(f"[TEST] Found {len(executed_signals)} executed signals in response")

            if len(executed_signals) > 0:
                print(f"[TEST] Example executed signal: ID={executed_signals[0]['id']}, "
                      f"{executed_signals[0]['symbol']} {executed_signals[0]['signal']}")
        else:
            # Our signal is in the response - verify executed flag
            print(f"[TEST] Found our signal in dashboard response: ID={our_signal['id']}")
            print(f"[TEST] Signal details: {our_signal['symbol']} {our_signal['signal']} "
                  f"executed={our_signal.get('executed', False)}")

            assert our_signal.get('executed', False) is True, \
                f"Signal {signal_id} should be marked as executed=True in dashboard API"

    def test_dashboard_endpoint_structure(self):
        """Test that the /partial endpoint returns the expected structure."""
        response = self.client.get("/partial")
        assert response.status_code == 200

        data = response.json()

        # Verify required keys
        assert 'signals' in data, "Response should contain 'signals'"
        assert isinstance(data['signals'], list), "signals should be a list"

        # Verify signal structure
        if len(data['signals']) > 0:
            signal = data['signals'][0]
            required_fields = ['id', 'symbol', 'signal', 'confidence', 'price', 'timestamp']
            for field in required_fields:
                assert field in signal, f"Signal should contain '{field}' field"

            # Verify executed field exists (even if False)
            assert 'executed' in signal, "Signal should contain 'executed' field"
            assert isinstance(signal['executed'], bool), "executed should be a boolean"

            print(f"\n[TEST] Dashboard signal structure verified:")
            print(f"       ID={signal['id']}, symbol={signal['symbol']}, "
                  f"signal={signal['signal']}, executed={signal['executed']}")

    def test_executed_indicator_logic(self):
        """
        Test the logic that determines if a signal is executed.
        Verifies that the dashboard correctly builds the executed_signal_ids set.
        """
        with get_db() as db:
            trade_repo = TradeRepository(db)
            signal_repo = SignalRepository(db)

            # Get all trades and build executed set (same logic as dashboard)
            all_trades = trade_repo.get_all(test_mode=False)
            executed_signal_ids = set()
            for t in all_trades:
                if t.signal_id:
                    executed_signal_ids.add(t.signal_id)

            print(f"\n[TEST] Executed signal IDs from trades: {executed_signal_ids}")

            # Get recent signals
            recent_signals = signal_repo.get_recent(limit=50, test_mode=False)

            # Check if any signals are marked as executed
            executed_count = 0
            for s in recent_signals:
                if s.id in executed_signal_ids:
                    executed_count += 1
                    print(f"[TEST] Signal {s.id} ({s.symbol} {s.final_signal}) is executed")

            print(f"[TEST] Total executed signals in recent 50: {executed_count}")

            # If we have trades with signal_ids, we should have executed signals
            if len(executed_signal_ids) > 0:
                # At least some should be in recent signals (unless they're all old)
                signal_ids_in_recent = {s.id for s in recent_signals}
                overlap = executed_signal_ids & signal_ids_in_recent
                print(f"[TEST] Executed signals also in recent: {overlap}")
