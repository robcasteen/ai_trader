import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app, save_status_to_file, STATUS_FILE, run_trade_cycle

client = TestClient(app)


def test_save_status_to_file_writes_json(tmp_path):
    status_file = tmp_path / "bot_status.json"

    # Patch STATUS_FILE to point into tmp dir
    with patch("app.main.STATUS_FILE", status_file):
        status = {"time": "2025-01-01 00:00:00", "message": "ok", "next_run": "soon"}
        save_status_to_file(status)

        # File exists and contains correct JSON
        data = json.loads(status_file.read_text())
        assert data == status


def test_status_endpoint_reads_file(tmp_path):
    """Test that /status endpoint reads from bot_status.json."""
    status_file = tmp_path / "bot_status.json"
    test_status = {
        "time": "2025-01-01 12:00:00",
        "message": "Completed successfully", 
        "next_run": "2025-01-01 12:05:00"
    }
    status_file.write_text(json.dumps(test_status))

    with patch("app.main.STATUS_FILE", status_file):
        # Also need to ensure dashboard uses the same file
        with patch("app.dashboard.LOGS_DIR", tmp_path):
            resp = client.get("/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["last_status"]["time"] == "2025-01-01 12:00:00"
            assert "next_run" in data

@patch("app.main.get_top_symbols", return_value=["BTC/USD"])
@patch("app.main.get_unseen_headlines", return_value={"BTCUSD": ["Breaking news!"]})
@patch("app.main.signal_model")
@patch("app.main.trader")
@patch("app.main.notifier")
@patch("app.main.kraken")
def test_run_trade_cycle_saves_status(mock_kraken, mock_notifier, mock_trader, mock_signal, *_):
    # Mock responses
    mock_kraken.get_price.return_value = 50000.0
    mock_kraken.get_balance.return_value = 1000.0
    mock_signal.get_signal.return_value = ("BUY", "Positive news")
    mock_trader.execute_trade.return_value = {"trade": "executed"}
    mock_notifier.send.return_value = None

    run_trade_cycle()

    # After run, STATUS_FILE should exist
    assert STATUS_FILE.exists()
    data = json.loads(STATUS_FILE.read_text())
    assert "time" in data
    assert "message" in data
    assert "next_run" in data
    assert isinstance(data["message"], str)


def test_run_now_endpoint_triggers_cycle():
    resp = client.get("/run-now")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "last_status" in data
    assert "next_run" in data


