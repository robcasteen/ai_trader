#!/usr/bin/env bash
set -e  # exit on first error

# where to create the venv
VENV_DIR=".venv"

echo "🔧 Setting up virtual environment at $VENV_DIR..."

# remove old venv if it exists
if [ -d "$VENV_DIR" ]; then
    echo "Removing old virtual environment..."
    rm -rf "$VENV_DIR"
fi

# create fresh venv
python3 -m venv "$VENV_DIR"

# activate venv
source "$VENV_DIR/bin/activate"

# upgrade pip/wheel/setuptools
echo "Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

# install project dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing project requirements..."
    pip install -r requirements.txt
else
    echo "⚠️ No requirements.txt found, skipping..."
fi

# install dev tools
echo "Installing dev tools (pytest)..."
pip install pytest

echo "✅ Environment setup complete!"
echo "To activate later, run: source $VENV_DIR/bin/activate"
