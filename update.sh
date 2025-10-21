# Find ALL related processes
ps aux | grep -E "uvicorn|python.*main.py|BackgroundScheduler" | grep -v grep

# Kill EVERYTHING
pkill -9 -f uvicorn
pkill -9 -f "python.*main"
pkill -9 -f BackgroundScheduler

# Verify nothing on port 8000
lsof -i :8000

# If still something there, kill by port
lsof -ti :8000 | xargs kill -9

# Verify it's dead
ps aux | grep uvicorn | grep -v grep
lsof -i :8000