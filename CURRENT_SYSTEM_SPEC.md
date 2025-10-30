# Current System Specification - What We Actually Built

## Core Functionality (What Needs Testing)

### 1. Database-Based Trading System

**NOT JSON files** - System uses SQLite database

#### Models:
- `Signal` - Trading signals from strategies
- `Trade` - Executed trades
- `Holding` - Current positions
- `RSSFeed` - News feed sources
- `ErrorLog` - System errors
- `BotStatus` - Bot state

#### Repositories:
- `SignalRepository` - CRUD for signals
- `TradeRepository` - CRUD for trades
- `HoldingRepository` - CRUD for holdings
- `RSSFeedRepository` - CRUD for feeds

### 2. Strategy Manager

**Returns**: `(signal: str, confidence: float, reason: str, signal_id: Optional[int])`

**Aggregation Methods**:
- `weighted_vote` - Weight strategies by confidence
- `highest_confidence` - Use highest confidence signal
- `unanimous` - Require agreement

**Writes signals to database** via `StrategySignalLogger`

### 3. Paper Trader

**Executes trades** and writes to database:
- Creates `Trade` records
- Updates `Holding` records
- Links trades to signals via `signal_id`

**Case**: Actions stored as UPPERCASE ("BUY", "SELL", "HOLD")

### 4. Dashboard API

**Endpoints**:
- `GET /partial?signal_limit=50` - Returns signals, trades, sentiment
- `GET /status` - Bot status
- `GET /api/balance` - Account balance
- `GET /api/health` - System health
- `GET /` - Dashboard HTML

**Signal filtering**: Backend includes ALL signals, frontend filters HOLDs

### 5. Symbol Format

**Canonical**: `BTCUSD`, `ETHUSD` (no slashes)
**Normalizer**: Converts variations → canonical

---

## Test Suite Requirements

### Test File 1: `test_database_integration.py`

```python
"""Test that all components use database, not JSON files."""

class TestDatabaseIntegration:
    def test_signals_written_to_database(self):
        """Strategy manager writes signals to DB."""

    def test_trades_written_to_database(self):
        """Paper trader writes trades to DB."""

    def test_holdings_written_to_database(self):
        """Paper trader writes holdings to DB."""

    def test_rss_feeds_loaded_from_database(self):
        """News fetcher loads feeds from DB."""

    def test_no_json_files_created(self):
        """System doesn't create trades.json, holdings.json, etc."""
```

### Test File 2: `test_strategy_manager_current.py`

```python
"""Test strategy manager with current 4-value return."""

class TestStrategyManagerAPI:
    def test_returns_four_values(self):
        """get_signal() returns (signal, confidence, reason, signal_id)."""

    def test_writes_signal_to_database(self):
        """Each call creates signal record in DB."""

    def test_weighted_vote_aggregation(self):
        """Weighted vote produces correct signal."""

    def test_confidence_threshold(self):
        """Signals below threshold converted to HOLD."""

    def test_signal_id_returned(self):
        """signal_id matches DB record ID."""
```

### Test File 3: `test_paper_trader_current.py`

```python
"""Test paper trader with current database implementation."""

class TestPaperTraderDatabase:
    def test_buy_creates_trade_record(self):
        """BUY action creates Trade in database."""

    def test_buy_creates_holding_record(self):
        """BUY action creates/updates Holding."""

    def test_sell_creates_trade_record(self):
        """SELL action creates Trade in database."""

    def test_sell_updates_holding_record(self):
        """SELL action reduces Holding amount."""

    def test_hold_creates_no_records(self):
        """HOLD action creates no Trade or Holding."""

    def test_trade_links_to_signal(self):
        """Trade record has signal_id foreign key."""

    def test_holding_links_to_signal_and_trade(self):
        """Holding has entry_signal_id and entry_trade_id."""

    def test_actions_stored_uppercase(self):
        """Trade.action stored as 'BUY'/'SELL' not 'buy'/'sell'."""

    def test_symbol_normalized(self):
        """Symbols stored in canonical format (BTCUSD)."""
```

### Test File 4: `test_dashboard_api_current.py`

