"""
Pytest configuration and fixtures for test isolation.

This ensures tests use a separate test database and don't pollute production data.
"""
import os
import pytest
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.models import Base


# Store original database path
ORIGINAL_DB_PATH = None
TEST_DB_PATH = None


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create a temporary test database for the entire test session."""
    global ORIGINAL_DB_PATH, TEST_DB_PATH

    # Save original database path
    from app.database.connection import DATABASE_URL
    ORIGINAL_DB_PATH = DATABASE_URL

    # Create temporary test database
    temp_dir = tempfile.gettempdir()
    TEST_DB_PATH = f"sqlite:///{temp_dir}/test_trading_bot.db"

    # Override database connection
    os.environ['TEST_DATABASE_URL'] = TEST_DB_PATH

    # Create test database schema
    engine = create_engine(TEST_DB_PATH.replace('sqlite:///', 'sqlite:///'))
    Base.metadata.create_all(engine)

    yield

    # Cleanup: remove test database
    try:
        db_file = TEST_DB_PATH.replace('sqlite:///', '')
        if os.path.exists(db_file):
            os.remove(db_file)
    except Exception as e:
        print(f"Warning: Could not remove test database: {e}")


@pytest.fixture(autouse=True)
def use_test_database(monkeypatch):
    """Ensure every test uses the test database."""
    global TEST_DB_PATH

    # Override database URL for this test
    monkeypatch.setenv('DATABASE_URL', TEST_DB_PATH)

    # Patch the database connection module
    from app.database import connection
    monkeypatch.setattr(connection, 'DATABASE_URL', TEST_DB_PATH)


@pytest.fixture
def db_session():
    """Provide a clean database session for each test."""
    from app.database.connection import get_db

    with get_db() as session:
        yield session
        session.rollback()


@pytest.fixture(autouse=True)
def clean_database():
    """Clean database before each test."""
    from app.database.connection import get_db
    from app.database.models import (
        Trade, Signal, Holding, ErrorLog, RSSFeed,
        SeenNews, BotStatus, StrategyPerformance, StrategyDefinition
    )

    with get_db() as db:
        # Clear all test data (order matters due to foreign keys)
        db.query(ErrorLog).delete()
        db.query(Holding).delete()
        db.query(Trade).delete()
        db.query(Signal).delete()
        db.query(SeenNews).delete()
        db.query(RSSFeed).delete()
        db.query(BotStatus).delete()
        db.query(StrategyPerformance).delete()
        db.query(StrategyDefinition).delete()
        db.commit()
