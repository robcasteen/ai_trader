"""
Event Emission Tests (TDD).

Tests that verify critical operations emit events to the event bus:
- Trades emit TRADE_EXECUTED events
- Signals emit SIGNAL_GENERATED events
- Config changes emit CONFIG_CHANGED events

These tests should FAIL until event emission is implemented.
"""

import pytest
from datetime import datetime, timezone
from app.events.event_bus import event_bus, EventType


@pytest.fixture(autouse=True)
def clear_event_bus():
    """Clear event bus before each test."""
    # Event bus subscribers are per-process, tests should be isolated
    yield
    # Cleanup happens automatically since each test gets fresh subscribers


class TestTradeExecutedEvents:
    """Test that trades emit events."""

    def test_paper_trader_emits_trade_event(self):
        """When PaperTrader executes a trade, should emit TRADE_EXECUTED event."""
        from app.logic.paper_trader import PaperTrader
        from app.database.connection import get_db
        from app.database.repositories import SignalRepository

        # Collect events
        events_collected = []

        async def collect_event(event: dict):
            events_collected.append(event)

        event_bus.subscribe(EventType.TRADE_EXECUTED, collect_event)

        try:
            # Execute trade (signal_id can be None for this test)
            trader = PaperTrader()
            trade_result = trader.execute_trade(
                symbol="BTCUSD",
                action="BUY",
                price=50000.0,
                balance=10000.0,
                reason="Test trade for event emission",
                amount=0.01,
                signal_id=None
            )

            # Verify event was emitted
            assert len(events_collected) > 0, "Should emit TRADE_EXECUTED event"
            assert events_collected[0]["type"] == EventType.TRADE_EXECUTED
            assert events_collected[0]["data"]["symbol"] == "BTCUSD"
            assert events_collected[0]["data"]["action"] == "buy"  # lowercase in database
            assert "trade_id" in events_collected[0]["data"]

        finally:
            event_bus.unsubscribe(EventType.TRADE_EXECUTED, collect_event)


class TestSignalGeneratedEvents:
    """Test that signals emit events."""

    def test_strategy_manager_emits_signal_event(self):
        """When StrategyManager generates signal, should emit SIGNAL_GENERATED event."""
        from app.strategies.strategy_manager import StrategyManager

        # Collect events
        events_collected = []

        async def collect_event(event: dict):
            events_collected.append(event)

        event_bus.subscribe(EventType.SIGNAL_GENERATED, collect_event)

        try:
            # Generate signal
            manager = StrategyManager()
            context = {
                'price': 50000,
                'headlines': ['Bitcoin bullish'],
                'price_history': [49000 + i*100 for i in range(50)],
                'volume': 1000,
                'volume_history': [1000] * 50
            }

            signal, confidence, reason, signal_id = manager.get_signal("BTC/USD", context)

            # Verify event was emitted
            assert len(events_collected) > 0, "Should emit SIGNAL_GENERATED event"
            assert events_collected[0]["type"] == EventType.SIGNAL_GENERATED
            assert "symbol" in events_collected[0]["data"]
            assert "signal" in events_collected[0]["data"]
            assert "confidence" in events_collected[0]["data"]
            assert "signal_id" in events_collected[0]["data"]

        finally:
            event_bus.unsubscribe(EventType.SIGNAL_GENERATED, collect_event)


class TestConfigChangedEvents:
    """Test that config changes emit events."""

    def test_config_update_emits_event(self):
        """When config is updated via API, should emit CONFIG_CHANGED event."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        # Collect events
        events_collected = []

        async def collect_event(event: dict):
            events_collected.append(event)

        event_bus.subscribe(EventType.CONFIG_CHANGED, collect_event)

        try:
            # Update config
            response = client.post("/api/config", json={
                "mode": "paper",
                "min_confidence": 0.65,
                "balance": 12000.0
            })

            assert response.status_code == 200, "Config update should succeed"

            # Verify event was emitted
            assert len(events_collected) > 0, "Should emit CONFIG_CHANGED event"
            assert events_collected[0]["type"] == EventType.CONFIG_CHANGED
            assert "config" in events_collected[0]["data"]

        finally:
            event_bus.unsubscribe(EventType.CONFIG_CHANGED, collect_event)


class TestBalanceUpdatedEvents:
    """Test that balance updates emit events."""

    def test_balance_update_emits_event(self):
        """When balance is updated via API, should emit BALANCE_UPDATED event."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        # Collect events
        events_collected = []

        async def collect_event(event: dict):
            events_collected.append(event)

        event_bus.subscribe(EventType.BALANCE_UPDATED, collect_event)

        try:
            # Update balance
            response = client.post("/api/config/balance", json={"balance": 15000.0})
            assert response.status_code == 200, "Balance update should succeed"

            # Verify event was emitted
            assert len(events_collected) > 0, "Should emit BALANCE_UPDATED event"
            assert events_collected[0]["type"] == EventType.BALANCE_UPDATED
            assert events_collected[0]["data"]["balance"] == 15000.0

        finally:
            event_bus.unsubscribe(EventType.BALANCE_UPDATED, collect_event)
