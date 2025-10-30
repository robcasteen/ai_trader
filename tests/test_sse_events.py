"""
SSE (Server-Sent Events) Integration Tests.

Tests that verify events are properly emitted to the event bus when:
- Trades are executed
- Signals are generated
- Balance is updated
- Config is changed

These tests use TDD - they should FAIL initially, then pass after implementation.

Note: We test event emission to the event bus, not the actual SSE HTTP streaming.
The SSE endpoint already exists and works - we just need to emit events to it.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client after conftest fixtures have run."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def event_collector():
    """Fixture that collects events emitted to the event bus."""
    from app.events.event_bus import event_bus, EventType

    collected_events = []

    async def collect_event(event):
        """Collect events for testing."""
        collected_events.append(event)

    # Subscribe to all event types
    for event_type in EventType:
        event_bus.subscribe(event_type, collect_event)

    yield collected_events

    # Cleanup - unsubscribe
    for event_type in EventType:
        event_bus.unsubscribe(event_type, collect_event)


class TestSSEEndpoint:
    """Test that SSE endpoint exists (it already does)."""

    def test_sse_endpoint_exists(self, client):
        """SSE endpoint should exist."""
        # Just verify the endpoint is registered
        response = client.get("/api/events", headers={"Accept": "text/event-stream"})
        # Note: This will return immediately in test mode, that's OK
        # We're just verifying the route exists
        assert response.status_code in [200, 500], "SSE endpoint should exist"


class TestTradeExecutedEvents:
    """Test that trade execution emits events to event bus."""

    def test_trade_executed_emits_event(self, event_collector):
        """When a trade is executed, should emit trade_executed event to event bus."""
        from app.logic.paper_trader import PaperTrader
        from app.database.connection import get_db
        from app.events.event_bus import EventType

        # Execute a trade through paper trader
        with get_db() as db:
            trader = PaperTrader(db, test_mode=True)

            # Create a signal first
            from app.database.repositories import SignalRepository
            signal_repo = SignalRepository(db)
            signal_id = signal_repo.create(
                symbol="BTCUSD",
                final_signal="BUY",
                final_confidence=0.75,
                strategies={},
                aggregation_method="test",
                price=50000.0,
                test_mode=True
            )

            # Execute trade - this should emit an event
            trader.execute_signal("BTCUSD", "BUY", 50000.0, 0.75, signal_id)

        # Verify trade_executed event was emitted to event bus
        trade_events = [e for e in event_collector if e.type == EventType.TRADE_EXECUTED]
        assert len(trade_events) > 0, "Should emit at least one trade_executed event to event bus"

        trade_event = trade_events[0]
        assert trade_event.data["symbol"] == "BTCUSD", "Event should contain trade symbol"
        assert trade_event.data["action"] == "BUY", "Event should contain trade action"


class TestSignalGeneratedEvents:
    """Test that signal generation emits SSE events."""

    def test_signal_generated_emits_event(self, client):
        """When a signal is generated, should emit signal_generated event via SSE."""
        events_received = []

        async def listen_for_events():
            """Listen for SSE events."""
            with client.stream("GET", "/api/events") as response:
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:])
                        events_received.append(data)
                        if data.get("type") == "signal_generated":
                            break

        # Generate a signal through strategy manager
        from app.strategies.strategy_manager import StrategyManager
        manager = StrategyManager()

        context = {
            'price': 50000,
            'headlines': ['Bitcoin bullish'],
            'price_history': [49000 + i*100 for i in range(50)],
            'volume': 1000,
            'volume_history': [1000] * 50
        }

        signal, confidence, reason, signal_id = manager.get_signal("BTC/USD", context)

        # Start listening
        asyncio.run(listen_for_events())

        # Verify signal_generated event was received
        signal_events = [e for e in events_received if e.get("type") == "signal_generated"]
        assert len(signal_events) > 0, "Should receive at least one signal_generated event"

        signal_event = signal_events[0]
        assert "symbol" in signal_event["data"], "Event should contain symbol"
        assert "signal" in signal_event["data"], "Event should contain signal"
        assert "confidence" in signal_event["data"], "Event should contain confidence"


class TestBalanceUpdatedEvents:
    """Test that balance updates emit SSE events."""

    def test_balance_updated_emits_event(self, client):
        """When balance changes, should emit balance_updated event via SSE."""
        events_received = []

        async def listen_for_events():
            """Listen for SSE events."""
            with client.stream("GET", "/api/events") as response:
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:])
                        events_received.append(data)
                        if data.get("type") == "balance_updated":
                            break

        # Update balance through config
        response = client.post("/api/config/balance", json={"balance": 15000.0})
        assert response.status_code == 200, "Balance update should succeed"

        # Start listening
        asyncio.run(listen_for_events())

        # Verify balance_updated event was received
        balance_events = [e for e in events_received if e.get("type") == "balance_updated"]
        assert len(balance_events) > 0, "Should receive at least one balance_updated event"

        balance_event = balance_events[0]
        assert "balance" in balance_event["data"], "Event should contain new balance"
        assert balance_event["data"]["balance"] == 15000.0, "Event should contain correct balance"


class TestConfigChangedEvents:
    """Test that config changes emit SSE events."""

    def test_config_changed_emits_event(self, client):
        """When config changes, should emit config_changed event via SSE."""
        events_received = []

        async def listen_for_events():
            """Listen for SSE events."""
            with client.stream("GET", "/api/events") as response:
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:])
                        events_received.append(data)
                        if data.get("type") == "config_changed":
                            break

        # Update config
        response = client.post("/api/config", json={
            "mode": "paper",
            "min_confidence": 0.6,
            "balance": 10000.0
        })
        assert response.status_code == 200, "Config update should succeed"

        # Start listening
        asyncio.run(listen_for_events())

        # Verify config_changed event was received
        config_events = [e for e in events_received if e.get("type") == "config_changed"]
        assert len(config_events) > 0, "Should receive at least one config_changed event"

        config_event = config_events[0]
        assert "config" in config_event["data"], "Event should contain new config"


class TestMultipleSSEClients:
    """Test that multiple SSE clients can connect and receive events."""

    def test_multiple_clients_receive_events(self, client):
        """Multiple SSE clients should all receive the same events."""
        client1_events = []
        client2_events = []

        async def listen_client1():
            """Listen for events on client 1."""
            with client.stream("GET", "/api/events") as response:
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:])
                        client1_events.append(data)
                        if data.get("type") == "balance_updated":
                            break

        async def listen_client2():
            """Listen for events on client 2."""
            with client.stream("GET", "/api/events") as response:
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:])
                        client2_events.append(data)
                        if data.get("type") == "balance_updated":
                            break

        # Start both clients listening
        asyncio.create_task(listen_client1())
        asyncio.create_task(listen_client2())

        # Trigger an event
        response = client.post("/api/config/balance", json={"balance": 20000.0})
        assert response.status_code == 200

        # Both clients should receive the event
        balance_events_1 = [e for e in client1_events if e.get("type") == "balance_updated"]
        balance_events_2 = [e for e in client2_events if e.get("type") == "balance_updated"]

        assert len(balance_events_1) > 0, "Client 1 should receive balance_updated event"
        assert len(balance_events_2) > 0, "Client 2 should receive balance_updated event"
        assert balance_events_1[0]["data"]["balance"] == balance_events_2[0]["data"]["balance"], \
            "Both clients should receive same event data"


class TestSSEEventFormat:
    """Test that SSE events follow the correct format."""

    def test_event_has_required_fields(self, client):
        """All SSE events should have type and data fields."""
        events_received = []

        async def listen_for_events():
            """Listen for a few events."""
            count = 0
            with client.stream("GET", "/api/events") as response:
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:])
                        events_received.append(data)
                        count += 1
                        if count >= 3:  # Collect first 3 events
                            break

        # Trigger some events
        client.post("/api/config/balance", json={"balance": 12000.0})

        asyncio.run(listen_for_events())

        # Verify all events have required structure
        for event in events_received:
            assert "type" in event, "Event must have 'type' field"
            assert "data" in event or "message" in event, \
                "Event must have either 'data' or 'message' field"
            assert isinstance(event["type"], str), "Event type must be string"
