"""Tests for news_fetcher with proper mocking."""

import pytest
import json
from unittest.mock import patch, Mock
from app import news_fetcher


@pytest.fixture
def temp_news_file(tmp_path, monkeypatch):
    news_file = tmp_path / "seen_news.json"
    monkeypatch.setattr(news_fetcher, 'NEWS_FILE', news_file)
    return news_file


def test_extract_btc_symbol():
    assert news_fetcher.extract_symbol_from_headline("BTC surges") == "BTCUSD"
    assert news_fetcher.extract_symbol_from_headline("Bitcoin reaches ATH") == "BTCUSD"


def test_extract_eth_symbol():
    assert news_fetcher.extract_symbol_from_headline("Ethereum update") == "ETHUSD"


def test_extract_no_symbol():
    assert news_fetcher.extract_symbol_from_headline("Generic crypto news") is None


def test_hash_consistency():
    h1 = news_fetcher.get_headline_hash("Bitcoin surges")
    h2 = news_fetcher.get_headline_hash("Bitcoin surges")
    assert h1 == h2


def test_save_and_load_seen(temp_news_file):
    seen_data = {"BTCUSD": ["hash1", "hash2"]}
    news_fetcher.save_seen(seen_data)
    
    loaded = news_fetcher.load_seen()
    assert loaded == seen_data


def test_mark_as_seen_limits_to_50(temp_news_file):
    headlines = [f"Headline {i}" for i in range(60)]
    news_fetcher.mark_as_seen("BTCUSD", headlines)
    
    seen = news_fetcher.load_seen()
    assert len(seen["BTCUSD"]) == 50


@patch('app.news_fetcher.feedparser.parse')
def test_get_unseen_headlines(mock_parse, temp_news_file):
    """Test fetching unseen headlines."""
    mock_entry = Mock()
    mock_entry.title = "Bitcoin surges to new high"
    
    mock_feed = Mock()
    mock_feed.entries = [mock_entry]
    mock_parse.return_value = mock_feed
    
    unseen = news_fetcher.get_unseen_headlines()
    
    assert "BTCUSD" in unseen
    assert len(unseen["BTCUSD"]) >= 1
