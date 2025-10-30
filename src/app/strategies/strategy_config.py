"""
Strategy Configuration - Configuration management for trading strategies.

Allows strategies to be configured, enabled/disabled, and weighted dynamically.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
import json
import yaml
from pathlib import Path
import logging


@dataclass
class StrategyConfig:
    """Configuration for a single strategy."""

    name: str
    enabled: bool = True
    weight: float = 1.0
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyConfig":
        """
        Create config from dict.

        Args:
            data: Config dict

        Returns:
            StrategyConfig instance
        """
        return cls(
            name=data["name"],
            enabled=data.get("enabled", True),
            weight=data.get("weight", 1.0),
            params=data.get("params", {}),
            description=data.get("description", "")
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert config to dict.

        Returns:
            Config dict
        """
        return asdict(self)

    def update(self, **kwargs):
        """Update config fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


class StrategyConfigLoader:
    """Loads and manages strategy configurations."""

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize config loader.

        Args:
            config_file: Path to configuration file (JSON or YAML)
        """
        self.config_file = config_file
        self._configs: Dict[str, StrategyConfig] = {}

    def load_from_list(self, configs: List[Dict[str, Any]]) -> List[StrategyConfig]:
        """
        Load configs from list of dicts.

        Args:
            configs: List of config dicts

        Returns:
            List of StrategyConfig objects
        """
        loaded = []
        for config_dict in configs:
            config = StrategyConfig.from_dict(config_dict)
            self._configs[config.name] = config
            loaded.append(config)

        return loaded

    def load_from_file(self, file_path: Path) -> List[StrategyConfig]:
        """
        Load configs from JSON or YAML file.

        Args:
            file_path: Path to config file

        Returns:
            List of StrategyConfig objects

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")

        with open(file_path, 'r') as f:
            if file_path.suffix == '.json':
                data = json.load(f)
            elif file_path.suffix in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")

        # Handle both list and dict with 'strategies' key
        if isinstance(data, list):
            configs = data
        elif isinstance(data, dict) and 'strategies' in data:
            configs = data['strategies']
        else:
            raise ValueError("Config file must contain a list or dict with 'strategies' key")

        return self.load_from_list(configs)

    def save_to_file(self, file_path: Path):
        """
        Save current configs to file.

        Args:
            file_path: Path to save config file
        """
        configs_list = [config.to_dict() for config in self._configs.values()]

        with open(file_path, 'w') as f:
            if file_path.suffix == '.json':
                json.dump({"strategies": configs_list}, f, indent=2)
            elif file_path.suffix in ['.yaml', '.yml']:
                yaml.dump({"strategies": configs_list}, f, default_flow_style=False)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")

        logging.info(f"[StrategyConfig] Saved {len(configs_list)} configs to {file_path}")

    def get(self, name: str) -> Optional[StrategyConfig]:
        """
        Get config by strategy name.

        Args:
            name: Strategy name

        Returns:
            StrategyConfig or None if not found
        """
        return self._configs.get(name)

    def get_enabled(self) -> List[StrategyConfig]:
        """
        Get all enabled strategy configs.

        Returns:
            List of enabled configs
        """
        return [config for config in self._configs.values() if config.enabled]

    def get_all(self) -> List[StrategyConfig]:
        """
        Get all strategy configs.

        Returns:
            List of all configs
        """
        return list(self._configs.values())

    def update_config(self, name: str, **kwargs):
        """
        Update a strategy's config.

        Args:
            name: Strategy name
            **kwargs: Fields to update
        """
        if name in self._configs:
            self._configs[name].update(**kwargs)
            logging.info(f"[StrategyConfig] Updated config for {name}: {kwargs}")
        else:
            logging.warning(f"[StrategyConfig] Strategy {name} not found")

    def add_config(self, config: StrategyConfig):
        """
        Add a new strategy config.

        Args:
            config: StrategyConfig to add
        """
        self._configs[config.name] = config
        logging.info(f"[StrategyConfig] Added config for {config.name}")

    def remove_config(self, name: str):
        """
        Remove a strategy config.

        Args:
            name: Strategy name
        """
        if name in self._configs:
            del self._configs[name]
            logging.info(f"[StrategyConfig] Removed config for {name}")


def create_default_config() -> List[Dict[str, Any]]:
    """
    Create default strategy configuration.

    Returns:
        List of default config dicts
    """
    return [
        {
            "name": "sentiment",
            "enabled": True,
            "weight": 1.0,
            "params": {
                "min_confidence": 0.5
            },
            "description": "Sentiment analysis from news headlines"
        },
        {
            "name": "technical",
            "enabled": True,
            "weight": 1.0,
            "params": {
                "sma_period": 20,
                "rsi_period": 14,
                "rsi_overbought": 70,
                "rsi_oversold": 30
            },
            "description": "Technical indicators (SMA, RSI, Momentum)"
        },
        {
            "name": "volume",
            "enabled": True,
            "weight": 0.8,
            "params": {
                "spike_threshold": 2.0,
                "obv_sensitivity": 0.1
            },
            "description": "Volume analysis and OBV"
        }
    ]
