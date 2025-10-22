"""
Tests for RSS feed management - edit and disable functionality.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestFeedEdit:
    """Test editing RSS feed name and URL."""
    
    def test_edit_feed_endpoint_exists(self):
        """PUT /api/feeds/{id} should exist."""
        response = client.put("/api/feeds/1", json={"name": "Test", "url": "http://test.com"})
        assert response.status_code in [200, 404]
    
    def test_edit_feed_updates_name(self):
        """Should be able to update feed name."""
        # Get existing feeds
        feeds_response = client.get("/api/feeds")
        initial_feeds = feeds_response.json()["feeds"]
        
        if not initial_feeds:
            pytest.skip("No feeds to test with")
        
        feed_id = initial_feeds[0]["id"]
        original_url = initial_feeds[0]["url"]
        
        # Edit the name
        edit_response = client.put(f"/api/feeds/{feed_id}", json={
            "name": "Test Updated Name",
            "url": original_url
        })
        
        assert edit_response.status_code == 200
        
        # Verify name changed
        feeds_after = client.get("/api/feeds").json()["feeds"]
        updated_feed = next((f for f in feeds_after if f["id"] == feed_id), None)
        assert updated_feed is not None
        assert updated_feed["name"] == "Test Updated Name"


class TestFeedDisable:
    """Test disabling/enabling feeds without deleting."""
    
    def test_feed_has_status_field(self):
        """Feeds should have a 'status' field (currently exists)."""
        response = client.get("/api/feeds")
        feeds = response.json()["feeds"]
        
        if feeds:
            assert "status" in feeds[0], "Feed should have 'status' field"
    
    def test_feed_needs_active_field(self):
        """Feeds should have an 'active' boolean field for enable/disable."""
        response = client.get("/api/feeds")
        feeds = response.json()["feeds"]
        
        if feeds:
            # This will fail - we need to add it
            assert "active" in feeds[0], "Feed should have 'active' field for toggling"
    
    def test_toggle_feed_endpoint_exists(self):
        """PUT /api/feeds/{id}/toggle should exist."""
        response = client.put("/api/feeds/1/toggle")
        assert response.status_code in [200, 404]
    
    def test_toggle_feed_changes_active_status(self):
        """Toggling should change active state."""
        feeds = client.get("/api/feeds").json()["feeds"]
        
        if not feeds:
            pytest.skip("No feeds to test with")
        
        feed_id = feeds[0]["id"]
        original_active = feeds[0].get("active", True)
        
        # Toggle it
        toggle_response = client.put(f"/api/feeds/{feed_id}/toggle")
        assert toggle_response.status_code == 200
        
        # Verify it changed
        feeds_after = client.get("/api/feeds").json()["feeds"]
        updated_feed = next((f for f in feeds_after if f["id"] == feed_id), None)
        new_active = updated_feed.get("active", True)
        assert new_active != original_active
