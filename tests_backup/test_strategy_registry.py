"""
Tests for Strategy Registry - TDD approach for pluggable strategy system.
"""

import pytest
from app.strategies.base_strategy import BaseStrategy


class TestStrategyRegistry:
    """Test strategy registration and loading system."""

    def test_register_strategy_class(self):
        """Test registering a strategy class."""
        from app.strategies.strategy_registry import StrategyRegistry

        registry = StrategyRegistry()

        # Create a mock strategy
        class MockStrategy(BaseStrategy):
            def analyze(self, **kwargs):
                return {"signal": "HOLD", "confidence": 0.5}

        registry.register("mock", MockStrategy)

        assert "mock" in registry.list_strategies()
        assert registry.get("mock") == MockStrategy

    def test_register_duplicate_strategy_raises_error(self):
        """Test that registering duplicate strategy name raises error."""
        from app.strategies.strategy_registry import StrategyRegistry

        registry = StrategyRegistry()

        class Strategy1(BaseStrategy):
            def analyze(self, **kwargs):
                return {"signal": "HOLD"}

        class Strategy2(BaseStrategy):
            def analyze(self, **kwargs):
                return {"signal": "BUY"}

        registry.register("test", Strategy1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register("test", Strategy2)

    def test_get_nonexistent_strategy_raises_error(self):
        """Test getting a strategy that doesn't exist raises error."""
        from app.strategies.strategy_registry import StrategyRegistry

        registry = StrategyRegistry()

        with pytest.raises(KeyError, match="not found"):
            registry.get("nonexistent")

    def test_list_all_strategies(self):
        """Test listing all registered strategies."""
        from app.strategies.strategy_registry import StrategyRegistry

        registry = StrategyRegistry()

        class Strategy1(BaseStrategy):
            def analyze(self, **kwargs):
                return {}

        class Strategy2(BaseStrategy):
            def analyze(self, **kwargs):
                return {}

        registry.register("strategy1", Strategy1)
        registry.register("strategy2", Strategy2)

        strategies = registry.list_strategies()
        assert "strategy1" in strategies
        assert "strategy2" in strategies
        assert len(strategies) == 2

    def test_unregister_strategy(self):
        """Test unregistering a strategy."""
        from app.strategies.strategy_registry import StrategyRegistry

        registry = StrategyRegistry()

        class MockStrategy(BaseStrategy):
            def analyze(self, **kwargs):
                return {}

        registry.register("mock", MockStrategy)
        assert "mock" in registry.list_strategies()

        registry.unregister("mock")
        assert "mock" not in registry.list_strategies()


class TestStrategyConfiguration:
    """Test strategy configuration and activation system."""

    def test_load_strategy_config_from_dict(self):
        """Test loading strategy configuration from dict."""
        from app.strategies.strategy_config import StrategyConfig

        config_dict = {
            "name": "technical",
            "enabled": True,
            "weight": 1.5,
            "params": {
                "sma_period": 20,
                "rsi_period": 14
            }
        }

        config = StrategyConfig.from_dict(config_dict)

        assert config.name == "technical"
        assert config.enabled is True
        assert config.weight == 1.5
        assert config.params["sma_period"] == 20

    def test_strategy_config_default_values(self):
        """Test strategy configuration has sensible defaults."""
        from app.strategies.strategy_config import StrategyConfig

        config = StrategyConfig(name="test")

        assert config.enabled is True
        assert config.weight == 1.0
        assert config.params == {}

    def test_strategy_config_to_dict(self):
        """Test converting strategy config to dict."""
        from app.strategies.strategy_config import StrategyConfig

        config = StrategyConfig(
            name="volume",
            enabled=False,
            weight=0.8,
            params={"threshold": 2.0}
        )

        config_dict = config.to_dict()

        assert config_dict["name"] == "volume"
        assert config_dict["enabled"] is False
        assert config_dict["weight"] == 0.8
        assert config_dict["params"]["threshold"] == 2.0

    def test_load_multiple_strategy_configs(self):
        """Test loading multiple strategy configurations."""
        from app.strategies.strategy_config import StrategyConfigLoader

        configs = [
            {"name": "sentiment", "enabled": True, "weight": 1.0},
            {"name": "technical", "enabled": True, "weight": 1.5},
            {"name": "volume", "enabled": False, "weight": 0.8}
        ]

        loader = StrategyConfigLoader()
        loaded_configs = loader.load_from_list(configs)

        assert len(loaded_configs) == 3
        assert loaded_configs[0].name == "sentiment"
        assert loaded_configs[1].enabled is True
        assert loaded_configs[2].enabled is False

    def test_filter_enabled_strategies(self):
        """Test filtering only enabled strategies."""
        from app.strategies.strategy_config import StrategyConfigLoader

        configs = [
            {"name": "sentiment", "enabled": True},
            {"name": "technical", "enabled": False},
            {"name": "volume", "enabled": True}
        ]

        loader = StrategyConfigLoader()
        all_configs = loader.load_from_list(configs)
        enabled_configs = [c for c in all_configs if c.enabled]

        assert len(enabled_configs) == 2
        assert all(c.enabled for c in enabled_configs)


class TestStrategyManager:
    """Test StrategyManager with configurable strategies."""

    def test_initialize_with_config(self):
        """Test StrategyManager initializes with configuration."""
        from app.strategies.strategy_manager import StrategyManager

        config = {
            "strategies": [
                {"name": "sentiment", "enabled": True, "weight": 1.0},
                {"name": "technical", "enabled": True, "weight": 1.5},
                {"name": "volume", "enabled": False, "weight": 0.8}
            ]
        }

        manager = StrategyManager(config=config)

        # Should only have 2 strategies (volume is disabled)
        assert len(manager.strategies) == 2

    def test_add_strategy_dynamically(self):
        """Test adding a strategy to manager at runtime."""
        from app.strategies.strategy_manager import StrategyManager
        from app.strategies.base_strategy import BaseStrategy

        manager = StrategyManager()
        initial_count = len(manager.strategies)

        class CustomStrategy(BaseStrategy):
            def analyze(self, **kwargs):
                return {"signal": "BUY", "confidence": 0.8}

        manager.add_strategy(CustomStrategy(), weight=2.0, enabled=True)

        assert len(manager.strategies) == initial_count + 1

    def test_remove_strategy_dynamically(self):
        """Test removing a strategy from manager at runtime."""
        from app.strategies.strategy_manager import StrategyManager

        config = {
            "strategies": [
                {"name": "sentiment", "enabled": True},
                {"name": "technical", "enabled": True}
            ]
        }

        manager = StrategyManager(config=config)
        initial_count = len(manager.strategies)

        manager.remove_strategy("sentiment")

        assert len(manager.strategies) == initial_count - 1

    def test_enable_disabled_strategy(self):
        """Test enabling a previously disabled strategy."""
        from app.strategies.strategy_manager import StrategyManager

        config = {
            "strategies": [
                {"name": "volume", "enabled": False}
            ]
        }

        manager = StrategyManager(config=config)
        assert len(manager.strategies) == 0

        manager.enable_strategy("volume")
        assert len(manager.strategies) == 1

    def test_disable_enabled_strategy(self):
        """Test disabling an enabled strategy."""
        from app.strategies.strategy_manager import StrategyManager

        config = {
            "strategies": [
                {"name": "technical", "enabled": True}
            ]
        }

        manager = StrategyManager(config=config)
        assert len(manager.strategies) == 1

        manager.disable_strategy("technical")
        assert len(manager.strategies) == 0

    def test_update_strategy_weight(self):
        """Test updating a strategy's weight."""
        from app.strategies.strategy_manager import StrategyManager

        config = {
            "strategies": [
                {"name": "sentiment", "enabled": True, "weight": 1.0}
            ]
        }

        manager = StrategyManager(config=config)

        manager.update_strategy_weight("sentiment", 2.5)

        # Verify weight was updated in signal generation
        # This would need to check internal state or behavior

    def test_get_active_strategies_list(self):
        """Test getting list of currently active strategies."""
        from app.strategies.strategy_manager import StrategyManager

        config = {
            "strategies": [
                {"name": "sentiment", "enabled": True},
                {"name": "technical", "enabled": True},
                {"name": "volume", "enabled": False}
            ]
        }

        manager = StrategyManager(config=config)
        active = manager.get_active_strategies()

        assert len(active) == 2
        assert "sentiment" in [s.name for s in active]
        assert "technical" in [s.name for s in active]
        assert "volume" not in [s.name for s in active]
