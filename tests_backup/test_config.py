"""
Unit tests for config module.

Tests cover:
- Configuration loading and defaults
- Strategy normalization
- Config updates with whitelisting
- File persistence
"""

import pytest
import json
from pathlib import Path
from app.config import get_current_config, update_config, DEFAULT_CONFIG


@pytest.fixture
def temp_config_file(tmp_path, monkeypatch):
    """Fixture providing a temporary config file."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    
    # Patch the module-level constants
    import app.config as config_module
    monkeypatch.setattr(config_module, 'CONFIG_DIR', config_dir)
    monkeypatch.setattr(config_module, 'CONFIG_FILE', config_file)
    
    return config_file


class TestGetCurrentConfig:
    def test_default_config_no_file(self, temp_config_file):
        """Test default config when file doesn't exist."""
        config = get_current_config()
        
        assert config["strategy"] == "gpt-sentiment"
        assert config["interval_minutes"] == 5

    def test_load_existing_config(self, temp_config_file):
        """Test loading existing configuration."""
        existing_config = {
            "strategy": "gpt-sentiment",
            "interval_minutes": 10
        }
        temp_config_file.write_text(json.dumps(existing_config))
        
        config = get_current_config()
        
        assert config["strategy"] == "gpt-sentiment"
        assert config["interval_minutes"] == 10

    def test_strategy_normalization_gpt_to_gpt_sentiment(self, temp_config_file):
        """Test that 'gpt' strategy is normalized to 'gpt-sentiment'."""
        temp_config_file.write_text(json.dumps({"strategy": "gpt"}))
        
        config = get_current_config()
        
        assert config["strategy"] == "gpt-sentiment"

    def test_overlay_defaults_on_partial_config(self, temp_config_file):
        """Test that defaults are overlaid on partial configs."""
        partial_config = {"strategy": "custom"}
        temp_config_file.write_text(json.dumps(partial_config))
        
        config = get_current_config()
        
        assert config["strategy"] == "custom"
        assert config["interval_minutes"] == 5  # From defaults

    def test_corrupted_config_file_returns_defaults(self, temp_config_file):
        """Test that corrupted config file returns defaults."""
        temp_config_file.write_text("{ invalid json }")
        
        config = get_current_config()
        
        assert config == DEFAULT_CONFIG


class TestUpdateConfig:
    def test_update_strategy(self, temp_config_file):
        """Test updating strategy configuration."""
        new_config = update_config({"strategy": "gpt-sentiment"})
        
        assert new_config["strategy"] == "gpt-sentiment"
        assert temp_config_file.exists()
        
        # Verify file contents
        saved = json.loads(temp_config_file.read_text())
        assert saved["strategy"] == "gpt-sentiment"

    def test_update_interval(self, temp_config_file):
        """Test updating interval_minutes."""
        new_config = update_config({"interval_minutes": 15})
        
        assert new_config["interval_minutes"] == 15

    def test_update_multiple_values(self, temp_config_file):
        """Test updating multiple config values."""
        new_config = update_config({
            "strategy": "gpt-sentiment",
            "interval_minutes": 20
        })
        
        assert new_config["strategy"] == "gpt-sentiment"
        assert new_config["interval_minutes"] == 20

    def test_update_ignores_non_whitelisted_keys(self, temp_config_file):
        """Test that non-whitelisted keys are ignored."""
        new_config = update_config({
            "strategy": "gpt-sentiment",
            "malicious_key": "bad_value",
            "another_bad_key": 123
        })
        
        assert "malicious_key" not in new_config
        assert "another_bad_key" not in new_config
        assert new_config["strategy"] == "gpt-sentiment"

    def test_update_preserves_existing_values(self, temp_config_file):
        """Test that update preserves other existing values."""
        # Set initial config
        temp_config_file.write_text(json.dumps({
            "strategy": "gpt-sentiment",
            "interval_minutes": 5
        }))
        
        # Update only strategy
        new_config = update_config({"strategy": "custom"})
        
        assert new_config["strategy"] == "custom"
        assert new_config["interval_minutes"] == 5  # Preserved

    def test_update_creates_file_if_missing(self, temp_config_file):
        """Test that update creates config file if it doesn't exist."""
        assert not temp_config_file.exists()
        
        update_config({"strategy": "gpt-sentiment"})
        
        assert temp_config_file.exists()

    def test_update_returns_full_config(self, temp_config_file):
        """Test that update returns complete config with defaults."""
        new_config = update_config({"strategy": "custom"})
        
        # Should include both updated and default values
        assert "strategy" in new_config
        assert "interval_minutes" in new_config

    def test_whitelisted_keys_only(self, temp_config_file):
        """Test that only whitelisted keys can be updated."""
        allowed_keys = {"strategy", "interval_minutes"}
        
        new_config = update_config({
            "strategy": "test",
            "interval_minutes": 10,
            "unauthorized": "value"
        })
        
        for key in new_config:
            assert key in allowed_keys or key in DEFAULT_CONFIG


class TestConfigPersistence:
    def test_config_persists_across_reads(self, temp_config_file):
        """Test that config changes persist across multiple reads."""
        update_config({"strategy": "custom", "interval_minutes": 25})
        
        config1 = get_current_config()
        config2 = get_current_config()
        
        assert config1 == config2
        assert config1["strategy"] == "custom"
        assert config1["interval_minutes"] == 25

    def test_json_formatting(self, temp_config_file):
        """Test that saved JSON is properly formatted."""
        update_config({"strategy": "gpt-sentiment"})
        
        content = temp_config_file.read_text()
        # Should be valid JSON with indentation
        parsed = json.loads(content)
        assert isinstance(parsed, dict)
        assert "\n" in content  # Has formatting


class TestEdgeCases:
    def test_empty_update(self, temp_config_file):
        """Test update with empty dict."""
        config = update_config({})
        
        assert config == DEFAULT_CONFIG

    def test_none_values(self, temp_config_file):
        """Test handling of None values in update."""
        config = update_config({"strategy": None})
        
        # Should still update with None
        assert config["strategy"] is None

    def test_numeric_strategy(self, temp_config_file):
        """Test handling of non-string strategy value."""
        config = update_config({"strategy": 12345})
        
        assert config["strategy"] == 12345