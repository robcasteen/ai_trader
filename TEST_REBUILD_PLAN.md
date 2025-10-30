# Test Rebuild Plan - Fresh Start with TDD

## What I Did

### ✅ Completed:
1. **Backed up all tests** to `tests_backup/`
2. **Deleted obsolete tests** that validate JSON files:
   - `test_news_fetcher.py` - Tested NEWS_FILE (doesn't exist)
   - `test_integration.py` - Tested STATUS_FILE (doesn't exist)
   - `test_news_fetcher_fixed.py` - Tested NEWS_FILE
3. **Documented current system** in `CURRENT_SYSTEM_SPEC.md`
4. **Created test specifications** for what needs testing

### 📊 Current State:
- Tests backed up to `tests_backup/`
- 3 obsolete test files deleted
- Test isolation working (`conftest.py`)
- Many existing tests ARE good (test current functionality)

---

## What Needs to Happen Next

### Phase 1: Run Remaining Tests (5 min)

```bash
cd /home/rcasteen/kraken-ai-bot
source .venv/bin/activate
export PYTHONPATH=src

# Kill background processes
pkill -9 -f pytest
pkill -9 -f uvicorn

# Run tests
pytest tests/ -v --tb=short | tee current_test_status.txt
```

**Expected**: Should have FEWER failures now (deleted ~30 obsolete tests)

### Phase 2: Identify Good vs Bad Tests (10 min)

**Good Tests** (Keep these - they test current functionality):
- `test_sentiment_strategy.py` ✅
- `test_technical_strategy.py` ✅
- `test_volume_strategy.py` ✅
- `test_risk_manager.py` ✅
- `test_performance_tracker.py` ✅
- `test_kraken_client.py` ✅
- `test_symbol_normalizer.py` ✅
- `test_paper_trader_database.py` ✅ (tests DB writes)
- `test_dashboard_db_integration.py` ✅ (tests DB reads)
- `test_strategy_manager.py` ✅ (just needs 4-value update - DONE)

**Tests Needing Updates** (Fix to match current API):
- `test_paper_trader.py` - Remove JSON file tests, keep logic tests
- `test_paper_trader_hold.py` - Remove TRADES_FILE expectations
- `test_dashboard.py` - Remove file-based tests
- `test_partial_endpoint.py` - Update HOLD filtering expectations
- `test_sell_validation.py` - Fix case sensitivity
- `test_signal_to_trade_flow.py` - Fix case sensitivity, 4-value returns

**Tests to Delete** (Obsolete or duplicate):
- `test_no_json_files.py` - Purpose unclear
- Any remaining tests expecting JSON files

### Phase 3: Fix Individual Test Files (2-3 hours)

For EACH test file, follow TDD:

#### Example: `test_paper_trader.py`

**Step 1**: Read the test file
```bash
cat tests/test_paper_trader.py
```

**Step 2**: Identify what needs fixing
- Tests expecting `TRADES_FILE`? → DELETE those tests
- Tests validating trade logic? → KEEP and update if needed

**Step 3**: Fix the file
```python
# DELETE these tests (obsolete):
def test_trades_persisted_to_file():  # DELETE
def test_corrupted_file_recovery():    # DELETE
def test_holdings_persisted_to_file(): # DELETE

# KEEP these tests (valid business logic):
def test_execute_buy_trade():  # KEEP - validates buy logic
def test_execute_sell_trade(): # KEEP - validates sell logic
def test_default_amount():     # KEEP - validates amount calculation
```

**Step 4**: Run just that test file
```bash
pytest tests/test_paper_trader.py -v
```

**Step 5**: Fix any failures
- Update assertions to match current behavior
- Fix imports if needed
- Ensure uses test database

**Step 6**: Move to next file

Repeat for:
1. `test_paper_trader.py`
2. `test_paper_trader_hold.py`
3. `test_dashboard.py`
4. `test_partial_endpoint.py`
5. `test_sell_validation.py`
6. `test_signal_to_trade_flow.py`
7. Any others that fail

### Phase 4: Add Missing Tests (1-2 hours)

Create new test files for gaps in coverage:

#### `tests/test_core_database_integration.py`
```python
"""Verify entire system uses database, not files."""

def test_system_creates_no_json_files():
    """After running bot, no trades.json/holdings.json exist."""

def test_all_trades_in_database():
    """All trades are in database with proper schema."""

def test_all_signals_in_database():
    """All signals are in database with proper schema."""
```

#### `tests/test_data_integrity.py`
```python
"""Verify foreign key relationships."""

def test_trade_links_to_signal():
    """Trade.signal_id references valid Signal.id."""

def test_holding_links_to_trade_and_signal():
    """Holding has entry_trade_id and entry_signal_id."""
```

### Phase 5: Verify Complete Coverage (30 min)

```bash
# Generate coverage report
pytest tests/ --cov=src/app --cov-report=html

# Open in browser
open htmlcov/index.html
```

**Target**: >80% coverage of critical code paths

### Phase 6: Final Verification (15 min)

```bash
# All tests should pass
pytest tests/ -v

# Should show: XXX passed, 0 failed

# Check for remaining issues
grep -r "TRADES_FILE\|NEWS_FILE\|STATUS_FILE" tests/
# Should return nothing
```

---

## Quick Wins (Do These First)

### Win 1: Delete Obsolete Tests in test_paper_trader.py

```bash
# Edit the file
vim tests/test_paper_trader.py

# Delete these entire test methods:
# - test_trades_persisted_to_file
# - test_multiple_trades_appended
# - test_corrupted_file_recovery
# - test_holdings_persisted_to_file

# Save and run
pytest tests/test_paper_trader.py -v
```

### Win 2: Fix Case Sensitivity

```bash
# Find and update
grep -r '== "sell"' tests/ | cut -d: -f1 | sort -u

# In each file, change:
assert trade["action"] == "sell"
# To:
assert trade["action"].upper() == "SELL"
```

### Win 3: Fix HOLD Test Expectations

```bash
vim tests/test_paper_trader_hold.py

# Remove imports expecting TRADES_FILE
# Update tests to use database assertions
```

---

## TDD Workflow for Each Fix

```
1. Read test - understand what it validates
2. Is validation still relevant?
   YES → Update test to match current API
   NO → Delete test
3. Run test - watch it fail (if updating)
4. Fix code (if needed) or test assertion
5. Run test - watch it pass
6. Run full suite - verify no regressions
7. Commit
```

---

## Current Test Count

**Before cleanup**: 528 tests (448 passing, 80 failing)
**After deleting 3 files**: ~500 tests (estimate)
**Target**: ~450-500 tests, all passing

We DON'T need 528 tests if many were testing obsolete functionality.

---

## Files Ready for You

1. `CURRENT_SYSTEM_SPEC.md` - What the system actually does
2. `TEST_FIX_STRATEGY.md` - Analysis of test purposes
3. `TEST_REBUILD_PLAN.md` - This file
4. `tests_backup/` - Backup of all original tests
5. `conftest.py` - Test isolation (working)

---

## Success Criteria

**Done When**:
1. All tests pass: `pytest tests/ -v` shows 0 failures
2. All tests validate CURRENT functionality (database-based)
3. No tests expect JSON files
4. Test coverage >80% on critical paths
5. Tests follow TDD: specific, isolated, fast

---

## Estimated Time

- Phase 1 (Run tests): 5 min
- Phase 2 (Identify): 10 min
- Phase 3 (Fix files): 2-3 hours
- Phase 4 (Add missing): 1-2 hours
- Phase 5 (Coverage): 30 min
- Phase 6 (Verify): 15 min

**Total**: 4-6 hours of focused work

---

## Next Command

```bash
cd /home/rcasteen/kraken-ai-bot
source .venv/bin/activate
export PYTHONPATH=src

# Kill background processes
pkill -9 -f pytest
pkill -9 -f uvicorn

# Run current tests
pytest tests/ -v --tb=short | tee test_results_after_cleanup.txt

# Count results
tail -3 test_results_after_cleanup.txt
```

Then proceed with Phase 2: Identify which remaining tests are good vs need work.
