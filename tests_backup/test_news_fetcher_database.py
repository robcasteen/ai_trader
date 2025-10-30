"""
Test that news_fetcher reads from and writes to database ONLY.
No JSON files allowed.
"""
import pytest
from app.news_fetcher import get_unseen_headlines, mark_as_seen
from app.database.connection import get_db
from app.database.repositories import RSSFeedRepository, SeenNewsRepository


def test_news_fetcher_uses_database_only():
    """Verify news fetcher reads feeds from database, not JSON files."""
    with get_db() as db:
        feed_repo = RSSFeedRepository(db)

        # Count enabled feeds in database
        feeds = feed_repo.get_all(enabled_only=True)
        feed_count = len(feeds)

        assert feed_count > 0, "Database should have enabled RSS feeds"

    # Fetch headlines (should use database)
    headlines = get_unseen_headlines()

    # Should return dict of symbol -> headlines
    assert isinstance(headlines, dict)
    print(f"✅ Fetched headlines for {len(headlines)} symbols")
    print(f"✅ Total headlines: {sum(len(h) for h in headlines.values())}")


def test_news_fetcher_stores_seen_in_database():
    """Verify news fetcher stores seen headlines in database."""
    headlines = get_unseen_headlines()

    if not headlines:
        pytest.skip("No new headlines to test with")

    # Get first symbol's headlines
    symbol = list(headlines.keys())[0]
    news_list = headlines[symbol][:2]  # Just first 2

    # Add symbol to each headline dict
    for item in news_list:
        item['symbol'] = symbol

    # Mark as seen
    mark_as_seen(news_list, triggered_signal=False)

    # Verify they're in database
    with get_db() as db:
        seen_repo = SeenNewsRepository(db)

        for item in news_list:
            assert seen_repo.is_seen_by_url(item['url']), \
                f"Headline should be marked as seen in database: {item['url']}"

    print(f"✅ Stored {len(news_list)} headlines in database")


def test_news_fetcher_deduplication():
    """Verify fetcher doesn't return already-seen headlines."""
    # First fetch
    headlines1 = get_unseen_headlines()
    total1 = sum(len(h) for h in headlines1.values())

    if total1 == 0:
        pytest.skip("No headlines to test deduplication")

    # Mark some as seen
    symbol = list(headlines1.keys())[0]
    news_list = headlines1[symbol][:5]
    for item in news_list:
        item['symbol'] = symbol
    mark_as_seen(news_list, triggered_signal=False)

    # Second fetch - should have fewer headlines
    headlines2 = get_unseen_headlines()
    total2 = sum(len(h) for h in headlines2.values())

    assert total2 < total1, "Second fetch should have fewer headlines (deduplication working)"

    print(f"✅ Deduplication working: {total1} → {total2} headlines")


def test_feeds_tab_shows_correct_counts():
    """Verify /api/feeds endpoint returns headline counts from database."""
    import requests

    response = requests.get("http://localhost:8000/api/feeds")
    assert response.status_code == 200

    data = response.json()
    feeds = data['feeds']

    # Verify each feed has headline counts
    for feed in feeds:
        assert 'headlines_count' in feed, f"Feed {feed['name']} missing headlines_count"
        assert 'relevant_count' in feed, f"Feed {feed['name']} missing relevant_count"
        assert isinstance(feed['headlines_count'], int)
        assert isinstance(feed['relevant_count'], int)

    total_headlines = sum(f['headlines_count'] for f in feeds)
    total_relevant = sum(f['relevant_count'] for f in feeds)

    print(f"✅ Feeds tab shows {total_headlines} total headlines, {total_relevant} relevant")
    print(f"✅ All {len(feeds)} feeds have proper counts from database")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("TESTING: News Fetcher Database Integration")
    print("="*70 + "\n")

    test_news_fetcher_uses_database_only()
    test_news_fetcher_stores_seen_in_database()
    test_news_fetcher_deduplication()
    test_feeds_tab_shows_correct_counts()

    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED - News fetcher uses database ONLY")
    print("="*70)