```python
"""Test dashboard API with current implementation."""

class TestPartialEndpoint:
    def test_returns_signals_from_database(self):
        """GET /partial returns signals from DB."""

    def test_returns_trades_from_database(self):
        """GET /partial returns trades from DB."""

    def test_signal_limit_parameter_works(self):
        """signal_limit parameter limits results."""

    def test_includes_hold_signals(self):
        """Backend includes HOLD signals (frontend filters)."""

    def test_marks_executed_signals(self):
        """Signals have 'executed' flag based on trades."""

class TestStatusEndpoint:
    def test_returns_bot_status_from_database(self):
        """GET /status returns status from DB."""

class TestBalanceEndpoint:
    def test_returns_paper_trading_balance(self):
        """GET /api/balance returns calculated balance."""
```

### Test File 5: `test_symbol_normalization_current.py`

```python
"""Test symbol normalization."""

class TestSymbolNormalization:
    def test_btc_slash_usd_normalized(self):
        """'BTC/USD' → 'BTCUSD'."""

    def test_lowercase_normalized(self):
        """'btcusd' → 'BTCUSD'."""

    def test_kraken_format_normalized(self):
        """'XBTCUSD' → 'BTCUSD'."""

    def test_canonical_format_unchanged(self):
        """'BTCUSD' stays 'BTCUSD'."""

    def test_normalization_in_paper_trader(self):
        """Paper trader normalizes before storing."""

    def test_normalization_in_strategy_manager(self):
        """Strategy manager normalizes before processing."""
```

### Test File 6: `test_data_integrity_current.py`

```python
"""Test data relationships and integrity."""

class TestDataIntegrity:
    def test_trade_references_valid_signal(self):
        """Trade.signal_id points to existing Signal."""

    def test_holding_references_valid_trade(self):
        """Holding.entry_trade_id points to existing Trade."""

    def test_holding_references_valid_signal(self):
        """Holding.entry_signal_id points to existing Signal."""

    def test_cannot_delete_signal_with_trades(self):
        """Foreign key constraint prevents orphaning."""

    def test_test_mode_isolation(self):
        """test_mode=True data separate from production."""
```

---

## Tests to DELETE (Obsolete)

These test JSON file functionality that no longer exists:

```bash
# Delete entire test files
rm tests/test_news_fetcher.py  # Tests NEWS_FILE
rm tests/test_integration.py   # Tests STATUS_FILE

# Delete specific tests in test_paper_trader.py
- test_trades_persisted_to_file
- test_multiple_trades_appended
- test_corrupted_file_recovery
- test_holdings_persisted_to_file

# Delete specific tests in test_paper_trader_hold.py
- test_hold_does_not_execute_trade (expects TRADES_FILE)
- test_buy_executes_correctly (expects TRADES_FILE)
- test_sell_executes_correctly (expects TRADES_FILE)

# Delete tests in test_dashboard.py that expect file loading
- test_status_with_bot_status_file
- Tests expecting file-based sentiment loading
```

---

## Implementation Plan

### Step 1: Clean Slate
```bash
cd /home/rcasteen/kraken-ai-bot

# Backup current tests
mkdir -p tests_backup
cp -r tests/* tests_backup/

# Delete obsolete tests
rm tests/test_news_fetcher.py
rm tests/test_integration.py
rm tests/test_news_fetcher_fixed.py
```

### Step 2: Write New Core Tests
Create the 6 test files above testing CURRENT functionality

### Step 3: Run Tests (They Should Mostly Pass)
```bash
source .venv/bin/activate
export PYTHONPATH=src
pytest tests/test_database_integration.py -v
pytest tests/test_strategy_manager_current.py -v
pytest tests/test_paper_trader_current.py -v
pytest tests/test_dashboard_api_current.py -v
pytest tests/test_symbol_normalization_current.py -v
pytest tests/test_data_integrity_current.py -v
```

### Step 4: Fix Any Failures
Follow TDD: Test fails → Fix code → Test passes

### Step 5: Keep Good Existing Tests
Many existing tests ARE testing current functionality:
- `test_sentiment_strategy.py` ✅
- `test_technical_strategy.py` ✅
- `test_volume_strategy.py` ✅
- `test_risk_manager.py` ✅
- `test_performance_tracker.py` ✅
- `test_kraken_client.py` ✅

Just update them if they expect 3-value returns instead of 4.

---

## Success Criteria

**All tests should**:
1. Test CURRENT functionality (database-based)
2. NOT expect JSON files
3. Handle 4-value strategy manager returns
4. Expect uppercase actions ('BUY'/'SELL')
5. Expect canonical symbol format ('BTCUSD')
6. Use test database (not production)

**Result**:
- Clear test suite documenting actual system behavior
- No obsolete tests confusing developers
- All tests passing
- Confidence to refactor/improve code
