"""
Event bus for broadcasting state changes to the UI.
"""
import asyncio
import json
import logging
from enum import Enum
from typing import Any, Dict, List, Callable
from datetime import datetime
from collections import defaultdict


class EventType(str, Enum):
    """Types of events that can be emitted."""
    TRADE_EXECUTED = "trade_executed"
    SIGNAL_GENERATED = "signal_generated"
    BALANCE_UPDATED = "balance_updated"
    HOLDINGS_UPDATED = "holdings_updated"
    NEWS_FETCHED = "news_fetched"
    STRATEGY_UPDATED = "strategy_updated"
    ERROR_OCCURRED = "error_occurred"
    BOT_STATUS_CHANGED = "bot_status_changed"


class EventBus:
    """
    Simple event bus for broadcasting events to subscribers.
    Supports both sync and async subscribers.
    """

    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._event_history: List[Dict[str, Any]] = []
        self._max_history = 100

    def subscribe(self, event_type: EventType, callback: Callable):
        """
        Subscribe to an event type.

        Args:
            event_type: Type of event to listen for
            callback: Function to call when event is emitted (can be sync or async)
        """
        self._subscribers[event_type].append(callback)
        logging.debug(f"[EventBus] Subscribed to {event_type}")

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """Unsubscribe from an event type."""
        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    async def emit(self, event_type: EventType, data: Dict[str, Any]):
        """
        Emit an event to all subscribers.

        Args:
            event_type: Type of event
            data: Event data payload
        """
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Notify subscribers
        subscribers = self._subscribers.get(event_type, [])
        logging.debug(f"[EventBus] Emitting {event_type} to {len(subscribers)} subscribers")

        for callback in subscribers:
            try:
                # Check if callback is async
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logging.error(f"[EventBus] Error in subscriber callback: {e}")

    def get_recent_events(self, event_type: EventType = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent events, optionally filtered by type."""
        if event_type:
            events = [e for e in self._event_history if e["type"] == event_type]
        else:
            events = self._event_history

        return events[-limit:]


# Global event bus instance
event_bus = EventBus()
