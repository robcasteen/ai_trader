"""
Tests for get_rss_feeds() function - FIXED VERSION.

Run with: pytest tests/test_news_fetcher_feeds.py -v
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestGetRssFeeds:
    """Test RSS feed loading from rss_feeds.json."""
    
    @patch('app.news_fetcher.Path')
    def test_load_feeds_from_json(self, mock_path_class, tmp_path):
        """Test loading feeds from rss_feeds.json file."""
        # Setup: Create test feeds file
        feeds_data = [
            {"id": 1, "name": "CoinDesk", "url": "https://coindesk.com/feed", "active": True},
            {"id": 2, "name": "CoinTelegraph", "url": "https://cointelegraph.com/rss", "active": True},
            {"id": 3, "name": "Inactive Feed", "url": "https://inactive.com/feed", "active": False}
        ]
        
        feeds_file = tmp_path / "rss_feeds.json"
        feeds_file.write_text(json.dumps(feeds_data))
        
        # Mock Path(__file__).parent to return tmp_path
        mock_path_instance = MagicMock()
        mock_path_instance.parent = tmp_path
        mock_path_class.return_value = mock_path_instance
        
        from app.news_fetcher import get_rss_feeds
        
        feeds = get_rss_feeds()
        
        # Should only return active feeds
        assert len(feeds) == 2
        assert all(feed["active"] == True for feed in feeds)
        assert feeds[0]["name"] == "CoinDesk"
        assert feeds[1]["name"] == "CoinTelegraph"
    
    @patch('app.news_fetcher.Path')
    def test_filters_inactive_feeds(self, mock_path_class, tmp_path):
        """Test that inactive feeds are filtered out."""
        feeds_data = [
            {"id": 1, "name": "Active", "url": "https://active.com", "active": True},
            {"id": 2, "name": "Inactive", "url": "https://inactive.com", "active": False},
            {"id": 3, "name": "Null", "url": "https://null.com", "active": None},
        ]
        
        feeds_file = tmp_path / "rss_feeds.json"
        feeds_file.write_text(json.dumps(feeds_data))
        
        mock_path_instance = MagicMock()
        mock_path_instance.parent = tmp_path
        mock_path_class.return_value = mock_path_instance
        
        from app.news_fetcher import get_rss_feeds
        
        feeds = get_rss_feeds()
        
        assert len(feeds) == 1
        assert feeds[0]["name"] == "Active"
    
    @patch('app.news_fetcher.Path')
    def test_returns_empty_list_when_no_active_feeds(self, mock_path_class, tmp_path):
        """Test returns empty list when all feeds are inactive."""
        feeds_data = [
            {"id": 1, "name": "Inactive1", "url": "https://1.com", "active": False},
            {"id": 2, "name": "Inactive2", "url": "https://2.com", "active": False},
        ]
        
        feeds_file = tmp_path / "rss_feeds.json"
        feeds_file.write_text(json.dumps(feeds_data))
        
        mock_path_instance = MagicMock()
        mock_path_instance.parent = tmp_path
        mock_path_class.return_value = mock_path_instance
        
        from app.news_fetcher import get_rss_feeds
        
        feeds = get_rss_feeds()
        
        assert len(feeds) == 0
    
    @patch('app.news_fetcher.Path')
    def test_fallback_when_file_not_found(self, mock_path_class, tmp_path):
        """Test fallback to hardcoded feeds when file doesn't exist."""
        # Point to non-existent file
        mock_path_instance = MagicMock()
        mock_path_instance.parent = tmp_path / "nonexistent"
        mock_path_class.return_value = mock_path_instance
        
        from app.news_fetcher import get_rss_feeds
        
        feeds = get_rss_feeds()
        
        # Should return fallback feeds
        assert len(feeds) >= 3
        assert all(feed["active"] == True for feed in feeds)
        assert any("coindesk" in feed["url"].lower() for feed in feeds)
    
    @patch('app.news_fetcher.Path')
    def test_fallback_when_json_corrupted(self, mock_path_class, tmp_path):
        """Test fallback when JSON file is corrupted."""
        feeds_file = tmp_path / "rss_feeds.json"
        feeds_file.write_text("{ invalid json }")
        
        mock_path_instance = MagicMock()
        mock_path_instance.parent = tmp_path
        mock_path_class.return_value = mock_path_instance
        
        from app.news_fetcher import get_rss_feeds
        
        feeds = get_rss_feeds()
        
        # Should return fallback feeds
        assert len(feeds) >= 3
        assert all(feed["active"] == True for feed in feeds)
    
    @patch('app.news_fetcher.Path')
    def test_handles_missing_active_field(self, mock_path_class, tmp_path):
        """Test handles feeds without 'active' field."""
        feeds_data = [
            {"id": 1, "name": "NoActiveField", "url": "https://test.com"},
            {"id": 2, "name": "WithActive", "url": "https://test2.com", "active": True},
        ]
        
        feeds_file = tmp_path / "rss_feeds.json"
        feeds_file.write_text(json.dumps(feeds_data))
        
        mock_path_instance = MagicMock()
        mock_path_instance.parent = tmp_path
        mock_path_class.return_value = mock_path_instance
        
        from app.news_fetcher import get_rss_feeds
        
        feeds = get_rss_feeds()
        
        # Should only return feeds with active: True explicitly
        assert len(feeds) == 1
        assert feeds[0]["name"] == "WithActive"
    
    @patch('app.news_fetcher.Path')
    def test_preserves_feed_metadata(self, mock_path_class, tmp_path):
        """Test that all feed metadata is preserved."""
        feeds_data = [
            {
                "id": 1,
                "name": "CoinDesk",
                "url": "https://coindesk.com/feed",
                "active": True,
                "description": "Crypto news",
                "last_fetch": "2025-10-15T01:10:08Z",
                "headlines_count": 25,
                "relevant_count": 5
            }
        ]
        
        feeds_file = tmp_path / "rss_feeds.json"
        feeds_file.write_text(json.dumps(feeds_data))
        
        mock_path_instance = MagicMock()
        mock_path_instance.parent = tmp_path
        mock_path_class.return_value = mock_path_instance
        
        from app.news_fetcher import get_rss_feeds
        
        feeds = get_rss_feeds()
        
        assert len(feeds) == 1
        feed = feeds[0]
        assert feed["name"] == "CoinDesk"
        assert feed["url"] == "https://coindesk.com/feed"
        assert feed["description"] == "Crypto news"
        assert feed["headlines_count"] == 25
        assert feed["relevant_count"] == 5


class TestProductionFeedLoading:
    """Test with actual production data."""
    
    def test_loads_actual_feeds(self):
        """Test loading from actual rss_feeds.json file."""
        from app.news_fetcher import get_rss_feeds
        
        feeds = get_rss_feeds()
        
        # Should load actual feeds
        assert len(feeds) >= 1  # At least one active feed
        assert all(isinstance(feed, dict) for feed in feeds)
        assert all("url" in feed for feed in feeds)
        assert all(feed.get("active") == True for feed in feeds)