"""
Database connection management.

Simple, resilient SQLite connection with session management.
"""
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database.models import Base

logger = logging.getLogger(__name__)

# Database file location
DB_DIR = Path(__file__).parent.parent.parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "trading_bot.db"

# Connection string
DATABASE_URL = f"sqlite:///{DB_PATH}"


# Enable WAL mode and foreign keys for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Configure SQLite for optimal performance and safety."""
    cursor = dbapi_conn.cursor()

    # Write-Ahead Logging for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL")

    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys=ON")

    # Synchronous=NORMAL is safe with WAL and faster
    cursor.execute("PRAGMA synchronous=NORMAL")

    # Cache size (negative number = KB, so -64000 = 64MB)
    cursor.execute("PRAGMA cache_size=-64000")

    # Temp store in memory
    cursor.execute("PRAGMA temp_store=MEMORY")

    cursor.close()


# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL logging during development
    connect_args={
        "check_same_thread": False,  # Allow multiple threads (safe with proper session management)
        "timeout": 30  # 30 second timeout for locks
    },
    poolclass=StaticPool,  # Single connection pool for SQLite
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def init_db():
    """Initialize database - create all tables."""
    try:
        logger.info(f"Initializing database at: {DB_PATH}")
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")

        # Log database info
        logger.info(f"Database location: {DB_PATH.absolute()}")
        logger.info(f"Database size: {DB_PATH.stat().st_size if DB_PATH.exists() else 0} bytes")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def drop_all_tables():
    """Drop all tables - USE WITH CAUTION!"""
    logger.warning("Dropping all database tables!")
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Get database session context manager.

    Usage:
        with get_db() as db:
            signal = db.query(Signal).first()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session() -> Session:
    """
    Get database session (for dependency injection in FastAPI).

    Usage in FastAPI:
        @app.get("/")
        def route(db: Session = Depends(get_db_session)):
            ...
    """
    session = SessionLocal()
    try:
        return session
    except Exception:
        session.close()
        raise


def close_db_session(session: Session):
    """Close a database session."""
    try:
        session.close()
    except Exception as e:
        logger.error(f"Error closing session: {e}")


def health_check() -> dict:
    """
    Check database health.

    Returns:
        dict with status, database info
    """
    try:
        with get_db() as db:
            # Try a simple query
            result = db.execute("SELECT 1").scalar()

            return {
                "status": "healthy",
                "database": str(DB_PATH),
                "size_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
                "connection_test": result == 1,
                "wal_enabled": db.execute("PRAGMA journal_mode").scalar() == "wal"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "database": str(DB_PATH)
        }


def get_table_counts() -> dict:
    """Get row counts for all tables."""
    from app.database.models import (
        Signal, Trade, Holding, StrategyPerformance,
        StrategyDefinition, ErrorLog, RSSFeed, SeenNews, BotStatus
    )

    counts = {}
    with get_db() as db:
        counts["signals"] = db.query(Signal).count()
        counts["trades"] = db.query(Trade).count()
        counts["holdings"] = db.query(Holding).count()
        counts["strategy_performance"] = db.query(StrategyPerformance).count()
        counts["strategy_definitions"] = db.query(StrategyDefinition).count()
        counts["error_logs"] = db.query(ErrorLog).count()
        counts["rss_feeds"] = db.query(RSSFeed).count()
        counts["seen_news"] = db.query(SeenNews).count()
        counts["bot_status"] = db.query(BotStatus).count()

        # Test vs Production split
        counts["test_signals"] = db.query(Signal).filter(Signal.test_mode == True).count()
        counts["prod_signals"] = db.query(Signal).filter(Signal.test_mode == False).count()
        counts["test_trades"] = db.query(Trade).filter(Trade.test_mode == True).count()
        counts["prod_trades"] = db.query(Trade).filter(Trade.test_mode == False).count()

    return counts


# Initialize database on module import
try:
    init_db()
except Exception as e:
    logger.error(f"Failed to initialize database on import: {e}")
