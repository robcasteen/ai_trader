"""
Unit tests for dashboard module.

Tests cover:
- Route handlers
- Data transformation and aggregation
- PnL calculations
- Summary building
- Sentiment data loading
"""

import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.dashboard import router, build_summary, load_pnl_data, load_sentiment
from fastapi import FastAPI


@pytest.fixture
def test_app():
    """Fixture providing a test FastAPI app with dashboard router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    """Fixture providing a test client."""
    return TestClient(test_app)


@pytest.fixture
def temp_logs_dir(tmp_path, monkeypatch):
    """Fixture providing temporary logs directory."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    
    import app.dashboard as dashboard_module
    monkeypatch.setattr(dashboard_module, 'LOGS_DIR', logs_dir)
    
    return logs_dir


class TestDashboardRoute:
    def test_dashboard_loads(self, client, temp_logs_dir):
        """Test that dashboard page loads successfully."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_dashboard_loads_terminal_ui(self, client, temp_logs_dir):
        """Test that dashboard includes terminal UI elements."""
        response = client.get("/")
        assert b"AI TRADING TERMINAL" in response.content or b"terminal-header" in response.content


class TestPartialRoute:
    def test_partial_returns_json(self, client, temp_logs_dir):
        """Test that /partial returns JSON data."""
        response = client.get("/partial")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_partial_structure(self, client, temp_logs_dir):
        """Test that /partial returns expected data structure."""
        # Create empty trades file
        trades_file = temp_logs_dir / "trades.json"
        trades_file.write_text("[]")
        
        response = client.get("/partial")
        data = response.json()
        
        assert "summary" in data
        assert "labels" in data
        assert "pnl_data" in data
        assert "sentiment" in data
        assert "trades" in data

class TestStatusRoute:
    def test_status_returns_json(self, client, temp_logs_dir):
        """Test that /status returns JSON."""
        response = client.get("/status")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_status_structure(self, client, temp_logs_dir):
        """Test that /status has expected structure."""
        response = client.get("/status")
        data = response.json()
        
        assert "last_status" in data
        assert "next_run" in data

    def test_status_missing_file(self, client, temp_logs_dir):
        """Test /status when bot_status.json doesn't exist."""
        response = client.get("/status")
        data = response.json()
        
        assert "last_status" in data
        assert data["last_status"]["time"] is None


class TestBuildSummary:
    def test_build_summary_empty_trades(self):
        """Test summary with no trades."""
        summary = build_summary([])
        
        assert summary["total_trades"] == 0
        assert summary["buy_count"] == 0
        assert summary["sell_count"] == 0
        assert summary["hold_count"] == 0
        assert summary["symbols"] == {}

    def test_build_summary_buy_and_sell(self):
        """Test summary counts buy and sell correctly."""
        trades = [
            {"action": "buy", "symbol": "BTC/USD", "price": 50000, "amount": 0.1},
            {"action": "sell", "symbol": "BTC/USD", "price": 52000, "amount": 0.1},
        ]
        
        summary = build_summary(trades)
        
        assert summary["total_trades"] == 2
        assert summary["buy_count"] == 1
        assert summary["sell_count"] == 1

    def test_build_summary_hold_not_counted_in_trades(self):
        """Test that HOLD signals don't count as trades."""
        trades = [
            {"action": "buy", "symbol": "BTC/USD", "price": 50000, "amount": 0.1},
            {"action": "hold", "symbol": "ETH/USD", "price": 3000, "amount": 0},
            {"action": "sell", "symbol": "BTC/USD", "price": 52000, "amount": 0.1},
        ]
        
        summary = build_summary(trades)
        
        assert summary["total_trades"] == 2  # Only buy and sell
        assert summary["hold_count"] == 1

    def test_build_summary_per_symbol_data(self):
        """Test per-symbol data in summary."""
        trades = [
            {
                "timestamp": "2025-01-01T10:00:00",
                "action": "buy",
                "symbol": "BTC/USD",
                "price": 50000,
                "amount": 0.1,
                "reason": "Good news"
            },
        ]
        
        summary = build_summary(trades)
        
        assert "BTC/USD" in summary["symbols"]
        assert summary["symbols"]["BTC/USD"]["last_action"] == "buy"
        assert summary["symbols"]["BTC/USD"]["last_price"] == 50000
        assert summary["symbols"]["BTC/USD"]["last_amount"] == 0.1
        assert summary["symbols"]["BTC/USD"]["last_reason"] == "Good news"

    def test_build_summary_case_insensitive_action(self):
        """Test that action matching is case-insensitive."""
        trades = [
            {"action": "BUY", "symbol": "BTC/USD", "price": 50000, "amount": 0.1},
            {"action": "SELL", "symbol": "BTC/USD", "price": 52000, "amount": 0.1},
            {"action": "HOLD", "symbol": "ETH/USD", "price": 3000, "amount": 0},
        ]
        
        summary = build_summary(trades)
        
        assert summary["buy_count"] == 1
        assert summary["sell_count"] == 1
        assert summary["hold_count"] == 1


