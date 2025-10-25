# Data Forensics Report
**Date:** 2025-10-25
**Purpose:** Comprehensive analysis of data integrity issues before MongoDB migration

---

## Executive Summary

### Critical Findings:
1. **THREE different signal file locations** causing data fragmentation
2. **Write/Read mismatch** - Code writes to one location, reads from another
3. **9% test/invalid trades** contaminating trade history
4. **14-day legacy data** mixed with recent production data
5. **No test mode isolation** - test and production data in same files

### Impact:
- ❌ **Performance analysis unreliable** - Reading wrong signal file
- ❌ **Cannot validate strategies** - Zombie data from previous iterations
- ❌ **No data provenance** - Can't distinguish test from real signals
- ❌ **Metrics contaminated** - Test trades skewing win rates

---

## Data File Inventory

### Signal Files (CRITICAL ISSUE)

| Location | Size | Entries | Modified | Status |
|----------|------|---------|----------|--------|
| `src/app/logs/strategy_signals.jsonl` | 1.8 MB | 2,562 | 2025-10-25 13:07 | **ACTIVE (WRITE)** |
| `data/strategy_signals.jsonl` | 176 KB | 326 | 2025-10-24 20:12 | **LEGACY (READ)** |
| `tests/test_logs/strategy_signals.jsonl` | 50 KB | 68 | 2025-10-24 16:27 | **TEST DATA** |

**Problem:**
- `strategy_manager.py` **WRITES** to `src/app/logs/strategy_signals.jsonl` (2,562 signals)
- `signal_performance.py` **READS** from `data/strategy_signals.jsonl` (326 OLD signals)
- **Dashboard shows signals from wrong file!**

### Trade Files

| File | Entries | Date Range | Test Data % |
|------|---------|------------|-------------|
| `src/app/logs/trades.json` | 210 | Oct 24-25 (21 hours) | 9% (19 invalid) |

**Issues:**
- 19 trades with amount=0 or amount>1000 (test trades)
- No separation between test and production

### Other Data Files

| File | Entries | Issues |
|------|---------|--------|
| `src/app/logs/holdings.json` | 10 positions | ✓ Clean |
| `src/app/logs/errors.json` | 2 | ✓ Clean |
| `src/app/logs/bot_status.json` | 3 fields | ✓ Clean |
| `src/app/logs/rss_feeds.json` | 18 feeds | ✓ Clean |
| `src/app/logs/seen_news.json` | 11 | ⚠️ Duplicate exists |
| `src/logs/seen_news.json` | 12 | ⚠️ Duplicate location |
| `src/app/logs/seen_headlines.json` | 12 | ✓ Clean |

---

## Data Flow Analysis

### Signal Generation Flow (BROKEN)

```
1. Trade Cycle Executes
   └─> paper_trader.py calls strategy_manager.generate_signal()
       └─> strategy_manager.py instantiates StrategySignalLogger(logs_dir)
           └─> WRITES to: src/app/logs/strategy_signals.jsonl ✓
```

### Signal Reading Flow (BROKEN)

```
1. Performance Dashboard
   └─> signal_performance.py reads signals
       └─> READS from: data/strategy_signals.jsonl ✗ (WRONG FILE!)
```

**Result:** Dashboard shows 326 OLD signals (oldest from Oct 10), not the 2,562 RECENT signals (from Oct 24-25)

---

## Timeline Analysis

### Signal Data Timeline

**ACTIVE FILE** (`src/app/logs/strategy_signals.jsonl`):
- **2,562 signals** from Oct 24-25 (21 hours)
- **Clean recent data** from current bot iteration
- Breakdown:
  - Oct 24: 290 signals
  - Oct 25: 2,272 signals

**LEGACY FILE** (`data/strategy_signals.jsonl`):
- **326 signals** spanning Oct 10-25 (14 days)
- **Zombie data** from previous test iterations
- Includes test signals with BTCUSD at $111k (clearly test data)
- Breakdown:
  - Oct 10-23: 305 signals (OLD iterations)
  - Oct 24-25: 21 signals (overlaps with active, but different trades)

### Trade Data Timeline

**TRADES** (`src/app/logs/trades.json`):
- 210 trades over 21 hours (Oct 24-25)
- 191 valid trades (91%)
- 19 test/invalid trades (9%)
  - Zero amount trades
  - Unusually large amounts

**Contamination:** Test trades skew metrics and can't be reliably filtered

---

## Code Path Discrepancies

### Writing Signals

