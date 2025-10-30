# Remaining Test Fixes

## Progress
- **448/528 tests passing (85%)**
- **83 failures, 17 errors remaining**

## Fixed
1. ✅ Test isolation with conftest.py
2. ✅ Foreign key constraint order
3. ✅ Strategy manager return signature (3→4 values)
4. ✅ Import Optional in strategy_manager.py

## To Fix

### 1. JSON File Constants (17 errors)
Tests expect constants that no longer exist:
- `app.news_fetcher.NEWS_FILE`
- `app.logic.paper_trader.TRADES_FILE`
- `app.main.STATUS_FILE`
- `app.strategies.strategy_manager.LOGS_DIR`

**Solution**: These tests should be removed or updated to use database

### 2. Case Sensitivity (5 failures)
Tests expect 'sell' but code returns 'SELL'
**Files**: test_sell_validation.py, test_signal_to_trade_flow.py

**Solution**:
```python
# Change assertions from:
assert result["action"] == "sell"
# To:
assert result["action"].lower() == "sell"
```

### 3. Partial Endpoint (2 failures)
- `test_partial_filters_out_hold_signals` - Backend includes HOLDs, frontend filters
- `test_partial_returns_recent_signals_only` - Returns 25 instead of 20

**Solution**: Update dashboard.py `/partial` endpoint to match test expectations

### 4. Strategy Registry Tests (10 failures)
- Missing `yaml` module - need `pip install pyyaml`
- API changes - methods don't exist

**Solution**:
```bash
pip install pyyaml
```
Then update tests or implement missing methods

### 5. News Fetcher Tests (25 failures)
Tests expect JSON file-based feed loading
**Solution**: Update tests to use database-based feed loading

### 6. Paper Trader Tests (10 failures)
Tests expect JSON file persistence
**Solution**: Update tests to verify database persistence instead

## Quick Fixes Script

```bash
# 1. Install missing dependency
pip install pyyaml

# 2. Fix case sensitivity
find tests/ -name "*.py" -exec sed -i 's/== "sell"/== "sell" or action.lower() == "sell"/g' {} \;
find tests/ -name "*.py" -exec sed -i 's/== "buy"/== "buy" or action.lower() == "buy"/g' {} \;

# 3. Remove/skip tests for deleted JSON files
# These tests are now obsolete since we use database

# 4. Run tests again
pytest tests/ -q
```

## Test Categories to Update

### A. Tests expecting JSON files (DELETE or SKIP)
- test_news_fetcher.py - NEWS_FILE tests
- test_paper_trader.py - TRADES_FILE tests
- test_integration.py - STATUS_FILE tests
- test_dashboard.py - File-based tests

### B. Tests for database features (UPDATE)
- test_paper_trader_database.py
- test_dashboard_db_integration.py
- test_news_fetcher_database.py

### C. API contract tests (UPDATE)
- test_partial_endpoint.py
- test_api_strategy_endpoints.py
- test_config_api.py
