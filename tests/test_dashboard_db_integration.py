"""
Tests for dashboard database integration.

These tests ensure dashboard endpoints correctly read from the database.
"""
import pytest
from datetime import datetime
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from unittest.mock import patch

from app.main import app
from app.database.models import Base
from app.database import connection as db_connection
from app.database.repositories import (
    SignalRepository, TradeRepository, RSSFeedRepository
)


@pytest.fixture
def test_db():
    """Create a test database."""
    import tempfile
    import os

    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)

    # Create engine with the temp file
    test_engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)

    # Create a shared session
    shared_session = TestSessionLocal()

    @contextmanager
    def mock_get_db():
        """Mock get_db that yields the shared session."""
        try:
            yield shared_session
        except Exception:
            shared_session.rollback()
            raise

    # Patch both locations where get_db is used
    with patch.object(db_connection, 'get_db', mock_get_db), \
         patch('app.dashboard.get_db', mock_get_db):
        yield shared_session

    # Clean up
    shared_session.close()
    test_engine.dispose()
    os.unlink(db_path)


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestStrategyEndpoint:
    """Test /api/strategy/current endpoint reads from database."""

    def test_strategy_endpoint_returns_db_data(self, test_db, client):
        """Test that strategy endpoint returns data from database."""
        # Insert test data
        repo = SignalRepository(test_db)
        signal = repo.create(
            timestamp=datetime.utcnow(),
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            final_signal="BUY",
            final_confidence=Decimal("0.85"),
            aggregation_method="weighted_vote",
            strategies={
                "sentiment": {"signal": "BUY", "confidence": 0.9},
                "technical": {"signal": "BUY", "confidence": 0.8}
            },
            test_mode=False
        )
        test_db.commit()

        # Call API endpoint
        response = client.get("/api/strategy/current")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] > 0
        assert any(s["symbol"] == "BTCUSD" for s in data["signals"])

    def test_strategy_endpoint_filters_test_data(self, test_db, client):
        """Test that strategy endpoint filters test mode signals."""
        repo = SignalRepository(test_db)

        # Production signal
        prod_signal = repo.create(
            timestamp=datetime.utcnow(),
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            final_signal="BUY",
            final_confidence=Decimal("0.85"),
            aggregation_method="weighted_vote",
            strategies={},
            test_mode=False
        )

        # Test signal
        test_signal = repo.create(
            timestamp=datetime.utcnow(),
            symbol="TESTUSD",
            price=Decimal("1.00"),
            final_signal="BUY",
            final_confidence=Decimal("1.00"),
            aggregation_method="test",
            strategies={},
            test_mode=True
        )
        test_db.commit()

        # Call API endpoint
        response = client.get("/api/strategy/current")

        assert response.status_code == 200
        data = response.json()
        symbols = [s["symbol"] for s in data["signals"]]
        assert "BTCUSD" in symbols
        assert "TESTUSD" not in symbols


class TestFeedsEndpoint:
    """Test /api/feeds endpoint reads from database."""

    def test_feeds_endpoint_returns_db_data(self, test_db, client):
        """Test that feeds endpoint returns data from database."""
        # Insert test data
        repo = RSSFeedRepository(test_db)
        feed = repo.create(
            url="https://example.com/rss",
            name="Example Feed",
            enabled=True,
            keywords=["bitcoin", "crypto"]
        )
        test_db.commit()

        # Call API endpoint
        response = client.get("/api/feeds")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["feeds"][0]["name"] == "Example Feed"
        assert data["feeds"][0]["url"] == "https://example.com/rss"

    def test_feeds_endpoint_includes_all_required_fields(self, test_db, client):
        """Test that feeds have all required fields."""
        repo = RSSFeedRepository(test_db)
        feed = repo.create(
            url="https://example.com/rss",
            name="Test Feed",
            enabled=True
        )
        test_db.commit()

        # Call API endpoint
        response = client.get("/api/feeds")

        assert response.status_code == 200
        data = response.json()
        feed_data = data["feeds"][0]

        # Dashboard expects these fields
        required_fields = ["id", "url", "name", "enabled", "active", "keywords"]
        for field in required_fields:
            assert field in feed_data, f"Missing required field: {field}"


