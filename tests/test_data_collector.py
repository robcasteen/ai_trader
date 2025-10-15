"""Tests for DataCollector."""
import pytest
from unittest.mock import Mock, patch
from app.data_collector import DataCollector

@pytest.fixture
def mock_kraken():
    with patch('app.data_collector.KrakenClient') as mock:
        client = Mock()
        client.get_tickers.return_value = {
            "BTCUSD": {"price": 50000, "volume": 1000},
            "ETHUSD": {"price": 3000, "volume": 500}
        }
        mock.return_value = client
        yield client

def test_collector_initialization():
    collector = DataCollector(max_history=50, poll_interval=1)
    assert collector.max_history == 50
    assert not collector.running

def test_collect_snapshot(mock_kraken):
    collector = DataCollector()
    collector.client = mock_kraken
    collector._collect_snapshot()
    assert len(collector.price_history["BTCUSD"]) == 1
    assert collector.price_history["BTCUSD"][0] == 50000

def test_get_price_history(mock_kraken):
    collector = DataCollector(max_history=10)
    collector.client = mock_kraken
    for i in range(5):
        mock_kraken.get_tickers.return_value = {
            "BTCUSD": {"price": 50000 + i*100, "volume": 1000}
        }
        collector._collect_snapshot()
    history = collector.get_price_history("BTCUSD")
    assert len(history) == 5
    assert history[-1] == 50400
