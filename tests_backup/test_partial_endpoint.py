"""
Test that GET /partial endpoint returns signals from database.

The /partial endpoint is used by the dashboard to populate multiple panels including
the recent signals panel. It should return signals from the database, not from JSON files.
"""

import pytest
from fastapi.testclient import TestClient
from decimal import Decimal
from datetime import datetime, timezone
from app.main import app
from app.database.connection import get_db
from app.database.repositories import SignalRepository
from app.database.models import Signal


class TestPartialEndpoint:
    """Test that /partial endpoint returns database signals."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def clean_database(self):
        """Clean signals table before each test."""
        with get_db() as db:
            db.query(Signal).delete()
            db.commit()

    def test_partial_returns_signals_from_database(self, client, clean_database):
        """Test that /partial endpoint includes signals from database."""
        # Create test signals in database
        with get_db() as db:
            signal_repo = SignalRepository(db)

            # Create a BUY signal
            signal_repo.create(
                timestamp=datetime.now(timezone.utc),
                symbol="BTCUSD",
                final_signal="BUY",
                final_confidence=Decimal("0.75"),
                price=Decimal("50000"),
                strategies={
                    "sentiment": {"signal": "BUY", "confidence": 0.8},
                    "technical": {"signal": "BUY", "confidence": 0.7}
                },
                aggregation_method="weighted_vote",
                test_mode=False
            )

            # Create a SELL signal
            signal_repo.create(
                timestamp=datetime.now(timezone.utc),
                symbol="ETHUSD",
                final_signal="SELL",
                final_confidence=Decimal("0.65"),
                price=Decimal("4000"),
                strategies={
                    "sentiment": {"signal": "SELL", "confidence": 0.7},
                    "technical": {"signal": "SELL", "confidence": 0.6}
                },
                aggregation_method="weighted_vote",
                test_mode=False
            )

            db.commit()

        # Call /partial endpoint
        response = client.get("/partial")
        assert response.status_code == 200

        data = response.json()

        # Verify response includes signals
        assert "signals" in data, "/partial response should include 'signals' key"
        signals = data["signals"]

        assert len(signals) >= 2, "Should return at least the 2 signals we created"

        # Find our test signals
        btc_signal = next((s for s in signals if s["symbol"] == "BTCUSD"), None)
        eth_signal = next((s for s in signals if s["symbol"] == "ETHUSD"), None)

        assert btc_signal is not None, "Should include BTCUSD signal"
        assert btc_signal["signal"] == "BUY"
        assert btc_signal["confidence"] == 0.75

        assert eth_signal is not None, "Should include ETHUSD signal"
        assert eth_signal["signal"] == "SELL"
        assert eth_signal["confidence"] == 0.65

    def test_partial_filters_out_hold_signals(self, client, clean_database):
        """Test that /partial endpoint filters out HOLD signals (showing only BUY/SELL)."""
        with get_db() as db:
            signal_repo = SignalRepository(db)

            # Create a HOLD signal
            signal_repo.create(
                timestamp=datetime.now(timezone.utc),
                symbol="DOGEUSD",
                final_signal="HOLD",
                final_confidence=Decimal("0.15"),
                price=Decimal("0.20"),
                strategies={
                    "sentiment": {"signal": "HOLD", "confidence": 0.1},
                    "technical": {"signal": "HOLD", "confidence": 0.2}
                },
                aggregation_method="weighted_vote",
                test_mode=False
            )

            # Create a BUY signal
            signal_repo.create(
                timestamp=datetime.now(timezone.utc),
                symbol="BTCUSD",
                final_signal="BUY",
                final_confidence=Decimal("0.80"),
                price=Decimal("50000"),
                strategies={
                    "sentiment": {"signal": "BUY", "confidence": 0.8},
                    "technical": {"signal": "BUY", "confidence": 0.8}
                },
                aggregation_method="weighted_vote",
                test_mode=False
            )

            db.commit()

        # Call /partial endpoint
        response = client.get("/partial")
        data = response.json()

        signals = data.get("signals", [])

        # Should only include BUY signal, not HOLD
        btc_signal = next((s for s in signals if s["symbol"] == "BTCUSD"), None)
        doge_signal = next((s for s in signals if s["symbol"] == "DOGEUSD"), None)

        assert btc_signal is not None, "Should include BUY signal"
        assert doge_signal is None, "Should NOT include HOLD signal"

    def test_partial_returns_recent_signals_only(self, client, clean_database):
        """Test that /partial returns only recent signals (e.g., last 20)."""
        with get_db() as db:
            signal_repo = SignalRepository(db)

            # Create many signals
            for i in range(25):
                signal_repo.create(
                    timestamp=datetime.now(timezone.utc),
                    symbol=f"TEST{i}USD",
                    final_signal="BUY" if i % 2 == 0 else "SELL",
                    final_confidence=Decimal("0.70"),
                    price=Decimal("100"),
                    strategies={
                        "sentiment": {"signal": "BUY", "confidence": 0.7}
                    },
                    aggregation_method="weighted_vote",
                    test_mode=False
                )

            db.commit()

        # Call /partial endpoint
        response = client.get("/partial")
        data = response.json()

        signals = data.get("signals", [])

        # Should limit to recent signals (e.g., 20)
        assert len(signals) <= 20, "Should return at most 20 recent signals"

    def test_partial_signal_format(self, client, clean_database):
        """Test that signals in /partial response have correct format."""
        with get_db() as db:
            signal_repo = SignalRepository(db)

            signal_repo.create(
                timestamp=datetime.now(timezone.utc),
                symbol="BTCUSD",
                final_signal="BUY",
                final_confidence=Decimal("0.75"),
                price=Decimal("50000"),
                strategies={
                    "sentiment": {"signal": "BUY", "confidence": 0.8},
                    "technical": {"signal": "BUY", "confidence": 0.7}
                },
                aggregation_method="weighted_vote",
                test_mode=False
            )

            db.commit()

        # Call /partial endpoint
        response = client.get("/partial")
        data = response.json()

        signals = data.get("signals", [])
        assert len(signals) > 0

        signal = signals[0]

        # Verify signal has required fields for dashboard
        assert "symbol" in signal
        assert "signal" in signal
        assert "confidence" in signal
        assert "price" in signal
        assert "timestamp" in signal

        # Verify types
        assert isinstance(signal["symbol"], str)
        assert signal["signal"] in ["BUY", "SELL", "HOLD"]
        assert isinstance(signal["confidence"], (int, float))
        assert isinstance(signal["price"], (int, float))
