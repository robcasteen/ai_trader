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

    def test_dashboard_contains_chart_script(self, client, temp_logs_dir):
        """Test that dashboard includes Chart.js."""
        response = client.get("/")
        
        assert b"Chart" in response.content or b"chart.js" in response.content


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

    def test_partial_with_trades(self, client, temp_logs_dir):
        """Test /partial with actual trade data."""
        trades = [
            {
                "timestamp": "2025-01-01T10:00:00",
                "action": "buy",
                "symbol": "BTC/USD",
                "price": 50000,
                "amount": 0.1,
                "value": 5000,
                "reason": "Test buy"
            },
            {
                "timestamp": "2025-01-01T11:00:00",
                "action": "sell",
                "symbol": "BTC/USD",
                "price": 52000,
                "amount": 0.1,
                "value": 5200,
                "reason": "Test sell"
            }
        ]
        
        trades_file = temp_logs_dir / "trades.json"
        trades_file.write_text(json.dumps(trades))
        
        response = client.get("/partial")
        data = response.json()
        
        assert data["summary"]["total_trades"] == 2
        assert data["summary"]["buy_count"] == 1
        assert data["summary"]["sell_count"] == 1
        assert len(data["trades"]) == 2


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

    def test_status_with_bot_status_file(self, client, temp_logs_dir):
        """Test /status reads from bot_status.json."""
        status_data = {
            "time": "2025-01-01 12:00:00",
            "message": "Completed successfully",
            "next_run": "2025-01-01 12:05:00"
        }
        
        status_file = temp_logs_dir / "bot_status.json"
        status_file.write_text(json.dumps(status_data))
        
        response = client.get("/status")
        data = response.json()
        
        assert data["last_status"]["time"] == "2025-01-01 12:00:00"
        assert data["last_status"]["message"] == "Completed successfully"
        assert data["next_run"] == "2025-01-01 12:05:00"

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


class TestLoadPnLData:
    def test_load_pnl_empty_trades(self, temp_logs_dir):
        """Test PnL calculation with no trades."""
        trades_file = temp_logs_dir / "trades.json"
        trades_file.write_text("[]")
        
        labels, pnl_data = load_pnl_data()
        
        assert labels == []
        assert pnl_data == []

    def test_load_pnl_simple_profit(self, temp_logs_dir):
        """Test PnL calculation for simple profitable trade."""
        trades = [
            {"action": "buy", "symbol": "BTC/USD", "price": 50000, "amount": 1},
            {"action": "sell", "symbol": "BTC/USD", "price": 52000, "amount": 1},
        ]
        
        trades_file = temp_logs_dir / "trades.json"
        trades_file.write_text(json.dumps(trades))
        
        labels, pnl_data = load_pnl_data()
        
        assert "BTC/USD" in labels
        idx = labels.index("BTC/USD")
        assert pnl_data[idx] == 2000.0  # Profit of $2000

    def test_load_pnl_simple_loss(self, temp_logs_dir):
        """Test PnL calculation for losing trade."""
        trades = [
            {"action": "buy", "symbol": "BTC/USD", "price": 50000, "amount": 1},
            {"action": "sell", "symbol": "BTC/USD", "price": 48000, "amount": 1},
        ]
        
        trades_file = temp_logs_dir / "trades.json"
        trades_file.write_text(json.dumps(trades))
        
        labels, pnl_data = load_pnl_data()
        
        idx = labels.index("BTC/USD")
        assert pnl_data[idx] == -2000.0  # Loss of $2000

    def test_load_pnl_multiple_symbols(self, temp_logs_dir):
        """Test PnL calculation with multiple symbols."""
        trades = [
            {"action": "buy", "symbol": "BTC/USD", "price": 50000, "amount": 1},
            {"action": "sell", "symbol": "BTC/USD", "price": 52000, "amount": 1},
            {"action": "buy", "symbol": "ETH/USD", "price": 3000, "amount": 1},
            {"action": "sell", "symbol": "ETH/USD", "price": 3200, "amount": 1},
        ]
        
        trades_file = temp_logs_dir / "trades.json"
        trades_file.write_text(json.dumps(trades))
        
        labels, pnl_data = load_pnl_data()
        
        assert len(labels) == 2
        assert "BTC/USD" in labels
        assert "ETH/USD" in labels


