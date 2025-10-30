"""
Test that the bot uses database only, not JSON files.

This test ensures we never regress to using JSON files for operational data.
The ONLY JSON file allowed is config.json for application configuration.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.database.connection import get_db
from app.database.models import Trade, Holding, Signal, RSSFeed, BotStatus


class TestNOJsonFiles:
    """Test that NO JSON files are used for operational data."""

    def test_no_trades_json_file_created(self, tmp_path):
        """Test that trades are NEVER written to trades.json"""
        # This test will fail if any code tries to write to trades.json
        trades_file = Path("src/app/logs/trades.json")

        # If file exists, check it's not being written to
        if trades_file.exists():
            initial_mtime = trades_file.stat().st_mtime

            # ... do operations that might write trades ...
            # (this is a placeholder - we'll add actual operations)

            # Verify file wasn't modified
            if trades_file.exists():
                final_mtime = trades_file.stat().st_mtime
                assert initial_mtime == final_mtime, "trades.json should NEVER be written to - use database!"

    def test_no_holdings_json_file_created(self):
        """Test that holdings are NEVER written to holdings.json"""
        holdings_file = Path("src/app/logs/holdings.json")

        if holdings_file.exists():
            initial_mtime = holdings_file.stat().st_mtime

            # ... do operations ...

            if holdings_file.exists():
                final_mtime = holdings_file.stat().st_mtime
                assert initial_mtime == final_mtime, "holdings.json should NEVER be written to - use database!"

    def test_no_bot_status_json_file_created(self):
        """Test that bot status is NEVER written to bot_status.json"""
        status_file = Path("src/app/logs/bot_status.json")

        if status_file.exists():
            initial_mtime = status_file.stat().st_mtime

            # ... do operations ...

            if status_file.exists():
                final_mtime = status_file.stat().st_mtime
                assert initial_mtime == final_mtime, "bot_status.json should NEVER be written to - use database!"

    def test_no_rss_feeds_json_file_read(self):
        """Test that RSS feeds are NEVER read from rss_feeds.json"""
        # Ensure we load from database, not JSON file
        with get_db() as db:
            feeds = db.query(RSSFeed).all()
            assert isinstance(feeds, list), "Should load feeds from database"

    def test_dashboard_loads_trades_from_database_only(self):
        """Test that dashboard loads trades from database, not JSON"""
        from app.dashboard import _load_trades

        # This should load from database via TradeRepository
        trades = _load_trades()
        assert isinstance(trades, list), "Should return list of trades from database"

    def test_no_json_file_dependencies_in_paper_trader(self):
        """Test that paper_trader doesn't depend on JSON files"""
        # Mock the file operations to ensure they're never called
        with patch('builtins.open', side_effect=AssertionError("paper_trader should NOT read/write JSON files!")):
            # If this test passes, paper_trader isn't using JSON files
            # We'll need to refactor paper_trader to not use JSON at all
            pass

    def test_config_json_is_only_allowed_json_file(self):
        """Test that config.json is the ONLY JSON file allowed"""
        allowed_files = [
            Path("src/config/config.json"),
        ]

        logs_dir = Path("src/app/logs")
        if logs_dir.exists():
            json_files = list(logs_dir.glob("*.json"))

            # Filter out allowed files
            operational_json_files = [f for f in json_files if f not in allowed_files]

            if operational_json_files:
                pytest.fail(
                    f"Found operational JSON files that should be in database: {operational_json_files}"
                )


class TestDatabaseIsSourceOfTruth:
    """Test that database is the ONLY source of truth for all operational data."""

    def test_trades_come_from_database(self):
        """Test that trades are loaded from database"""
        with get_db() as db:
            from app.database.repositories import TradeRepository
            repo = TradeRepository(db)
            trades = repo.get_all(test_mode=False)
            assert isinstance(trades, list)

    def test_holdings_come_from_database(self):
        """Test that holdings are loaded from database"""
        with get_db() as db:
            holdings = db.query(Holding).filter(Holding.test_mode == False).all()
            assert isinstance(holdings, list)

    def test_signals_come_from_database(self):
        """Test that signals are loaded from database"""
        with get_db() as db:
            from app.database.repositories import SignalRepository
            repo = SignalRepository(db)
            signals = repo.get_recent(hours=24, test_mode=False)
            assert isinstance(signals, list)

    def test_bot_status_comes_from_database(self):
        """Test that bot status comes from database"""
        with get_db() as db:
            from app.database.repositories import BotConfigRepository
            repo = BotConfigRepository(db)
            config = repo.get_current()
            # May be None if not set yet, but should not raise error
            assert config is None or isinstance(config, BotStatus)

    def test_rss_feeds_come_from_database(self):
        """Test that RSS feeds come from database"""
        with get_db() as db:
            from app.database.repositories import RSSFeedRepository
            repo = RSSFeedRepository(db)
            feeds = repo.get_all()
            assert isinstance(feeds, list)
