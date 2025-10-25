# Database Layer - SQLite + SQLAlchemy

**Easy Setup | Resilient | Performative**

---

## Overview

The bot now uses **SQLite** with **SQLAlchemy ORM** for all data storage. This provides:

✅ **Zero setup** - No external database server required
✅ **ACID compliance** - Transaction safety and crash recovery
✅ **Test isolation** - Clean separation of test and production data
✅ **Fast queries** - Indexed lookups in milliseconds
✅ **Easy migration** - Can switch to PostgreSQL/MySQL later with zero code changes

---

## Database Location

```
data/trading_bot.db
```

This single file contains all your trading data.

---

## Quick Start

### 1. Install Dependencies (already done)

```bash
pip install sqlalchemy alembic
```

### 2. Initialize Database

The database initializes automatically on first import. To manually initialize:

```bash
python -c "from app.database.connection import init_db; init_db()"
```

### 3. Migrate Existing Data

```bash
python scripts/migrate_to_sqlite.py
```

This imports data from JSON files and properly tags test data.

---

## Schema

### Collections (Tables)

1. **signals** - All trading signals with strategy breakdown
2. **trades** - Executed trades with attribution
3. **holdings** - Current positions
4. **strategy_performance** - Aggregated metrics
5. **strategy_definitions** - Dynamic strategy configs
6. **error_logs** - Structured error tracking
7. **rss_feeds** - News feed configurations
8. **seen_news** - News deduplication
9. **bot_status** - Runtime state

### Key Features

**Test Mode Isolation:**
```python
# Query only production data
prod_trades = session.query(Trade).filter(Trade.test_mode == False).all()

# Query only test data
test_trades = session.query(Trade).filter(Trade.test_mode == True).all()
```

**Signal → Trade Attribution:**
```python
# Get all trades from a specific signal
signal = session.query(Signal).first()
trades = signal.trades  # Relationship automatically loaded
```

**Data Provenance:**
- Every record has `bot_version`
- Signals have `strategy_version` hash
- Full audit trail

---

## Usage Examples

### Get Database Session

```python
from app.database.connection import get_db

# Context manager (recommended)
with get_db() as db:
    signals = db.query(Signal).filter(Signal.test_mode == False).all()

# FastAPI dependency injection
from fastapi import Depends
from app.database.connection import get_db_session

@app.get("/signals")
def get_signals(db: Session = Depends(get_db_session)):
    return db.query(Signal).limit(10).all()
```

### Insert Signal

```python
from app.database.models import Signal
from app.database.connection import get_db
from datetime import datetime
from decimal import Decimal

with get_db() as db:
    signal = Signal(
        timestamp=datetime.utcnow(),
        symbol="BTCUSD",
        price=Decimal("50000.00"),
        final_signal="BUY",
        final_confidence=Decimal("0.85"),
        aggregation_method="weighted_average",
        strategies={
            "sentiment": {"signal": "BUY", "confidence": 0.9},
            "technical": {"signal": "BUY", "confidence": 0.8"}
        },
        test_mode=False,
        bot_version="1.0.0"
    )
    db.add(signal)
    db.commit()
```

### Query with Filters

```python
from app.database.models import Trade
from datetime import datetime, timedelta

# Last 24 hours of production trades
yesterday = datetime.utcnow() - timedelta(days=1)
recent_trades = (
    db.query(Trade)
    .filter(Trade.test_mode == False)
    .filter(Trade.timestamp >= yesterday)
    .order_by(Trade.timestamp.desc())
    .all()
)

# Trades for specific symbol
btc_trades = (
    db.query(Trade)
    .filter(Trade.symbol == "BTCUSD")
    .filter(Trade.test_mode == False)
    .all()
)
```

### Join Signals and Trades

```python
from app.database.models import Signal, Trade

# Get signals with their trades
results = (
    db.query(Signal, Trade)
    .outerjoin(Trade, Signal.id == Trade.signal_id)
    .filter(Signal.test_mode == False)
    .all()
)

for signal, trade in results:
    print(f"Signal: {signal.final_signal}, Trade: {trade.action if trade else 'Not executed'}")
```

