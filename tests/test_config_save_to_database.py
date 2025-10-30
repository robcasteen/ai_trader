"""
Test that POST /api/config saves configuration to the database.

This test ensures that when the settings modal saves config via POST /api/config,
the configuration is persisted to the database (not just the JSON file).
"""

import pytest
import json
from decimal import Decimal
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import get_db
from app.database.repositories import BotConfigRepository
from app.database.models import BotStatus


class TestConfigSavesToDatabase:
    """Test that /api/config POST saves to database."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def clean_database(self):
        """Clean bot_status table before each test."""
        with get_db() as db:
            db.query(BotStatus).delete()
            db.commit()

    def test_post_config_saves_min_confidence_to_database(self, client, clean_database):
        """Test that POST /api/config saves min_confidence to database."""
        # Send config update via API (like the settings modal does)
        config_data = {
            "config": {
                "aggregation": {
                    "min_confidence": 0.5
                },
                "trading_mode": "paper",
                "risk_management": {
                    "position_size_percent": 5.0
                }
            }
        }

        response = client.post("/api/config", json=config_data)
        assert response.status_code == 200

        # Verify it was saved to database
        with get_db() as db:
            config_repo = BotConfigRepository(db)
            db_config = config_repo.get_current()

            assert db_config is not None, "Config should be saved to database"
            assert db_config.min_confidence == Decimal("0.5"), "min_confidence should be 0.5 in database"

    def test_post_config_saves_trading_mode_to_database(self, client, clean_database):
        """Test that POST /api/config saves trading_mode to database."""
        config_data = {
            "config": {
                "trading_mode": "paper",
                "aggregation": {
                    "min_confidence": 0.777
                }
            }
        }

        response = client.post("/api/config", json=config_data)
        assert response.status_code == 200

        # Verify it was saved to database
        with get_db() as db:
            config_repo = BotConfigRepository(db)
            db_config = config_repo.get_current()

            assert db_config is not None
            assert db_config.mode == "paper"

    def test_post_config_saves_position_size_to_database(self, client, clean_database):
        """Test that POST /api/config saves position_size to database."""
        config_data = {
            "config": {
                "risk_management": {
                    "position_size_percent": 10.0
                },
                "aggregation": {
                    "min_confidence": 0.5
                }
            }
        }

        response = client.post("/api/config", json=config_data)
        assert response.status_code == 200

        # Verify it was saved to database
        with get_db() as db:
            config_repo = BotConfigRepository(db)
            db_config = config_repo.get_current()

            assert db_config is not None
            assert db_config.position_size == Decimal("10.0")

    def test_post_config_updates_existing_database_config(self, client, clean_database):
        """Test that POST /api/config updates existing database config."""
        # Create initial config in database
        with get_db() as db:
            config_repo = BotConfigRepository(db)
            config_repo.create_or_update(
                mode="paper",
                min_confidence=Decimal("0.5"),
                position_size=Decimal("5.0")
            )
            db.commit()

        # Update via API
        config_data = {
            "config": {
                "aggregation": {
                    "min_confidence": 0.777
                },
                "risk_management": {
                    "position_size_percent": 8.0
                }
            }
        }

        response = client.post("/api/config", json=config_data)
        assert response.status_code == 200

        # Verify database was updated
        with get_db() as db:
            config_repo = BotConfigRepository(db)
            db_config = config_repo.get_current()

            assert db_config.min_confidence == Decimal("0.777")
            assert db_config.position_size == Decimal("8.0")

        # Verify only one config exists (update, not create new)
        with get_db() as db:
            all_configs = db.query(BotStatus).all()
            assert len(all_configs) == 1

    def test_settings_modal_workflow_saves_to_database(self, client, clean_database):
        """Test complete workflow: user saves settings via modal, config is in database."""
        # This simulates the exact workflow from the dashboard settings modal

        # User opens settings modal and saves with 50% min confidence
        settings_from_modal = {
            "config": {
                "strategy": "gpt-sentiment",
                "interval_minutes": 5,
                "trading_fee_percent": 0.26,
                "strategies": {
                    "sentiment": {"enabled": True, "weight": 1.5},
                    "technical": {"enabled": True, "weight": 1.0},
                    "volume": {"enabled": False, "weight": 0.8}
                },
                "aggregation": {
                    "method": "weighted_vote",
                    "min_confidence": 0.5  # User sets 50%
                },
                "risk_management": {
                    "position_size_percent": 5.0,
                    "max_daily_loss_percent": 10,
                    "max_open_positions": None
                },
                "trading_mode": "paper",
                "paper_starting_capital": 200
            }
        }

        # Save via API
        response = client.post("/api/config", json=settings_from_modal)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify the trade cycle will load this config from database
        with get_db() as db:
            config_repo = BotConfigRepository(db)

            # This is what the trade cycle calls
            config_dict = config_repo.get_config_dict()

            # Verify trade cycle will use user's 50% threshold
            assert config_dict["min_confidence"] == 0.5, "Trade cycle should use 50% min_confidence from database"
            assert config_dict["mode"] == "paper"
            assert config_dict["position_size"] == 5.0

    def test_config_persists_after_bot_restart_simulation(self, client, clean_database):
        """Test that saved config persists across 'bot restarts' (database sessions)."""
        # Save config in one session
        config_data = {
            "config": {
                "aggregation": {"min_confidence": 0.65},
                "trading_mode": "paper"
            }
        }
        client.post("/api/config", json=config_data)

        # Simulate bot restart by starting new database session
        with get_db() as db:
            config_repo = BotConfigRepository(db)
            loaded_config = config_repo.get_config_dict()

            # Config should still be there
            assert loaded_config["min_confidence"] == 0.65
            assert loaded_config["mode"] == "paper"

    def test_post_config_does_not_write_to_json_file(self, client, clean_database, tmp_path):
        """Test that POST /api/config does NOT write to JSON file (database only)."""
        # Create a temporary test config file path
        test_config_file = tmp_path / "config.json"

        # Send config update via API
        config_data = {
            "config": {
                "aggregation": {"min_confidence": 0.8},
                "trading_mode": "paper",
                "risk_management": {"position_size_percent": 7.0}
            }
        }

        response = client.post("/api/config", json=config_data)
        assert response.status_code == 200

        # Verify JSON file was NOT written
        config_file = Path("src/config/config.json")

        # Get file modification time before and after
        if config_file.exists():
            initial_mtime = config_file.stat().st_mtime

            # Make another config update
            config_data["config"]["aggregation"]["min_confidence"] = 0.9
            response = client.post("/api/config", json=config_data)
            assert response.status_code == 200

            # Verify file was NOT modified
            final_mtime = config_file.stat().st_mtime
            assert initial_mtime == final_mtime, "Config file should not be modified by /api/config"

        # Verify config WAS saved to database
        with get_db() as db:
            config_repo = BotConfigRepository(db)
            db_config = config_repo.get_current()
            assert db_config is not None
            assert db_config.min_confidence == Decimal("0.9")
