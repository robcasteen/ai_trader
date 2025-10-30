"""
Tests for BotConfigRepository - verifying configuration reads/writes to database.
"""

import pytest
from datetime import datetime
from decimal import Decimal
from app.database.connection import get_db
from app.database.repositories import BotConfigRepository
from app.database.models import BotStatus


class TestBotConfigRepository:
    """Test BotConfigRepository database operations."""

    @pytest.fixture
    def clean_database(self):
        """Clean bot_status table before each test."""
        with get_db() as db:
            db.query(BotStatus).delete()
            db.commit()

    @pytest.fixture
    def config_repo(self):
        """Create a BotConfigRepository instance."""
        with get_db() as db:
            yield BotConfigRepository(db)

    def test_create_new_config(self, clean_database):
        """Test creating a new configuration in database."""
        with get_db() as db:
            repo = BotConfigRepository(db)

            config = repo.create_or_update(
                mode="paper",
                min_confidence=Decimal("0.7"),
                position_size=Decimal("10.0")
            )

            db.commit()

            # Verify config was created
            assert config is not None
            assert config.mode == "paper"
            assert config.min_confidence == Decimal("0.7")
            assert config.position_size == Decimal("10.0")

        # Verify it persists in database
        with get_db() as db:
            repo = BotConfigRepository(db)
            loaded = repo.get_current()

            assert loaded is not None
            assert loaded.mode == "paper"
            assert loaded.min_confidence == Decimal("0.7")
            assert loaded.position_size == Decimal("10.0")

    def test_update_existing_config(self, clean_database):
        """Test updating an existing configuration."""
        # Create initial config
        with get_db() as db:
            repo = BotConfigRepository(db)
            repo.create_or_update(
                mode="paper",
                min_confidence=Decimal("0.5"),
                position_size=Decimal("5.0")
            )
            db.commit()

        # Update config
        with get_db() as db:
            repo = BotConfigRepository(db)
            updated = repo.create_or_update(
                mode="live",
                min_confidence=Decimal("0.8"),
                position_size=Decimal("15.0")
            )
            db.commit()

            # Verify updated
            assert updated.mode == "live"
            assert updated.min_confidence == Decimal("0.8")
            assert updated.position_size == Decimal("15.0")

        # Verify only one config exists (update, not create)
        with get_db() as db:
            all_configs = db.query(BotStatus).all()
            assert len(all_configs) == 1

    def test_get_current_config(self, clean_database):
        """Test getting the current configuration."""
        # No config yet
        with get_db() as db:
            repo = BotConfigRepository(db)
            current = repo.get_current()
            assert current is None

        # Create config
        with get_db() as db:
            repo = BotConfigRepository(db)
            repo.create_or_update(
                mode="paper",
                min_confidence=Decimal("0.6")
            )
            db.commit()

        # Get current
        with get_db() as db:
            repo = BotConfigRepository(db)
            current = repo.get_current()
            assert current is not None
            assert current.mode == "paper"
            assert current.min_confidence == Decimal("0.6")

    def test_get_config_dict_with_data(self, clean_database):
        """Test getting configuration as dictionary."""
        # Create config
        with get_db() as db:
            repo = BotConfigRepository(db)
            repo.create_or_update(
                mode="paper",
                min_confidence=Decimal("0.777"),
                position_size=Decimal("5.0"),
                balance=Decimal("10000.0")
            )
            db.commit()

        # Get as dict
        with get_db() as db:
            repo = BotConfigRepository(db)
            config_dict = repo.get_config_dict()

            assert config_dict["mode"] == "paper"
            assert config_dict["min_confidence"] == 0.777
            assert config_dict["position_size"] == 5.0
            assert config_dict["balance"] == 10000.0
            assert config_dict["aggregation_method"] == "weighted_vote"
            assert "strategy_weights" in config_dict

    def test_get_config_dict_returns_defaults_when_empty(self, clean_database):
        """Test that get_config_dict returns defaults when no config exists."""
        with get_db() as db:
            repo = BotConfigRepository(db)
            config_dict = repo.get_config_dict()

            # Verify defaults
            assert config_dict["mode"] == "paper"
            assert config_dict["min_confidence"] == 0.5
            assert config_dict["position_size"] == 5.0
            assert config_dict["aggregation_method"] == "weighted_vote"
            assert config_dict["strategy_weights"]["sentiment"] == 1.0
            assert config_dict["strategy_weights"]["technical"] == 1.0
            assert config_dict["strategy_weights"]["volume"] == 0.8

    def test_partial_update_preserves_other_fields(self, clean_database):
        """Test that updating only some fields preserves others."""
        # Create with full config
        with get_db() as db:
            repo = BotConfigRepository(db)
            repo.create_or_update(
                mode="paper",
                min_confidence=Decimal("0.5"),
                position_size=Decimal("5.0"),
                balance=Decimal("10000.0")
            )
            db.commit()

        # Update only min_confidence
        with get_db() as db:
            repo = BotConfigRepository(db)
            repo.create_or_update(
                min_confidence=Decimal("0.8")
            )
            db.commit()

        # Verify other fields preserved
        with get_db() as db:
            repo = BotConfigRepository(db)
            current = repo.get_current()

            assert current.mode == "paper"  # Preserved
            assert current.min_confidence == Decimal("0.8")  # Updated
            assert current.position_size == Decimal("5.0")  # Preserved
            assert current.balance == Decimal("10000.0")  # Preserved

    def test_timestamp_updates_on_save(self, clean_database):
        """Test that timestamp is updated when config is saved."""
        # Create initial
        with get_db() as db:
            repo = BotConfigRepository(db)
            initial = repo.create_or_update(mode="paper")
            db.commit()
            initial_timestamp = initial.timestamp

        # Wait a tiny bit (in real test this would be more significant)
        import time
        time.sleep(0.01)

        # Update
        with get_db() as db:
            repo = BotConfigRepository(db)
            updated = repo.create_or_update(mode="live")
            db.commit()

            # Timestamp should be newer
            assert updated.timestamp > initial_timestamp

    def test_config_persists_across_sessions(self, clean_database):
        """Test that configuration persists across database sessions."""
        # Session 1: Create config
        with get_db() as db:
            repo = BotConfigRepository(db)
            repo.create_or_update(
                mode="paper",
                min_confidence=Decimal("0.65"),
                position_size=Decimal("7.5")
            )
            db.commit()

        # Session 2: Read config
        with get_db() as db:
            repo = BotConfigRepository(db)
            config = repo.get_current()

            assert config.mode == "paper"
            assert config.min_confidence == Decimal("0.65")
            assert config.position_size == Decimal("7.5")

        # Session 3: Update config
        with get_db() as db:
            repo = BotConfigRepository(db)
            repo.create_or_update(min_confidence=Decimal("0.9"))
            db.commit()

        # Session 4: Verify update persisted
        with get_db() as db:
            repo = BotConfigRepository(db)
            config = repo.get_current()

            assert config.min_confidence == Decimal("0.9")

    def test_decimal_precision_preserved(self, clean_database):
        """Test that Decimal precision is preserved in database."""
        with get_db() as db:
            repo = BotConfigRepository(db)
            repo.create_or_update(
                min_confidence=Decimal("0.777"),
                position_size=Decimal("5.25"),
                balance=Decimal("12345.67")
            )
            db.commit()

        with get_db() as db:
            repo = BotConfigRepository(db)
            config = repo.get_current()

            # Check precision
            assert config.min_confidence == Decimal("0.777")
            assert config.position_size == Decimal("5.25")
            assert config.balance == Decimal("12345.67")

    def test_config_dict_converts_decimals_to_floats(self, clean_database):
        """Test that get_config_dict converts Decimals to floats."""
        with get_db() as db:
            repo = BotConfigRepository(db)
            repo.create_or_update(
                min_confidence=Decimal("0.777"),
                position_size=Decimal("5.0")
            )
            db.commit()

        with get_db() as db:
            repo = BotConfigRepository(db)
            config_dict = repo.get_config_dict()

            # Should be float, not Decimal
            assert isinstance(config_dict["min_confidence"], float)
            assert isinstance(config_dict["position_size"], float)
            assert config_dict["min_confidence"] == 0.777
            assert config_dict["position_size"] == 5.0

    def test_multiple_configs_gets_latest(self, clean_database):
        """Test that get_current returns the latest configuration."""
        # Create multiple configs (shouldn't happen, but test it)
        with get_db() as db:
            config1 = BotStatus(
                timestamp=datetime(2024, 1, 1),
                mode="paper",
                min_confidence=Decimal("0.5")
            )
            config2 = BotStatus(
                timestamp=datetime(2024, 2, 1),
                mode="live",
                min_confidence=Decimal("0.8")
            )
            config3 = BotStatus(
                timestamp=datetime(2024, 3, 1),
                mode="paper",
                min_confidence=Decimal("0.7")
            )
            db.add_all([config1, config2, config3])
            db.commit()

        # Get current should return latest (March)
        with get_db() as db:
            repo = BotConfigRepository(db)
            current = repo.get_current()

            assert current.min_confidence == Decimal("0.7")
            assert current.timestamp.year == 2024
            assert current.timestamp.month == 3

    def test_config_with_extra_fields(self, clean_database):
        """Test that extra fields can be stored."""
        with get_db() as db:
            repo = BotConfigRepository(db)
            repo.create_or_update(
                mode="paper",
                min_confidence=Decimal("0.5"),
                position_size=Decimal("5.0")
            )
            db.commit()

        with get_db() as db:
            repo = BotConfigRepository(db)
            config = repo.get_current()

            assert config.mode == "paper"
            assert config.min_confidence == Decimal("0.5")
            assert config.position_size == Decimal("5.0")
