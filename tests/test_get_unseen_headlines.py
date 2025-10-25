"""
Test for get_unseen_headlines() handling dict feeds.

Run with: pytest tests/test_get_unseen_headlines.py -v
"""
import pytest
from unittest.mock import patch, MagicMock
from app.news_fetcher import get_unseen_headlines


class TestGetUnseenHeadlinesWithDictFeeds:
    """Test get_unseen_headlines works with dict feeds (not string URLs)."""
    
    @patch('app.news_fetcher.get_rss_feeds')
    @patch('app.news_fetcher.feedparser.parse')
    @patch('app.news_fetcher.load_seen')
    def test_handles_dict_feeds(self, mock_load_seen, mock_parse, mock_get_feeds):
        """Test that get_unseen_headlines extracts URL from feed dicts."""
        # Setup: Mock feeds as dicts
        mock_get_feeds.return_value = [
            {"name": "CoinDesk", "url": "https://coindesk.com/feed", "active": True},
            {"name": "CoinTelegraph", "url": "https://cointelegraph.com/rss", "active": True},
        ]
        
        # Mock feedparser to return test headlines
        mock_entry = MagicMock()
        mock_entry.title = "Bitcoin reaches new all-time high"
        
        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]
        mock_parse.return_value = mock_feed
        
        # Mock seen headlines (empty)
        mock_load_seen.return_value = {}
        
        # Execute
        result = get_unseen_headlines()
        
        # Verify: Should have extracted URL from dict and called feedparser.parse
        assert mock_parse.call_count == 2
        mock_parse.assert_any_call("https://coindesk.com/feed")
        mock_parse.assert_any_call("https://cointelegraph.com/rss")
        
        # Should extract BTCUSD from "Bitcoin reaches new all-time high"
        assert "BTCUSD" in result
        assert len(result["BTCUSD"]) == 2  # Same headline from 2 feeds
    
    @patch('app.news_fetcher.get_rss_feeds')
    @patch('app.news_fetcher.feedparser.parse')
    @patch('app.news_fetcher.load_seen')
    def test_filters_seen_headlines(self, mock_load_seen, mock_parse, mock_get_feeds):
        """Test that previously seen headlines are filtered out."""
        mock_get_feeds.return_value = [
            {"name": "TestFeed", "url": "https://test.com/feed", "active": True}
        ]
        
        # Mock headlines
        entry1 = MagicMock()
        entry1.title = "Bitcoin hits $100k"
        entry2 = MagicMock()
        entry2.title = "Ethereum update coming"
        
        mock_feed = MagicMock()
        mock_feed.entries = [entry1, entry2]
        mock_parse.return_value = mock_feed
        
        # Mock seen: Bitcoin headline already seen
        from app.news_fetcher import get_headline_hash
        btc_hash = get_headline_hash("Bitcoin hits $100k")
        mock_load_seen.return_value = {
            "BTCUSD": [btc_hash]
        }
        
        result = get_unseen_headlines()
        
        # Should only return unseen Ethereum headline
        assert "ETHUSD" in result
        assert len(result["ETHUSD"]) == 1
        assert "BTCUSD" not in result  # Already seen
    
    @patch('app.news_fetcher.get_rss_feeds')
    @patch('app.news_fetcher.feedparser.parse')
    @patch('app.news_fetcher.load_seen')
    def test_handles_feed_fetch_errors(self, mock_load_seen, mock_parse, mock_get_feeds):
        """Test that feed fetch errors don't crash the function."""
        mock_get_feeds.return_value = [
            {"name": "GoodFeed", "url": "https://good.com/feed", "active": True},
            {"name": "BadFeed", "url": "https://bad.com/feed", "active": True},
        ]
        
        # First feed works, second throws exception
        good_entry = MagicMock()
        good_entry.title = "Bitcoin news"
        good_feed = MagicMock()
        good_feed.entries = [good_entry]
        
        def parse_side_effect(url):
            if "good.com" in url:
                return good_feed
            else:
                raise Exception("Connection timeout")
        
        mock_parse.side_effect = parse_side_effect
        mock_load_seen.return_value = {}
        
        # Should not crash
        result = get_unseen_headlines()
        
        # Should still have results from good feed
        assert "BTCUSD" in result
        assert len(result["BTCUSD"]) == 1
    
    @patch('app.news_fetcher.get_rss_feeds')
    @patch('app.news_fetcher.feedparser.parse')
    @patch('app.news_fetcher.load_seen')
    def test_skips_headlines_without_symbols(self, mock_load_seen, mock_parse, mock_get_feeds):
        """Test that headlines without crypto symbols are skipped."""
        mock_get_feeds.return_value = [
            {"name": "TestFeed", "url": "https://test.com/feed", "active": True}
        ]
        
        # Headlines: one with symbol, one without
        entry1 = MagicMock()
        entry1.title = "Bitcoin reaches new high"  # Has symbol
        entry2 = MagicMock()
        entry2.title = "Stock market update today"  # No crypto symbol
        
        mock_feed = MagicMock()
        mock_feed.entries = [entry1, entry2]
        mock_parse.return_value = mock_feed
        mock_load_seen.return_value = {}
        
        result = get_unseen_headlines()
        
        # Should only have Bitcoin headline
        assert "BTCUSD" in result
        assert len(result) == 1  # Only one symbol group
    
    @patch('app.news_fetcher.get_rss_feeds')
    @patch('app.news_fetcher.load_seen')
    def test_returns_empty_when_no_feeds(self, mock_load_seen, mock_get_feeds):
        """Test returns empty dict when no feeds configured."""
        mock_get_feeds.return_value = []
        mock_load_seen.return_value = {}
        
        result = get_unseen_headlines()
        
        assert result == {}
    
    @patch('app.news_fetcher.get_rss_feeds')
    @patch('app.news_fetcher.feedparser.parse')
    @patch('app.news_fetcher.load_seen')
    def test_aggregates_headlines_by_symbol(self, mock_load_seen, mock_parse, mock_get_feeds):
        """Test that multiple headlines for same symbol are aggregated."""
        mock_get_feeds.return_value = [
            {"name": "TestFeed", "url": "https://test.com/feed", "active": True}
        ]
        
        # Multiple Bitcoin headlines
        entry1 = MagicMock()
        entry1.title = "Bitcoin hits $100k"
        entry2 = MagicMock()
        entry2.title = "Bitcoin adoption growing"
        entry3 = MagicMock()
        entry3.title = "Ethereum update"
        
        mock_feed = MagicMock()
        mock_feed.entries = [entry1, entry2, entry3]
        mock_parse.return_value = mock_feed
        mock_load_seen.return_value = {}
        
        result = get_unseen_headlines()
        
        # Should aggregate Bitcoin headlines
        assert "BTCUSD" in result
        assert len(result["BTCUSD"]) == 2
        assert "ETHUSD" in result
        assert len(result["ETHUSD"]) == 1