"""
Strategy Registry - Centralized registry for pluggable trading strategies.

This allows dynamic registration, discovery, and management of trading strategies.
"""

from typing import Dict, Type, List
import logging

from app.strategies.base_strategy import BaseStrategy


class StrategyRegistry:
    """
    Global registry for trading strategies.

    Allows strategies to be registered, discovered, and instantiated dynamically.
    """

    def __init__(self):
        """Initialize empty strategy registry."""
        self._strategies: Dict[str, Type[BaseStrategy]] = {}
        self._metadata: Dict[str, Dict] = {}

    def register(
        self,
        name: str,
        strategy_class: Type[BaseStrategy],
        description: str = "",
        version: str = "1.0.0",
        author: str = ""
    ):
        """
        Register a strategy class.

        Args:
            name: Unique strategy name (e.g., "technical", "sentiment")
            strategy_class: Strategy class (must inherit from BaseStrategy)
            description: Human-readable description
            version: Strategy version
            author: Strategy author

        Raises:
            ValueError: If strategy name is already registered
            TypeError: If strategy_class doesn't inherit from BaseStrategy
        """
        if name in self._strategies:
            raise ValueError(f"Strategy '{name}' is already registered")

        if not issubclass(strategy_class, BaseStrategy):
            raise TypeError(f"Strategy must inherit from BaseStrategy")

        self._strategies[name] = strategy_class
        self._metadata[name] = {
            "description": description,
            "version": version,
            "author": author,
            "class": strategy_class.__name__
        }

        logging.info(f"[StrategyRegistry] Registered strategy: {name} v{version}")

    def unregister(self, name: str):
        """
        Unregister a strategy.

        Args:
            name: Strategy name to remove

        Raises:
            KeyError: If strategy not found
        """
        if name not in self._strategies:
            raise KeyError(f"Strategy '{name}' not found in registry")

        del self._strategies[name]
        del self._metadata[name]

        logging.info(f"[StrategyRegistry] Unregistered strategy: {name}")

    def get(self, name: str) -> Type[BaseStrategy]:
        """
        Get a strategy class by name.

        Args:
            name: Strategy name

        Returns:
            Strategy class

        Raises:
            KeyError: If strategy not found
        """
        if name not in self._strategies:
            raise KeyError(f"Strategy '{name}' not found in registry")

        return self._strategies[name]

    def list_strategies(self) -> List[str]:
        """
        Get list of all registered strategy names.

        Returns:
            List of strategy names
        """
        return list(self._strategies.keys())

    def get_metadata(self, name: str) -> Dict:
        """
        Get metadata for a strategy.

        Args:
            name: Strategy name

        Returns:
            Metadata dict

        Raises:
            KeyError: If strategy not found
        """
        if name not in self._metadata:
            raise KeyError(f"Strategy '{name}' not found in registry")

        return self._metadata[name].copy()

    def list_all_with_metadata(self) -> List[Dict]:
        """
        Get list of all strategies with their metadata.

        Returns:
            List of dicts with name and metadata
        """
        return [
            {"name": name, **metadata}
            for name, metadata in self._metadata.items()
        ]

    def instantiate(self, name: str, **kwargs) -> BaseStrategy:
        """
        Instantiate a strategy by name.

        Args:
            name: Strategy name
            **kwargs: Arguments to pass to strategy constructor

        Returns:
            Strategy instance

        Raises:
            KeyError: If strategy not found
        """
        strategy_class = self.get(name)
        return strategy_class(**kwargs)


# Global singleton registry
_global_registry = StrategyRegistry()


def get_registry() -> StrategyRegistry:
    """Get the global strategy registry."""
    return _global_registry


def register_strategy(name: str, strategy_class: Type[BaseStrategy], **kwargs):
    """
    Convenience function to register a strategy globally.

    Args:
        name: Strategy name
        strategy_class: Strategy class
        **kwargs: Additional metadata (description, version, author)
    """
    _global_registry.register(name, strategy_class, **kwargs)


def register_builtin_strategies():
    """Register all built-in strategies."""
    from app.strategies.sentiment_strategy import SentimentStrategy
    from app.strategies.technical_strategy import TechnicalStrategy
    from app.strategies.volume_strategy import VolumeStrategy

    register_strategy(
        "sentiment",
        SentimentStrategy,
        description="Sentiment analysis based on news headlines",
        version="1.0.0",
        author="Trading Bot"
    )

    register_strategy(
        "technical",
        TechnicalStrategy,
        description="Technical analysis using SMA, RSI, and momentum",
        version="1.0.0",
        author="Trading Bot"
    )

    register_strategy(
        "volume",
        VolumeStrategy,
        description="Volume analysis and OBV indicators",
        version="1.0.0",
        author="Trading Bot"
    )


# Auto-register built-in strategies on import
register_builtin_strategies()
