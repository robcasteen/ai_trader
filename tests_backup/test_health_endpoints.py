"""
Tests for enhanced health endpoints.

Run with: pytest tests/test_health_endpoints.py -v
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

# You'll need to adjust these imports based on your app structure
# from app.main import app
# from app.error_tracker import error_tracker


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    # This assumes your main FastAPI app is in app.main
    # Adjust import as needed
    from app.main import app
    return TestClient(app)


@pytest.fixture
def mock_error_tracker():
    """Mock error tracker for testing."""
    with patch('app.dashboard.error_tracker') as mock:
        mock.get_errors.return_value = []
        mock.clear_errors.return_value = 0
        mock.get_component_errors.return_value = []
        mock.get_error_count.return_value = 0
        mock.get_last_error.return_value = None
        yield mock


@pytest.fixture
def sample_errors():
    """Sample error data for testing."""
    return [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": "openai",
            "message": "API key invalid",
            "severity": "error",
            "exception": "AuthenticationError",
            "exception_type": "AuthenticationError",
            "metadata": {}
        },
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": "exchange",
            "message": "Rate limit exceeded",
            "severity": "warning",
            "exception": "RateLimitError",
            "exception_type": "RateLimitError",
            "metadata": {"retry_after": 30}
        }
    ]


class TestGetErrors:
    """Test GET /api/errors endpoint."""
    
    def test_get_errors_empty(self, client, mock_error_tracker):
        """Test getting errors when none exist."""
        mock_error_tracker.get_errors.return_value = []
        
        response = client.get("/api/errors")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "errors" in data
        assert "total" in data
        assert data["total"] == 0
        assert len(data["errors"]) == 0
    
    def test_get_errors_with_data(self, client, mock_error_tracker, sample_errors):
        """Test getting errors when data exists."""
        mock_error_tracker.get_errors.return_value = sample_errors
        
        response = client.get("/api/errors")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 2
        assert len(data["errors"]) == 2
        assert data["errors"][0]["component"] == "openai"
        assert data["errors"][1]["component"] == "exchange"
    
    def test_get_errors_filter_by_component(self, client, mock_error_tracker, sample_errors):
        """Test filtering errors by component."""
        openai_errors = [e for e in sample_errors if e["component"] == "openai"]
        mock_error_tracker.get_errors.return_value = openai_errors
        
        response = client.get("/api/errors?component=openai")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["component"] == "openai"
        assert data["total"] == 1
        assert all(e["component"] == "openai" for e in data["errors"])
    
    def test_get_errors_with_limit(self, client, mock_error_tracker, sample_errors):
        """Test limiting number of returned errors."""
        mock_error_tracker.get_errors.return_value = sample_errors[:1]
        
        response = client.get("/api/errors?limit=1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["errors"]) == 1
        mock_error_tracker.get_errors.assert_called_once()
        call_args = mock_error_tracker.get_errors.call_args
        assert call_args[1]["limit"] == 1


class TestClearErrors:
    """Test POST /api/errors/clear endpoint."""
    
    def test_clear_all_errors(self, client, mock_error_tracker):
        """Test clearing all errors."""
        mock_error_tracker.clear_errors.return_value = 5
        
        response = client.post("/api/errors/clear")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["cleared"] == 5
        assert data["component"] == "all"
    
    def test_clear_component_errors(self, client, mock_error_tracker):
        """Test clearing errors for specific component."""
        mock_error_tracker.clear_errors.return_value = 3
        
        response = client.post("/api/errors/clear?component=openai")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["cleared"] == 3
        assert data["component"] == "openai"
        mock_error_tracker.clear_errors.assert_called_once_with(component="openai")


class TestTestOpenAI:
    """Test POST /api/test/openai endpoint."""
    
    @patch('app.dashboard.check_openai_health')
    def test_openai_test_success(self, mock_check, client, mock_error_tracker):
        """Test successful OpenAI connection test."""
        mock_check.return_value = {
            "status": "operational",
            "message": "Connection successful",
            "latency": 150
        }
        
        response = client.post("/api/test/openai")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["status"] == "operational"
        assert "timestamp" in data
        assert data["latency"] == 150
    
    @patch('app.dashboard.check_openai_health')
    def test_openai_test_failure(self, mock_check, client, mock_error_tracker):
        """Test failed OpenAI connection test."""
        mock_check.return_value = {
            "status": "error",
            "message": "Authentication failed"
        }
        
        response = client.post("/api/test/openai")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is False
        assert data["status"] == "error"
        mock_error_tracker.log_error.assert_called_once()
    
    @patch('app.dashboard.check_openai_health')
    def test_openai_test_exception(self, mock_check, client, mock_error_tracker):
        """Test OpenAI test when exception occurs."""
        mock_check.side_effect = Exception("Network error")
        
        response = client.post("/api/test/openai")
        
        assert response.status_code == 500
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        mock_error_tracker.log_error.assert_called_once()


class TestTestKraken:
    """Test POST /api/test/kraken endpoint."""
    
    @patch('app.dashboard.check_exchange_health')
    def test_kraken_test_success(self, mock_check, client, mock_error_tracker):
        """Test successful Kraken connection test."""
        mock_check.return_value = {
            "status": "operational",
            "message": "Connection successful",
            "latency": 200
        }
        
        response = client.post("/api/test/kraken")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["status"] == "operational"
        assert data["latency"] == 200
    
    @patch('app.dashboard.check_exchange_health')
    def test_kraken_test_degraded(self, mock_check, client, mock_error_tracker):
        """Test Kraken test when service is degraded."""
        mock_check.return_value = {
            "status": "degraded",
            "message": "High latency detected",
            "latency": 5000
        }
        
        response = client.post("/api/test/kraken")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is False
        assert data["status"] == "degraded"
        mock_error_tracker.log_error.assert_called_once()


class TestTestRSS:
    """Test POST /api/test/rss endpoint."""
    
    @patch('app.dashboard.check_rss_feeds_health')
    def test_rss_test_success(self, mock_check, client, mock_error_tracker):
        """Test successful RSS feeds test."""
        mock_check.return_value = {
            "status": "operational",
            "message": "All feeds accessible"
        }
        
        response = client.post("/api/test/rss")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["status"] == "operational"
    
    @patch('app.dashboard.check_rss_feeds_health')
    def test_rss_test_failure(self, mock_check, client, mock_error_tracker):
        """Test RSS test when feeds are down."""
        mock_check.return_value = {
            "status": "error",
            "message": "Multiple feeds unreachable"
        }
        
        response = client.post("/api/test/rss")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is False
        mock_error_tracker.log_error.assert_called_once()


class TestDetailedHealth:
    """Test GET /api/health/detailed endpoint."""
    
    @patch('app.dashboard.check_database_health')
    @patch('app.dashboard.check_rss_feeds_health')
    @patch('app.dashboard.check_exchange_health')
    @patch('app.dashboard.check_openai_health')
    def test_detailed_health_all_operational(
        self, 
        mock_openai,
        mock_exchange,
        mock_rss,
        mock_db,
        client,
        mock_error_tracker
    ):
        """Test detailed health when all services operational."""
        # Mock all health checks as operational
        mock_openai.return_value = {"status": "operational", "latency": 100}
        mock_exchange.return_value = {"status": "operational", "latency": 150}
        mock_rss.return_value = {"status": "operational", "latency": 200}
        mock_db.return_value = {"status": "operational", "latency": 50}
        
        # Mock error tracker responses
        mock_error_tracker.get_error_count.return_value = 0
        mock_error_tracker.get_last_error.return_value = None
        mock_error_tracker.get_component_errors.return_value = []
        
        response = client.get("/api/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have all services
        assert "openai" in data
        assert "exchange" in data
        assert "rssFeeds" in data
        assert "database" in data
        
        # All should be operational
        assert data["openai"]["status"] == "operational"
        assert data["exchange"]["status"] == "operational"
        assert data["rssFeeds"]["status"] == "operational"
        assert data["database"]["status"] == "operational"
        
        # Should have error counts
        assert data["openai"]["errorCount"] == 0
        assert data["exchange"]["errorCount"] == 0
    
    @patch('app.dashboard.check_database_health')
    @patch('app.dashboard.check_rss_feeds_health')
    @patch('app.dashboard.check_exchange_health')
    @patch('app.dashboard.check_openai_health')
    def test_detailed_health_with_errors(
        self,
        mock_openai,
        mock_exchange,
        mock_rss,
        mock_db,
        client,
        mock_error_tracker,
        sample_errors
    ):
        """Test detailed health when services have errors."""
        # Mock degraded service
        mock_openai.return_value = {"status": "degraded", "latency": 1000}
        mock_exchange.return_value = {"status": "operational", "latency": 150}
        mock_rss.return_value = {"status": "operational", "latency": 200}
        mock_db.return_value = {"status": "operational", "latency": 50}
        
        # Mock error tracker with errors
        def get_error_count_side_effect(component):
            if component == "openai":
                return 5
            return 0
        
        def get_last_error_side_effect(component):
            if component == "openai":
                return sample_errors[0]
            return None
        
        def get_component_errors_side_effect(component):
            if component == "openai":
                return [sample_errors[0]]
            return []
        
        mock_error_tracker.get_error_count.side_effect = get_error_count_side_effect
        mock_error_tracker.get_last_error.side_effect = get_last_error_side_effect
        mock_error_tracker.get_component_errors.side_effect = get_component_errors_side_effect
        
        response = client.get("/api/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        
        # OpenAI should show errors
        assert data["openai"]["status"] == "degraded"
        assert data["openai"]["errorCount"] == 5
        assert data["openai"]["lastError"] is not None
        assert data["openai"]["lastError"]["message"] == "API key invalid"
        assert len(data["openai"]["recentErrors"]) > 0
        
        # Other services should be clean
        assert data["exchange"]["errorCount"] == 0
        assert data["exchange"]["lastError"] is None


class TestEndpointIntegration:
    """Integration tests for health endpoints."""
    
    def test_error_workflow(self, client, mock_error_tracker, sample_errors):
        """Test complete error workflow: log -> view -> clear."""
        # Setup: errors exist
        mock_error_tracker.get_errors.return_value = sample_errors
        
        # 1. View errors
        response = client.get("/api/errors")
        assert response.status_code == 200
        assert response.json()["total"] == 2
        
        # 2. Clear specific component
        mock_error_tracker.clear_errors.return_value = 1
        response = client.post("/api/errors/clear?component=openai")
        assert response.status_code == 200
        assert response.json()["cleared"] == 1
        
        # 3. View remaining errors
        mock_error_tracker.get_errors.return_value = [sample_errors[1]]
        response = client.get("/api/errors")
        assert response.status_code == 200
        assert response.json()["total"] == 1
    
    @patch('app.dashboard.check_openai_health')
    def test_test_and_monitor_workflow(self, mock_check, client, mock_error_tracker):
        """Test workflow: test service -> monitor errors."""
        # 1. Test fails
        mock_check.return_value = {
            "status": "error",
            "message": "Connection refused"
        }
        
        response = client.post("/api/test/openai")
        assert response.status_code == 200
        assert response.json()["success"] is False
        
        # Error should be logged
        mock_error_tracker.log_error.assert_called()
        
        # 2. View logged error
        mock_error_tracker.get_errors.return_value = [{
            "component": "openai",
            "message": "OpenAI test failed: Connection refused",
            "severity": "warning",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
        
        response = client.get("/api/errors?component=openai")
        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) == 1
        assert "Connection refused" in data["errors"][0]["message"]


class TestErrorLogging:
    """Test error logging in health endpoints."""
    
    @patch('app.dashboard.check_openai_health')
    def test_test_endpoint_logs_error_on_failure(
        self,
        mock_check,
        client,
        mock_error_tracker
    ):
        """Test that test endpoints log errors on failure."""
        mock_check.return_value = {
            "status": "error",
            "message": "Authentication failed"
        }
        
        client.post("/api/test/openai")
        
        # Should have logged error
        mock_error_tracker.log_error.assert_called_once()
        call_args = mock_error_tracker.log_error.call_args
        
        assert call_args[1]["component"] == "openai"
        assert "failed" in call_args[1]["message"].lower()
    
    @patch('app.dashboard.check_openai_health')
    def test_test_endpoint_no_log_on_success(
        self,
        mock_check,
        client,
        mock_error_tracker
    ):
        """Test that test endpoints don't log on success."""
        mock_check.return_value = {
            "status": "operational",
            "message": "OK"
        }
        
        client.post("/api/test/openai")
        
        # Should NOT have logged error
        mock_error_tracker.log_error.assert_not_called()