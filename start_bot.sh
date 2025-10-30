#!/bin/bash
# start_bot.sh - Start the trading bot
# Run with: ./start_bot.sh

cd ~/kraken-ai-bot

# Check if bot is already running
if lsof -i :8000 > /dev/null 2>&1; then
    echo "⚠️  Bot already running on port 8000"
    echo "Stop it first with: pkill -f uvicorn"
    exit 1
fi

echo "🚀 Starting AI Trading Bot..."
echo ""

# Activate virtual environment
source .venv/bin/activate

# Start bot with reload
PYTHONPATH=src python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &

# Wait for startup
sleep 3

# Check if started successfully
if lsof -i :8000 > /dev/null 2>&1; then
    echo "✅ Bot started successfully!"
    echo ""
    echo "📊 Dashboard: http://localhost:8000"
    echo "🛑 To stop: pkill -f uvicorn"
    echo ""
    echo "📋 Check status:"
    echo "  ps aux | grep uvicorn"
    echo "  tail -f src/app/logs/strategy_signals.jsonl"
else
    echo "❌ Failed to start bot"
    echo "Check for errors above"
    exit 1
fi