**File:** `strategy_manager.py:56`
```python
self.signal_logger = StrategySignalLogger(data_dir=logs_dir)
# logs_dir = "src/app/logs"
# WRITES TO: src/app/logs/strategy_signals.jsonl
```

### Reading Signals

**File:** `signal_performance.py:22`
```python
signals_file = Path(__file__).parent.parent.parent / "data" / "strategy_signals.jsonl"
# READS FROM: data/strategy_signals.jsonl
```

**File:** `dashboard.py` (Recent Signals panel)
```python
("strategy_signals.jsonl", LOGS_DIR / "strategy_signals.jsonl")
# READS FROM: src/app/logs/strategy_signals.jsonl (CORRECT)
```

**Inconsistency:**
- Recent Signals panel reads from ACTIVE file ✓
- Performance Analysis reads from LEGACY file ✗

---

## Data Quality Issues

### 1. Test Data Contamination
- **9% of trades** are test data (amount=0 or unrealistic)
- No field to mark `test_mode=true`
- Can't reliably filter out test data

### 2. Zombie Historical Data
- 14-day-old signals in `data/` folder
- Previous bot iterations mixed with current
- No version tracking or reset mechanism

### 3. Duplicate File Locations
- **Signals:** 3 locations
- **Seen news:** 2 locations
- Different components reading different files

### 4. No Data Provenance
- Can't determine:
  - Which bot version generated the data
  - Test mode vs production mode
  - Manual tests vs automated cycles

---

## Root Cause Analysis

### Why This Happened:

1. **Path inconsistency** - Some code uses relative paths, some uses absolute
2. **No central data registry** - Each module defines its own file paths
3. **No migration scripts** - Old data never cleaned up after code changes
4. **File-based storage limitations** - Can't query, can't enforce schema
5. **No test isolation** - Test mode writes to same files as production

### Why It Matters Now:

You're at an inflection point where:
- Strategy validation requires clean historical data
- Performance attribution needs accurate signal→trade correlation
- Going live requires regulatory-grade audit trails
- Adding new strategies requires backtest capability

**File-based storage cannot support these requirements.**

---

## Recommended Actions

### Immediate (Pre-Migration Cleanup):

1. **Archive all current data**
   ```bash
   mkdir -p backups/pre_mongodb_$(date +%Y%m%d_%H%M%S)
   cp -r src/app/logs/* backups/pre_mongodb_*/
   cp -r data/* backups/pre_mongodb_*/
   ```

2. **Delete zombie data**
   ```bash
   rm data/strategy_signals.jsonl  # Old legacy file
   rm src/logs/seen_news.json      # Duplicate
   ```

3. **Clean test trades** from trades.json
   - Filter out amount=0 or amount>1000
   - Keep only valid trades from Oct 24-25

4. **Fix code paths** (or wait for MongoDB migration)
   - Option A: Fix `signal_performance.py` to read from `src/app/logs`
   - Option B: Wait for MongoDB (better)

### MongoDB Migration (Recommended):

See separate migration plan document.

---

## Current Data State Summary

| Data Type | Current State | Action Needed |
|-----------|---------------|---------------|
| **Signals** | 3 locations, read/write mismatch | Consolidate to MongoDB |
| **Trades** | 9% test data contamination | Clean + migrate |
| **Holdings** | Clean | Migrate as-is |
| **Errors** | Clean but limited | Migrate + expand schema |
| **RSS Feeds** | Clean | Migrate as-is |
| **News** | Duplicate locations | Consolidate to MongoDB |

---

## Next Steps

**Choose your path:**

**Option A: Quick Fix (1-2 hours)**
- Fix `signal_performance.py` path
- Clean test trades
- Delete legacy files
- Continue with file-based storage

**Option B: MongoDB Migration (Recommended, 4-8 hours)**
- Archive all data
- Set up MongoDB
- Design schema with test_mode, versioning, provenance
- Migrate clean data only
- Deprecate file-based storage

**Option C: Nuclear Reset (30 minutes)**
- Delete all data files
- Start fresh with MongoDB
- Begin collecting clean data from scratch

---

## Files Requiring Code Changes

If staying with files (not recommended):

1. **src/app/signal_performance.py:22** - Fix path to `src/app/logs`
2. **src/app/strategy_signal_logger.py** - Add test_mode field
3. **src/app/logic/paper_trader.py** - Add test_mode flag to all operations
4. **All data operations** - Add schema validation

If migrating to MongoDB:
- All of the above + see MongoDB migration plan

---

**Decision Point:** Ready to proceed with MongoDB migration?