---

## Database Management

### Health Check

```python
from app.database.connection import health_check

status = health_check()
print(status)
# {'status': 'healthy', 'database': 'data/trading_bot.db', 'size_bytes': 4096, ...}
```

### Get Table Counts

```python
from app.database.connection import get_table_counts

counts = get_table_counts()
print(f"Total signals: {counts['signals']}")
print(f"Production trades: {counts['prod_trades']}")
print(f"Test trades: {counts['test_trades']}")
```

### Backup Database

```bash
# Simple file copy
cp data/trading_bot.db backups/trading_bot_$(date +%Y%m%d).db

# Or use SQLite backup command
sqlite3 data/trading_bot.db ".backup backups/trading_bot_$(date +%Y%m%d).db"
```

### Inspect Database

```bash
# Open SQLite shell
sqlite3 data/trading_bot.db

# List tables
.tables

# Show schema
.schema signals

# Query data
SELECT * FROM signals WHERE test_mode = 0 LIMIT 10;

# Exit
.quit
```

---

## Performance

### Optimizations Enabled

- **WAL Mode** - Write-Ahead Logging for better concurrency
- **64MB Cache** - In-memory caching
- **Indexes** - All queries are indexed
- **Foreign Keys** - Enforced relationships
- **Synchronous=NORMAL** - Fast yet safe writes

### Expected Performance

- **Inserts**: 10,000+ per second
- **Queries**: < 1ms for indexed lookups
- **Database Size**: ~4KB + (signals × 1KB) + (trades × 500 bytes)

Example: 10,000 signals + 1,000 trades = ~10MB database

---

## Migration Path

### To PostgreSQL (when you scale)

Just change the connection string:

```python
# SQLite (current)
DATABASE_URL = "sqlite:///data/trading_bot.db"

# PostgreSQL (future)
DATABASE_URL = "postgresql://user:pass@localhost/kraken_bot"
```

**Zero code changes required!** SQLAlchemy handles everything.

---

## Troubleshooting

### Database Locked Error

**Cause**: Another process is writing to the database.

**Solution**: Use context managers (`with get_db()`) to ensure connections are closed.

### Duplicate Index Error

**Cause**: Re-running migrations without dropping tables first.

**Solution**:
```python
from app.database.connection import drop_all_tables, init_db

drop_all_tables()  # Careful! This deletes all data
init_db()
```

### Migration Failed

**Cause**: Data validation errors in JSON files.

**Solution**: Check the migration script output for specific errors. The script will skip bad records and continue.

---

## Test vs Production Data

### How Test Data is Tagged

**Test Trades:**
- `amount == 0`
- `amount > 1000` (unrealistically large)
- `price > 200000` (e.g., BTC > $200k)

**Test Signals:**
- Symbols starting with "TEST"
- Unrealistic prices

All test data has `test_mode = True`.

### Querying Only Production Data

```python
# Always filter by test_mode
prod_signals = db.query(Signal).filter(Signal.test_mode == False).all()
prod_trades = db.query(Trade).filter(Trade.test_mode == False).all()
```

---

## Files Created

```
src/app/database/
├── __init__.py
├── models.py          # SQLAlchemy ORM models
└── connection.py      # Database connection management

scripts/
└── migrate_to_sqlite.py   # Migration script

data/
└── trading_bot.db     # SQLite database file (gitignored)
```

---

## Next Steps

1. ✅ Database created and migrated
2. ⏳ Update application code to use database instead of JSON files
3. ⏳ Add repository pattern for cleaner data access
4. ⏳ Create API endpoints using database
5. ⏳ Add comprehensive tests

---

## Support

For issues or questions, check:
- [DATA_FORENSICS_REPORT.md](DATA_FORENSICS_REPORT.md) - Understanding data issues
- [MONGODB_MIGRATION_PLAN.md](MONGODB_MIGRATION_PLAN.md) - Alternative database options
- SQLAlchemy docs: https://docs.sqlalchemy.org/
