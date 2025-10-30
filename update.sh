#!/bin/bash
# reset_bot_200.sh - Reset bot to fresh state with $200 starting balance
# Run with: ./reset_bot_200.sh

set -e  # Exit on error

cd ~/kraken-ai-bot

echo "🛑 Stopping bot..."
pkill -f uvicorn || echo "Bot not running"
sleep 2

echo ""
echo "💾 Backing up current state..."
BACKUP_DIR="backups/reset_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup all logs
cp src/app/logs/trades.json "$BACKUP_DIR/" 2>/dev/null || echo "No trades.json to backup"
cp src/app/logs/holdings.json "$BACKUP_DIR/" 2>/dev/null || echo "No holdings.json to backup"
cp src/app/logs/strategy_signals.jsonl "$BACKUP_DIR/" 2>/dev/null || echo "No signals to backup"
cp src/app/logs/bot_status.json "$BACKUP_DIR/" 2>/dev/null || echo "No status to backup"

echo "✅ Backed up to $BACKUP_DIR"

echo ""
echo "🗑️  Clearing state files..."

# Reset trades (empty array)
echo "[]" > src/app/logs/trades.json

# Reset holdings (empty object)
echo "{}" > src/app/logs/holdings.json

# Clear strategy signals (keep file, empty it)
> src/app/logs/strategy_signals.jsonl

# Reset bot status
cat > src/app/logs/bot_status.json << 'EOF'
{
  "last_run": null,
  "next_run": null,
  "status": "Ready to start",
  "message": "Reset with $200 starting balance"
}
EOF

# Keep RSS feeds as-is (they're working)
# Keep seen headlines (prevents re-processing old news)

echo "✅ State files cleared"

echo ""
echo "💰 Setting balance to $200..."

# Update config.py to set PAPER_TRADING_BALANCE = 200
CONFIG_FILE="src/app/config.py"

if grep -q "PAPER_TRADING_BALANCE" "$CONFIG_FILE"; then
    # Replace existing value
    sed -i 's/PAPER_TRADING_BALANCE = [0-9]*/PAPER_TRADING_BALANCE = 200/' "$CONFIG_FILE"
    echo "✅ Updated PAPER_TRADING_BALANCE to 200"
else
    echo "⚠️  PAPER_TRADING_BALANCE not found in config.py - add it manually"
fi

echo ""
echo "🧹 Clearing Python cache..."
find src -name "*.pyc" -delete
find src -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo ""
echo "✅ Reset complete!"
echo ""
echo "📊 Current state:"
echo "  - Balance: $200"
echo "  - Trades: 0"
echo "  - Holdings: 0 positions"
echo "  - Signals: cleared"
echo ""
echo "🚀 To start bot:"
echo "  source .venv/bin/activate"
echo "  PYTHONPATH=src python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "Or run: ./start_bot.sh"
echo ""
echo "📁 Backup saved to: $BACKUP_DIR"