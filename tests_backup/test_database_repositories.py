"""
Tests for database repositories.

These tests ensure all database I/O operations work correctly.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base
from app.database.repositories import (
    SignalRepository, TradeRepository, HoldingRepository,
    RSSFeedRepository, PerformanceRepository
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()


class TestSignalRepository:
    """Test SignalRepository CRUD operations."""

    def test_create_signal(self, db_session):
        """Test creating a signal."""
        repo = SignalRepository(db_session)

        signal = repo.create(
            timestamp=datetime.utcnow(),
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            final_signal="BUY",
            final_confidence=Decimal("0.85"),
            aggregation_method="weighted_vote",
            strategies={"sentiment": {"signal": "BUY", "confidence": 0.9}},
            test_mode=False,
            bot_version="1.0.0"
        )

        assert signal.id is not None
        assert signal.symbol == "BTCUSD"
        assert signal.final_signal == "BUY"
        assert signal.final_confidence == Decimal("0.85")
        assert signal.test_mode is False

    def test_get_recent_signals(self, db_session):
        """Test getting recent signals."""
        repo = SignalRepository(db_session)

        # Create signals with different timestamps
        now = datetime.utcnow()
        old_signal = repo.create(
            timestamp=now - timedelta(hours=48),
            symbol="ETHUSD",
            price=Decimal("3000.00"),
            final_signal="SELL",
            final_confidence=Decimal("0.7"),
            aggregation_method="weighted_vote",
            strategies={},
            test_mode=False
        )

        recent_signal = repo.create(
            timestamp=now,
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            final_signal="BUY",
            final_confidence=Decimal("0.85"),
            aggregation_method="weighted_vote",
            strategies={},
            test_mode=False
        )

        db_session.commit()

        # Get recent signals (last 24 hours)
        recent = repo.get_recent(hours=24, test_mode=False)

        assert len(recent) == 1
        assert recent[0].symbol == "BTCUSD"

    def test_filter_by_test_mode(self, db_session):
        """Test filtering signals by test_mode."""
        repo = SignalRepository(db_session)

        # Create production signal
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

        # Create test signal
        test_signal = repo.create(
            timestamp=datetime.utcnow(),
            symbol="ETHUSD",
            price=Decimal("3000.00"),
            final_signal="SELL",
            final_confidence=Decimal("0.7"),
            aggregation_method="weighted_vote",
            strategies={},
            test_mode=True
        )

        db_session.commit()

        # Get only production signals
        prod_signals = repo.get_recent(test_mode=False)
        assert len(prod_signals) == 1
        assert prod_signals[0].symbol == "BTCUSD"

        # Get only test signals
        test_signals = repo.get_recent(test_mode=True)
        assert len(test_signals) == 1
        assert test_signals[0].symbol == "ETHUSD"


class TestTradeRepository:
    """Test TradeRepository CRUD operations."""

    def test_create_trade(self, db_session):
        """Test creating a trade."""
        repo = TradeRepository(db_session)

        trade = repo.create(
            timestamp=datetime.utcnow(),
            action="BUY",
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            amount=Decimal("0.1"),
            gross_value=Decimal("5000.00"),
            fee=Decimal("13.00"),
            net_value=Decimal("5013.00"),
            test_mode=False,
            reason="Strong buy signal"
        )

        assert trade.id is not None
        assert trade.action == "BUY"
        assert trade.symbol == "BTCUSD"
        assert trade.amount == Decimal("0.1")
        assert trade.test_mode is False

    def test_get_all_trades(self, db_session):
        """Test getting all trades."""
        repo = TradeRepository(db_session)

        # Create multiple trades
        trade1 = repo.create(
            timestamp=datetime.utcnow() - timedelta(hours=2),
            action="BUY",
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            amount=Decimal("0.1"),
            gross_value=Decimal("5000.00"),
            fee=Decimal("13.00"),
            net_value=Decimal("5013.00"),
            test_mode=False
        )

        trade2 = repo.create(
            timestamp=datetime.utcnow(),
            action="SELL",
            symbol="ETHUSD",
            price=Decimal("3000.00"),
            amount=Decimal("1.0"),
            gross_value=Decimal("3000.00"),
            fee=Decimal("7.80"),
            net_value=Decimal("2992.20"),
            test_mode=False
        )

        db_session.commit()

        all_trades = repo.get_all(test_mode=False)
        assert len(all_trades) == 2

    def test_filter_trades_by_test_mode(self, db_session):
        """Test filtering trades by test_mode."""
        repo = TradeRepository(db_session)

        # Create production trade
        prod_trade = repo.create(
            timestamp=datetime.utcnow(),
            action="BUY",
            symbol="BTCUSD",
            price=Decimal("50000.00"),
            amount=Decimal("0.1"),
            gross_value=Decimal("5000.00"),
            fee=Decimal("13.00"),
            net_value=Decimal("5013.00"),
            test_mode=False
        )

        # Create test trade with unrealistic values
        test_trade = repo.create(
            timestamp=datetime.utcnow(),
            action="BUY",
            symbol="ETHUSD",
            price=Decimal("1.00"),
            amount=Decimal("1000000.00"),
            gross_value=Decimal("1000000.00"),
            fee=Decimal("0.00"),
            net_value=Decimal("1000000.00"),
            test_mode=True
        )

        db_session.commit()

        # Get only production trades
        prod_trades = repo.get_all(test_mode=False)
        assert len(prod_trades) == 1
        assert prod_trades[0].symbol == "BTCUSD"

        # Get only test trades
        test_trades = repo.get_all(test_mode=True)
        assert len(test_trades) == 1
        assert test_trades[0].amount == Decimal("1000000.00")


class TestRSSFeedRepository:
    """Test RSSFeedRepository CRUD operations."""

    def test_create_feed(self, db_session):
        """Test creating an RSS feed."""
        repo = RSSFeedRepository(db_session)

        feed = repo.create(
            url="https://example.com/rss",
            name="Example Feed",
            enabled=True,
            keywords=["bitcoin", "crypto"]
        )

        assert feed.id is not None
        assert feed.url == "https://example.com/rss"
        assert feed.name == "Example Feed"
        assert feed.enabled is True
        assert feed.keywords == ["bitcoin", "crypto"]

    def test_get_all_feeds(self, db_session):
        """Test getting all feeds."""
        repo = RSSFeedRepository(db_session)

        feed1 = repo.create(
            url="https://example1.com/rss",
            name="Feed 1",
            enabled=True
        )

        feed2 = repo.create(
            url="https://example2.com/rss",
            name="Feed 2",
            enabled=False
        )

        db_session.commit()

        # Get all feeds
        all_feeds = repo.get_all()
        assert len(all_feeds) == 2

        # Get only enabled feeds
        enabled_feeds = repo.get_all(enabled_only=True)
        assert len(enabled_feeds) == 1
        assert enabled_feeds[0].name == "Feed 1"

    def test_get_feed_by_url(self, db_session):
        """Test getting feed by URL."""
        repo = RSSFeedRepository(db_session)

        original = repo.create(
            url="https://example.com/rss",
            name="Example Feed"
        )
        db_session.commit()

        found = repo.get_by_url("https://example.com/rss")
        assert found is not None
        assert found.id == original.id
        assert found.name == "Example Feed"

    def test_update_feed(self, db_session):
        """Test updating a feed."""
        repo = RSSFeedRepository(db_session)

        feed = repo.create(
            url="https://example.com/rss",
            name="Old Name",
            enabled=True
        )
        db_session.commit()

        updated = repo.update(feed.id, name="New Name", enabled=False)
        db_session.commit()

        assert updated.name == "New Name"
        assert updated.enabled is False

    def test_delete_feed(self, db_session):
        """Test deleting a feed."""
        repo = RSSFeedRepository(db_session)

        feed = repo.create(
            url="https://example.com/rss",
            name="To Delete"
        )
        db_session.commit()

        feed_id = feed.id
        result = repo.delete(feed_id)
        db_session.commit()

        assert result is True
        assert repo.get_by_id(feed_id) is None

    def test_feed_has_required_attributes(self, db_session):
        """Test that feed has all required attributes for dashboard."""
        repo = RSSFeedRepository(db_session)

        feed = repo.create(
            url="https://example.com/rss",
            name="Test Feed",
            enabled=True
        )
        db_session.commit()

        # These are the attributes the dashboard expects
        assert hasattr(feed, 'id')
        assert hasattr(feed, 'url')
        assert hasattr(feed, 'name')
        assert hasattr(feed, 'enabled')
        assert hasattr(feed, 'keywords')
        assert hasattr(feed, 'last_fetch')  # This was missing!
        assert hasattr(feed, 'last_error')  # This was missing!
        assert hasattr(feed, 'created_at')


class TestHoldingRepository:
    """Test HoldingRepository CRUD operations."""

    def test_create_holding(self, db_session):
        """Test creating a holding."""
        repo = HoldingRepository(db_session)

        holding = repo.create(
            timestamp=datetime.utcnow(),
            symbol="BTCUSD",
            amount=Decimal("0.5"),
            avg_buy_price=Decimal("50000.00"),
            current_price=Decimal("51000.00"),
            test_mode=False
        )

        assert holding.id is not None
        assert holding.symbol == "BTCUSD"
        assert holding.amount == Decimal("0.5")
        assert holding.test_mode is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
