#!/bin/bash

# Purge All Historic Data - Fresh Start Script
# This will delete ALL trading data and start from scratch

echo "=========================================="
echo "PURGING ALL HISTORIC DATA"
echo "=========================================="
echo ""

# Stop any running servers
echo "1. Stopping all servers..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 2
echo "   ✓ Servers stopped"
echo ""

# Backup directory
BACKUP_DIR="backups/purge_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup existing data
echo "2. Backing up existing data to $BACKUP_DIR..."
cp -r data/*.jsonl "$BACKUP_DIR/" 2>/dev/null
cp -r data/*.json "$BACKUP_DIR/" 2>/dev/null
cp -r data/*.db* "$BACKUP_DIR/" 2>/dev/null
cp -r src/app/logs/*.jsonl "$BACKUP_DIR/" 2>/dev/null
cp -r src/app/logs/*.json "$BACKUP_DIR/" 2>/dev/null
echo "   ✓ Backup complete"
echo ""

# Delete database
echo "3. Deleting database..."
rm -f data/trading_bot.db
rm -f data/trading_bot.db-shm
rm -f data/trading_bot.db-wal
echo "   ✓ Database deleted"
echo ""

# Delete JSON/JSONL files
echo "4. Deleting all JSON/JSONL data files..."
rm -f data/strategy_signals.jsonl
rm -f data/trades.json
rm -f data/holdings.json
rm -f data/bot_status.json
rm -f data/rss_feeds.json
rm -f data/errors.json
rm -f src/app/logs/strategy_signals.jsonl
rm -f src/app/logs/trades.json
rm -f src/app/logs/holdings.json
rm -f src/app/logs/bot_status.json
rm -f src/app/logs/rss_feeds.json
rm -f src/app/logs/errors.json
echo "   ✓ All data files deleted"
echo ""

# Initialize fresh database
echo "5. Initializing fresh database..."
source .venv/bin/activate
PYTHONPATH=src python -c "
from app.database.connection import init_db, get_db_health
print('   Creating new database...')
init_db()
health = get_db_health()
print(f'   ✓ Database created: {health[\"path\"]}')
print(f'   ✓ Size: {health[\"size_bytes\"]} bytes')
"
echo ""

# Create empty JSON files
echo "6. Creating fresh JSON files..."
echo "[]" > data/trades.json
echo "[]" > data/holdings.json
echo "{}" > data/bot_status.json
echo "[]" > data/rss_feeds.json
echo "[]" > data/errors.json
echo "   ✓ Fresh JSON files created"
echo ""

echo "=========================================="
echo "PURGE COMPLETE - FRESH START READY!"
echo "=========================================="
echo ""
echo "Backup saved to: $BACKUP_DIR"
echo ""
echo "To start the server, run:"
echo "  source .venv/bin/activate"
echo "  PYTHONPATH=src python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
