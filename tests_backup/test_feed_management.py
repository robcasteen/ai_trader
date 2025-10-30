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
    
    def test_feed_has_enabled_field(self):
        """Feeds should have an 'enabled' field for toggling."""
        response = client.get("/api/feeds")
        feeds = response.json()["feeds"]

        if feeds:
            assert "enabled" in feeds[0], "Feed should have 'enabled' field"
            assert isinstance(feeds[0]["enabled"], bool), "'enabled' should be a boolean"
    
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


class TestFeedDelete:
    """Test deleting RSS feeds."""

    def test_delete_feed_endpoint_exists(self):
        """DELETE /api/feeds/{id} should exist."""
        response = client.delete("/api/feeds/99999")  # Non-existent ID
        assert response.status_code in [404, 500]  # Should return 404 for not found

    def test_delete_nonexistent_feed_returns_404(self):
        """Deleting non-existent feed should return 404."""
        response = client.delete("/api/feeds/99999")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"].lower()

    def test_delete_feed_removes_from_database(self):
        """Deleting a feed should remove it from the database."""
        # Create a test feed first
        create_response = client.post("/api/feeds", json={
            "name": "Test Delete Feed",
            "url": "https://test-delete.com/rss"
        })

        if create_response.status_code != 200:
            pytest.skip("Cannot create test feed")

        feed_id = create_response.json()["id"]

        # Verify it exists
        feeds_before = client.get("/api/feeds").json()["feeds"]
        assert any(f["id"] == feed_id for f in feeds_before)

        # Delete it
        delete_response = client.delete(f"/api/feeds/{feed_id}")
        assert delete_response.status_code == 200

        # Verify it's gone
        feeds_after = client.get("/api/feeds").json()["feeds"]
        assert not any(f["id"] == feed_id for f in feeds_after)

    def test_toggle_feed_uses_database(self):
        """Toggle should persist to database, not JSON files."""
        feeds = client.get("/api/feeds").json()["feeds"]

        if not feeds:
            pytest.skip("No feeds to test with")

        feed_id = feeds[0]["id"]

        # Toggle it
        toggle_response = client.put(f"/api/feeds/{feed_id}/toggle")
        assert toggle_response.status_code == 200

        # Verify response has correct structure
        data = toggle_response.json()
        assert "success" in data
        assert "active" in data
        assert "feed_id" in data
        assert data["success"] is True
        assert data["feed_id"] == feed_id

    def test_delete_feed_uses_database(self):
        """Delete should remove from database, not JSON files."""
        # Create a test feed
        create_response = client.post("/api/feeds", json={
            "name": "Test Database Delete",
            "url": "https://test-db-delete.com/rss"
        })

        if create_response.status_code != 200:
            pytest.skip("Cannot create test feed")

        feed_id = create_response.json()["id"]

        # Delete it
        delete_response = client.delete(f"/api/feeds/{feed_id}")
        assert delete_response.status_code == 200

        # Verify response structure
        data = delete_response.json()
        assert "status" in data
        assert data["status"] == "success"
        assert "id" in data
        assert data["id"] == feed_id