class TestLoadSentiment:
    def test_load_sentiment_empty_file(self, temp_logs_dir):
        """Test loading sentiment with no file."""
        sentiment = load_sentiment()
        
        assert sentiment == {}

    def test_load_sentiment_with_data(self, temp_logs_dir):
        """Test loading sentiment data."""
        sentiment_data = {
            "BTC/USD": {
                "signal": "buy",
                "reason": "Positive news",
                "updated_at": "2025-01-01T10:00:00"
            },
            "ETH/USD": {
                "signal": "sell",
                "reason": "Negative sentiment",
                "timestamp": "2025-01-01T11:00:00"
            }
        }
        
        sentiment_file = temp_logs_dir / "sentiment.json"
        sentiment_file.write_text(json.dumps(sentiment_data))
        
        sentiment = load_sentiment()
        
        assert "BTC/USD" in sentiment
        assert sentiment["BTC/USD"]["signal"] == "BUY"  # Uppercased
        assert sentiment["BTC/USD"]["reason"] == "Positive news"

    def test_load_sentiment_normalizes_signals(self, temp_logs_dir):
        """Test that signals are uppercased."""
        sentiment_data = {
            "BTC/USD": {"signal": "buy", "reason": "Test"},
            "ETH/USD": {"signal": "sell", "reason": "Test"},
            "SOL/USD": {"signal": "hold", "reason": "Test"},
        }
        
        sentiment_file = temp_logs_dir / "sentiment.json"
        sentiment_file.write_text(json.dumps(sentiment_data))
        
        sentiment = load_sentiment()
        
        assert sentiment["BTC/USD"]["signal"] == "BUY"
        assert sentiment["ETH/USD"]["signal"] == "SELL"
        assert sentiment["SOL/USD"]["signal"] == "HOLD"

    def test_load_sentiment_empty_signal_defaults_to_hold(self, temp_logs_dir):
        """Test that empty/missing signal defaults to HOLD."""
        sentiment_data = {
            "BTC/USD": {"signal": "", "reason": "Test"},
            "ETH/USD": {"reason": "Test"},  # No signal field
        }
        
        sentiment_file = temp_logs_dir / "sentiment.json"
        sentiment_file.write_text(json.dumps(sentiment_data))
        
        sentiment = load_sentiment()
        
        assert sentiment["BTC/USD"]["signal"] == "HOLD"
        assert sentiment["ETH/USD"]["signal"] == "HOLD"

    def test_load_sentiment_corrupted_file(self, temp_logs_dir):
        """Test loading corrupted sentiment file."""
        sentiment_file = temp_logs_dir / "sentiment.json"
        sentiment_file.write_text("{ invalid json }")
        
        sentiment = load_sentiment()
        
        assert sentiment == {}

    def test_load_sentiment_handles_timestamp_variants(self, temp_logs_dir):
        """Test that both 'updated_at' and 'timestamp' are handled."""
        sentiment_data = {
            "BTC/USD": {
                "signal": "buy",
                "updated_at": "2025-01-01T10:00:00"
            },
            "ETH/USD": {
                "signal": "sell",
                "timestamp": "2025-01-01T11:00:00"
            }
        }
        
        sentiment_file = temp_logs_dir / "sentiment.json"
        sentiment_file.write_text(json.dumps(sentiment_data))
        
        sentiment = load_sentiment()
        
        assert sentiment["BTC/USD"]["updated_at"] == "2025-01-01T10:00:00"
        assert sentiment["ETH/USD"]["updated_at"] == "2025-01-01T11:00:00"


class TestPartialDataIntegration:
    def test_partial_filters_holds_from_recent_trades(self, client, temp_logs_dir):
        """Test that /partial only returns real trades (buy/sell) in recent trades."""
        trades = [
            {"action": "buy", "symbol": "BTC/USD", "price": 50000, "amount": 0.1},
            {"action": "hold", "symbol": "ETH/USD", "price": 3000, "amount": 0},
            {"action": "sell", "symbol": "BTC/USD", "price": 52000, "amount": 0.1},
        ]
        
        trades_file = temp_logs_dir / "trades.json"
        trades_file.write_text(json.dumps(trades))
        
        response = client.get("/partial")
        data = response.json()
        
        # Recent trades should only include buy and sell
        assert len(data["trades"]) == 2
        assert all(t["action"] in ("buy", "sell") for t in data["trades"])

    def test_partial_limits_recent_trades_to_20(self, client, temp_logs_dir):
        """Test that /partial returns max 20 recent trades."""
        trades = [
            {"action": "buy", "symbol": f"SYM{i}", "price": 100, "amount": 1}
            for i in range(30)
        ]
        
        trades_file = temp_logs_dir / "trades.json"
        trades_file.write_text(json.dumps(trades))
        
        response = client.get("/partial")
        data = response.json()
        
        assert len(data["trades"]) == 20

    def test_partial_fallback_sentiment_for_unknown_symbols(self, client, temp_logs_dir):
        """Test that /partial creates fallback sentiment for symbols without sentiment data."""
        trades = [
            {"action": "buy", "symbol": "BTC/USD", "price": 50000, "amount": 0.1},
        ]
        
        trades_file = temp_logs_dir / "trades.json"
        trades_file.write_text(json.dumps(trades))
        
        response = client.get("/partial")
        data = response.json()
        
        # Should have fallback sentiment for BTC/USD
        assert "BTC/USD" in data["sentiment"]
        assert data["sentiment"]["BTC/USD"]["signal"] == "HOLD"
        assert "No headlines" in data["sentiment"]["BTC/USD"]["reason"]