"""
Tests for error_tracker.py

Run with: pytest tests/test_error_tracker.py -v
"""
import pytest
import json
from datetime import datetime, timezone
from pathlib import Path
from app.error_tracker import ErrorTracker


@pytest.fixture
def temp_log_file(tmp_path):
    """Create a temporary log file for testing."""
    return tmp_path / "test_errors.json"


@pytest.fixture
def error_tracker(temp_log_file):
    """Create an ErrorTracker instance for testing."""
    return ErrorTracker(max_errors=10, log_file=temp_log_file)


class TestErrorTrackerBasics:
    """Test basic error tracker functionality."""
    
    def test_initialization(self, temp_log_file):
        """Test error tracker initializes correctly."""
        tracker = ErrorTracker(max_errors=50, log_file=temp_log_file)
        assert tracker.max_errors == 50
        assert tracker.log_file == temp_log_file
        assert len(tracker.errors) == 0
        assert len(tracker.error_counts) == 0
    
    def test_log_error_basic(self, error_tracker):
        """Test logging a basic error."""
        error_tracker.log_error(
            component="openai",
            message="API key invalid"
        )
        
        assert len(error_tracker.errors) == 1
        error = error_tracker.errors[0]
        
        assert error["component"] == "openai"
        assert error["message"] == "API key invalid"
        assert error["severity"] == "error"
        assert "timestamp" in error
        assert "metadata" in error
    
    def test_log_error_with_exception(self, error_tracker):
        """Test logging an error with exception."""
        try:
            raise ValueError("Invalid value")
        except Exception as e:
            error_tracker.log_error(
                component="exchange",
                message="Validation failed",
                error=e,
                severity="critical"
            )
        
        error = error_tracker.errors[0]
        assert error["component"] == "exchange"
        assert error["severity"] == "critical"
        assert "exception" in error
        assert "Invalid value" in error["exception"]
        assert error["exception_type"] == "ValueError"
        assert "stack_trace" in error
    
    def test_log_error_with_metadata(self, error_tracker):
        """Test logging error with metadata."""
        error_tracker.log_error(
            component="rss",
            message="Feed fetch failed",
            metadata={"url": "https://example.com/feed", "status_code": 404}
        )
        
        error = error_tracker.errors[0]
        assert error["metadata"]["url"] == "https://example.com/feed"
        assert error["metadata"]["status_code"] == 404


class TestErrorRetrieval:
    """Test error retrieval and filtering."""
    
    def test_get_errors_all(self, error_tracker):
        """Test getting all errors."""
        error_tracker.log_error("openai", "Error 1")
        error_tracker.log_error("exchange", "Error 2")
        error_tracker.log_error("rss", "Error 3")
        
        errors = error_tracker.get_errors()
        assert len(errors) == 3
        
        # Should be newest first
        assert errors[0]["message"] == "Error 3"
        assert errors[1]["message"] == "Error 2"
        assert errors[2]["message"] == "Error 1"
    
    def test_get_errors_by_component(self, error_tracker):
        """Test filtering errors by component."""
        error_tracker.log_error("openai", "OpenAI error 1")
        error_tracker.log_error("exchange", "Exchange error")
        error_tracker.log_error("openai", "OpenAI error 2")
        
        openai_errors = error_tracker.get_errors(component="openai")
        assert len(openai_errors) == 2
        assert all(e["component"] == "openai" for e in openai_errors)
    
    def test_get_errors_by_severity(self, error_tracker):
        """Test filtering errors by severity."""
        error_tracker.log_error("openai", "Minor issue", severity="warning")
        error_tracker.log_error("exchange", "Major issue", severity="error")
        error_tracker.log_error("rss", "Critical issue", severity="critical")
        
        critical_errors = error_tracker.get_errors(severity="critical")
        assert len(critical_errors) == 1
        assert critical_errors[0]["severity"] == "critical"
    
    def test_get_errors_with_limit(self, error_tracker):
        """Test limiting number of returned errors."""
        for i in range(10):
            error_tracker.log_error("test", f"Error {i}")
        
        errors = error_tracker.get_errors(limit=5)
        assert len(errors) == 5
    
    def test_get_component_errors(self, error_tracker):
        """Test getting errors for specific component."""
        error_tracker.log_error("openai", "Error 1")
        error_tracker.log_error("openai", "Error 2")
        error_tracker.log_error("exchange", "Error 3")
        
        openai_errors = error_tracker.get_component_errors("openai")
        assert len(openai_errors) == 2
        assert all(e["component"] == "openai" for e in openai_errors)
    
    def test_get_error_count(self, error_tracker):
        """Test getting error count for component."""
        error_tracker.log_error("openai", "Error 1")
        error_tracker.log_error("openai", "Error 2")
        error_tracker.log_error("exchange", "Error 3")
        
        assert error_tracker.get_error_count("openai") == 2
        assert error_tracker.get_error_count("exchange") == 1
        assert error_tracker.get_error_count("nonexistent") == 0
    
    def test_get_last_error(self, error_tracker):
        """Test getting last error for component."""
        error_tracker.log_error("openai", "Error 1")
        error_tracker.log_error("openai", "Error 2")
        
        last_error = error_tracker.get_last_error("openai")
        assert last_error is not None
        assert last_error["message"] == "Error 2"
    
    def test_get_last_error_none(self, error_tracker):
        """Test getting last error when none exist."""
        last_error = error_tracker.get_last_error("nonexistent")
        assert last_error is None


class TestErrorClearing:
    """Test error clearing functionality."""
    
    def test_clear_all_errors(self, error_tracker):
        """Test clearing all errors."""
        error_tracker.log_error("openai", "Error 1")
        error_tracker.log_error("exchange", "Error 2")
        error_tracker.log_error("rss", "Error 3")
        
        cleared = error_tracker.clear_errors()
        
        assert cleared == 3
        assert len(error_tracker.errors) == 0
        assert len(error_tracker.error_counts) == 0
    
    def test_clear_component_errors(self, error_tracker):
        """Test clearing errors for specific component."""
        error_tracker.log_error("openai", "Error 1")
        error_tracker.log_error("openai", "Error 2")
        error_tracker.log_error("exchange", "Error 3")
        
        cleared = error_tracker.clear_errors(component="openai")
        
        assert cleared == 2
        assert len(error_tracker.errors) == 1
        assert error_tracker.errors[0]["component"] == "exchange"
        assert error_tracker.get_error_count("openai") == 0
        assert error_tracker.get_error_count("exchange") == 1
    
    def test_clear_nonexistent_component(self, error_tracker):
        """Test clearing errors for component with no errors."""
        error_tracker.log_error("openai", "Error 1")
        
        cleared = error_tracker.clear_errors(component="nonexistent")
        
        assert cleared == 0
        assert len(error_tracker.errors) == 1


class TestErrorPersistence:
    """Test error persistence to disk."""
    
    def test_save_to_disk(self, error_tracker, temp_log_file):
        """Test saving errors to disk."""
        error_tracker.log_error("openai", "Error 1")
        error_tracker.log_error("exchange", "Error 2")
        
        # Errors should be saved automatically
        assert temp_log_file.exists()
        
        with open(temp_log_file) as f:
            data = json.load(f)
        
        assert "errors" in data
        assert "error_counts" in data
        assert len(data["errors"]) == 2
    
    def test_load_from_disk(self, temp_log_file):
        """Test loading errors from disk."""
        # Create and save errors
        tracker1 = ErrorTracker(max_errors=10, log_file=temp_log_file)
        tracker1.log_error("openai", "Error 1")
        tracker1.log_error("exchange", "Error 2")
        
        # Create new tracker that should load existing errors
        tracker2 = ErrorTracker(max_errors=10, log_file=temp_log_file)
        
        assert len(tracker2.errors) == 2
        assert tracker2.get_error_count("openai") == 1
        assert tracker2.get_error_count("exchange") == 1
    
    def test_no_persistence_without_log_file(self):
        """Test error tracker works without persistence."""
        tracker = ErrorTracker(max_errors=10, log_file=None)
        tracker.log_error("openai", "Error 1")
        
        assert len(tracker.errors) == 1
        # Should not crash without log file


class TestErrorBounds:
    """Test error bounds and limits."""
    
    def test_max_errors_limit(self, error_tracker):
        """Test that max_errors limit is enforced."""
        # Tracker has max_errors=10
        for i in range(15):
            error_tracker.log_error("test", f"Error {i}")
        
        # Should only keep last 10
        assert len(error_tracker.errors) == 10
        
        # Should have newest errors
        errors = list(error_tracker.errors)
        assert errors[-1]["message"] == "Error 14"
        assert errors[0]["message"] == "Error 5"
    
    def test_empty_tracker(self, error_tracker):
        """Test operations on empty tracker."""
        assert len(error_tracker.get_errors()) == 0
        assert error_tracker.get_last_error("openai") is None
        assert error_tracker.get_error_count("openai") == 0
        assert error_tracker.clear_errors() == 0


class TestHealthSummary:
    """Test health summary generation."""
    
    def test_get_health_summary(self, error_tracker):
        """Test getting health summary."""
        error_tracker.log_error("openai", "Error 1")
        error_tracker.log_error("openai", "Error 2")
        error_tracker.log_error("exchange", "Error 3")
        
        summary = error_tracker.get_health_summary()
        
        assert "openai" in summary
        assert "exchange" in summary
        
        assert summary["openai"]["error_count"] == 2
        assert summary["openai"]["status"] == "error"
        assert summary["openai"]["last_error"] is not None
        
        assert summary["exchange"]["error_count"] == 1
        assert summary["exchange"]["status"] == "error"
    
    def test_get_health_summary_empty(self, error_tracker):
        """Test health summary with no errors."""
        summary = error_tracker.get_health_summary()
        assert summary == {}


class TestErrorMetadata:
    """Test error metadata handling."""
    
    def test_error_has_timestamp(self, error_tracker):
        """Test that errors have valid timestamps."""
        error_tracker.log_error("test", "Error")
        
        error = error_tracker.errors[0]
        timestamp = datetime.fromisoformat(error["timestamp"])
        
        # Should be recent (within last 5 seconds)
        now = datetime.now(timezone.utc)
        diff = (now - timestamp).total_seconds()
        assert diff < 5
    
    def test_error_has_component(self, error_tracker):
        """Test that all errors have component."""
        error_tracker.log_error("openai", "Error")
        
        error = error_tracker.errors[0]
        assert "component" in error
        assert error["component"] == "openai"
    
    def test_error_has_message(self, error_tracker):
        """Test that all errors have message."""
        error_tracker.log_error("test", "Test message")
        
        error = error_tracker.errors[0]
        assert "message" in error
        assert error["message"] == "Test message"
    
    def test_error_has_severity(self, error_tracker):
        """Test that all errors have severity."""
        error_tracker.log_error("test", "Error", severity="warning")
        
        error = error_tracker.errors[0]
        assert "severity" in error
        assert error["severity"] == "warning"
    
    def test_error_default_severity(self, error_tracker):
        """Test default severity is 'error'."""
        error_tracker.log_error("test", "Error")
        
        error = error_tracker.errors[0]
        assert error["severity"] == "error"


class TestConcurrency:
    """Test error tracker under concurrent conditions."""
    
    def test_multiple_components_simultaneously(self, error_tracker):
        """Test logging errors from multiple components."""
        components = ["openai", "exchange", "rss", "database"]
        
        for component in components:
            for i in range(3):
                error_tracker.log_error(component, f"{component} error {i}")
        
        # Should have all errors
        assert len(error_tracker.errors) == 10  # max_errors=10
        
        # Should track counts for all components
        for component in components[:3]:  # First 3 should have all their errors
            assert error_tracker.get_error_count(component) == 3