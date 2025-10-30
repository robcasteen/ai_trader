#!/usr/bin/env bash
set -e

VENV_DIR=".venv"

# ensure venv exists
if [ ! -d "$VENV_DIR" ]; then
  echo "⚠️ Virtual environment not found. Run ./setup_env.sh first."
  exit 1
fi

# activate venv
source "$VENV_DIR/bin/activate"

# set PYTHONPATH for app code
export PYTHONPATH="$(pwd)/src"
echo "PYTHONPATH is set to: $PYTHONPATH"

# mode selection
if [ "$1" = "test" ]; then
    echo "🧪 Running test suite..."
    echo ""
    echo "🐍 Running Python tests..."
    pytest -v
    PYTHON_EXIT=$?
    
    echo ""
    echo "📊 Running JavaScript tests..."
    npm test
    JS_EXIT=$?
    
    echo ""
    if [ $PYTHON_EXIT -ne 0 ] || [ $JS_EXIT -ne 0 ]; then
        echo "❌ Tests failed"
        exit 1
    fi
    
    echo "✅ All tests passed!"
elif [ "$1" = "dev" ]; then
    echo "🚀 Starting FastAPI app in dev mode..."
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
else
    echo "🚀 Starting FastAPI app..."
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi