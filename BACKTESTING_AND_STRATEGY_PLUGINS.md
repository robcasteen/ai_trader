# Backtesting & Strategy Plugin System

## Overview

We've implemented a comprehensive backtesting system with a pluggable strategy architecture using Test-Driven Development (TDD).

## What's Been Built

### 1. Backtesting System

#### Components:
- **[BacktestEngine](src/app/backtesting/backtest_engine.py)** - Core backtesting engine
- **[BacktestPortfolio](src/app/backtesting/backtest_engine.py)** - Portfolio simulation with realistic fees
- **[PerformanceAnalyzer](src/app/backtesting/performance_metrics.py)** - Comprehensive metrics calculator

#### Test Coverage:
- ✅ Portfolio initialization
- ✅ Buy/sell order execution
- ✅ Fee calculation (0.26% Kraken fees)
- ✅ Portfolio valuation
- ✅ Multiple position management
- ⚠️  1 test failing (partial sell - minor bug)

### 2. Strategy Plugin System

#### Components:
- **[StrategyRegistry](src/app/strategies/strategy_registry.py)** - Global strategy registry
- **[StrategyConfig](src/app/strategies/strategy_config.py)** - Configuration management
- **[strategies.yaml](config/strategies.yaml)** - User-editable strategy configuration

#### Features:
- ✅ Register/unregister strategies dynamically
- ✅ Enable/disable strategies via configuration
- ✅ Adjustable strategy weights
- ✅ Per-strategy parameters
- ✅ YAML/JSON configuration file support
- ⚠️  Needs StrategyManager integration (in progress)

## How to Use

### Running Backtests

```bash
# Quick test (7 days, BTC + ETH)
PYTHONPATH=src python scripts/run_backtest.py --quick

# Custom backtest
PYTHONPATH=src python scripts/run_backtest.py \
  --symbols XXBTZUSD XETHZUSD SOLUSD \
  --days 30 \
  --capital 10000 \
  --interval 60

# Save results to JSON
PYTHONPATH=src python scripts/run_backtest.py \
  --days 30 \
  --output results.json
```

### Configuring Strategies

Edit `config/strategies.yaml`:

```yaml
strategies:
  - name: sentiment
    enabled: true
    weight: 1.0
    params:
      min_confidence: 0.5

  - name: technical
    enabled: true
    weight: 1.5
    params:
      sma_period: 20
      rsi_period: 14

  - name: volume
    enabled: false  # Disable this strategy
    weight: 0.8
```

### Creating Custom Strategies

1. **Create your strategy class**:

```python
# src/app/strategies/my_strategy.py
from app.strategies.base_strategy import BaseStrategy

class MyCustomStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params or {})

    def analyze(self, symbol, price, **kwargs):
        # Your logic here
        return {
            "signal": "BUY",  # or "SELL", "HOLD"
            "confidence": 0.75,
            "reason": "My custom analysis"
        }

    def get_signal(self, symbol, price, **kwargs):
        return self.analyze(symbol, price, **kwargs)
```

2. **Register it**:

```python
from app.strategies.strategy_registry import register_strategy
from app.strategies.my_strategy import MyCustomStrategy

register_strategy(
    "my_custom",
    MyCustomStrategy,
    description="My custom trading strategy",
    version="1.0.0"
)
```

3. **Add to config**:

```yaml
strategies:
  - name: my_custom
    enabled: true
    weight: 2.0
    params:
      custom_param: value
```

## What's Left to Implement

### Critical (for tests to pass):

1. **Install PyYAML**:
   ```bash
   pip install pyyaml
   ```

2. **Fix BacktestPortfolio partial sell** - Position should remain when partially sold

3. **Extend StrategyManager** with:
   - `add_strategy(strategy, weight, enabled)`
   - `remove_strategy(name)`
   - `enable_strategy(name)`
   - `disable_strategy(name)`
   - `update_strategy_weight(name, weight)`
   - `get_active_strategies()`
   - Load strategies from config file

### Nice to Have:

4. **Strategy Management API/CLI**:
   ```bash
   # List all strategies
   python scripts/manage_strategies.py list

   # Enable/disable
   python scripts/manage_strategies.py enable sentiment
   python scripts/manage_strategies.py disable volume

   # Update weights
   python scripts/manage_strategies.py set-weight technical 2.0
   ```

5. **Backtest Comparison Tool**:
   - Compare multiple backtest runs
   - A/B test different strategy configurations
   - Generate comparison reports

6. **Visualization**:
   - Plot equity curves
   - Drawdown charts
   - Trade distribution

## Test Status

### Passing (15/27):
- ✅ All StrategyRegistry tests (5/5)
- ✅ Most BacktestPortfolio tests (9/10)
- ✅ One StrategyManager test (1/12)

### Failing (12/27):
- ❌ PyYAML not installed (6 tests)
- ❌ StrategyManager missing methods (5 tests)
- ❌ BacktestPortfolio partial sell bug (1 test)

## Running Tests

```bash
# Run all backtest tests
PYTHONPATH=src pytest tests/test_backtest_portfolio.py -v

# Run strategy registry tests
PYTHONPATH=src pytest tests/test_strategy_registry.py -v

# Run all tests
PYTHONPATH=src pytest tests/ -v
```

## Architecture Diagram

```
┌─────────────────────────────────────────┐
│         Strategy Registry               │
│  (Global plugin system)                 │
│  - register()                           │
│  - unregister()                         │
│  - list_strategies()                    │
└──────────────┬──────────────────────────┘
               │
               ├─────> SentimentStrategy
               ├─────> TechnicalStrategy
               ├─────> VolumeStrategy
               └─────> CustomStrategy (your own!)

┌─────────────────────────────────────────┐
│      Strategy Configuration             │
│  (YAML/JSON files)                      │
│  - Enable/disable                       │
│  - Weights                              │
│  - Parameters                           │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│       Strategy Manager                  │
│  (Orchestrates strategies)              │
│  - load_from_config()                   │
│  - generate_signal()                    │
│  - aggregate_signals()                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│      Backtest Engine                    │
│  - Fetch historical data                │
│  - Replay through strategies            │
│  - Simulate trading                     │
│  - Calculate metrics                    │
└─────────────────────────────────────────┘
```

## Next Steps

1. **Install PyYAML**: `pip install pyyaml`
2. **Fix failing tests** (see TODO items above)
3. **Run your first backtest**: `PYTHONPATH=src python scripts/run_backtest.py --quick`
4. **Create your first custom strategy**
5. **Compare strategy configurations** to find optimal weights

## Benefits

✅ **Test historical performance** before risking real money
✅ **Optimize strategy weights** based on data
✅ **Rapidly prototype new strategies** with plugin system
✅ **A/B test** different configurations
✅ **Identify which strategies work** for which market conditions
