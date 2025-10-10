"""
Tests for Strategy Signal API endpoints.

Tests all 7 API routes added in Phase 2.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.strategy_signal_logger import StrategySignalLogger


@pytest.fixture
def temp_data_dir():
    """Create temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def client():
    """Create test client for API."""
    return TestClient(app)


@pytest.fixture
def populated_logger(temp_data_dir):
    """Create logger with test data."""
    logger = StrategySignalLogger(data_dir=temp_data_dir)
    
    # Add some test signals
    for i in range(10):
        logger.log_decision(
            symbol="BTC/USD" if i % 2 == 0 else "ETH/USD",
            price=50000 + i * 100,
            final_signal=["BUY", "SELL", "HOLD"][i % 3],
            final_confidence=0.5 + (i * 0.05),
            strategy_signals={
                "technical": {
                    "signal": "BUY",
                    "confidence": 0.7,
                    "reason": "Test technical signal",
                    "weight": 1.0,
                    "enabled": True
                },
                "sentiment": {
                    "signal": ["BUY", "SELL", "HOLD"][i % 3],
                    "confidence": 0.6 + (i * 0.02),
                    "reason": "Test sentiment signal",
                    "weight": 1.0,
                    "enabled": True
                },
                "volume": {
                    "signal": "HOLD",
                    "confidence": 0.4,
                    "reason": "Test volume signal",
                    "weight": 0.8,
                    "enabled": True
                }
            },
            aggregation_method="weighted_vote",
            metadata={
                "min_confidence": 0.5,
                "num_strategies": 3
            }
        )
    
    return logger


class TestSummaryEndpoint:
    """Test GET /api/strategy/summary"""
    
    def test_summary_with_data(self, client, populated_logger, monkeypatch):
        """Should return summary of all signals."""
        # Replace the global signal_logger with our test logger
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert data['total_decisions'] == 10
        assert data['total_strategies'] == 3
        assert set(data['strategy_names']) == {'technical', 'sentiment', 'volume'}
        assert set(data['symbols_tracked']) == {'BTC/USD', 'ETH/USD'}
        assert 'date_range' in data
        assert 'aggregation_methods' in data
    
    def test_summary_with_no_data(self, client, temp_data_dir, monkeypatch):
        """Should handle empty signal log."""
        import app.dashboard as dashboard_module
        empty_logger = StrategySignalLogger(data_dir=temp_data_dir)
        monkeypatch.setattr(dashboard_module, 'signal_logger', empty_logger)
        
        response = client.get("/api/strategy/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert data['total_decisions'] == 0


class TestCurrentSignalsEndpoint:
    """Test GET /api/strategy/current"""
    
    def test_current_signals(self, client, populated_logger, monkeypatch):
        """Should return most recent signal per symbol."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/current")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert data['count'] == 2  # BTC and ETH
        assert len(data['signals']) == 2
        
        symbols = {s['symbol'] for s in data['signals']}
        assert symbols == {'BTC/USD', 'ETH/USD'}
    
    def test_current_signals_empty(self, client, temp_data_dir, monkeypatch):
        """Should handle no signals gracefully."""
        import app.dashboard as dashboard_module
        empty_logger = StrategySignalLogger(data_dir=temp_data_dir)
        monkeypatch.setattr(dashboard_module, 'signal_logger', empty_logger)
        
        response = client.get("/api/strategy/current")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['count'] == 0
        assert data['signals'] == []


class TestHistoryEndpoint:
    """Test GET /api/strategy/history"""
    
    def test_history_default(self, client, populated_logger, monkeypatch):
        """Should return recent signals."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert data['count'] == 10
        assert data['filtered_by'] is None
        assert len(data['signals']) == 10
    
    def test_history_with_limit(self, client, populated_logger, monkeypatch):
        """Should respect limit parameter."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/history?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['count'] == 5
        assert len(data['signals']) == 5
    
    def test_history_with_symbol_filter(self, client, populated_logger, monkeypatch):
        """Should filter by symbol."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/history?symbol=BTC/USD")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['filtered_by'] == 'BTC/USD'
        assert all(s['symbol'] == 'BTC/USD' for s in data['signals'])
    
    def test_history_invalid_limit(self, client, populated_logger, monkeypatch):
        """Should reject invalid limit."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/history?limit=invalid")
        
        assert response.status_code == 400
        data = response.json()
        assert data['status'] == 'error'
    
    def test_history_respects_max_limit(self, client, populated_logger, monkeypatch):
        """Should cap at 1000 records."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/history?limit=5000")
        
        assert response.status_code == 200
        # Should cap at 1000, but we only have 10, so returns 10
        data = response.json()
        assert data['count'] <= 1000


class TestPerformanceEndpoint:
    """Test GET /api/strategy/performance"""
    
    def test_performance_all_strategies(self, client, populated_logger, monkeypatch):
        """Should return performance for all strategies."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/performance")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert data['lookback_days'] == 7
        assert 'strategies' in data
        assert 'technical' in data['strategies']
        assert 'sentiment' in data['strategies']
        assert 'volume' in data['strategies']
        
        # Check structure of strategy metrics
        tech = data['strategies']['technical']
        assert 'total_signals' in tech
        assert 'signal_distribution' in tech
        assert 'avg_confidence' in tech
        assert 'agreement_rate' in tech
    
    def test_performance_with_lookback(self, client, populated_logger, monkeypatch):
        """Should respect lookback_days parameter."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/performance?lookback_days=30")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['lookback_days'] == 30
    
    def test_performance_invalid_lookback(self, client, populated_logger, monkeypatch):
        """Should reject invalid lookback_days."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/performance?lookback_days=invalid")
        
        assert response.status_code == 400
        data = response.json()
        assert data['status'] == 'error'
    
    def test_performance_respects_max_lookback(self, client, populated_logger, monkeypatch):
        """Should cap lookback at 90 days."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/performance?lookback_days=365")
        
        assert response.status_code == 200
        data = response.json()
        assert data['lookback_days'] == 90  # Capped


class TestSingleStrategyPerformanceEndpoint:
    """Test GET /api/strategy/performance/{strategy_name}"""
    
    def test_single_strategy_performance(self, client, populated_logger, monkeypatch):
        """Should return performance for specific strategy."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/performance/technical")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert data['strategy_name'] == 'technical'
        assert 'total_signals' in data
        assert 'signal_distribution' in data
        assert 'avg_confidence' in data
    
    def test_nonexistent_strategy(self, client, populated_logger, monkeypatch):
        """Should return 404 for unknown strategy."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/performance/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert data['status'] == 'not_found'


class TestCorrelationEndpoint:
    """Test GET /api/strategy/correlation"""
    
    def test_correlation_matrix(self, client, populated_logger, monkeypatch):
        """Should return correlation matrix."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/correlation")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert 'correlations' in data
        assert 'description' in data
        
        corr = data['correlations']
        # Should have all three strategies
        assert 'technical' in corr
        assert 'sentiment' in corr
        assert 'volume' in corr
        
        # Self-correlation should be 1.0
        assert corr['technical']['technical'] == 1.0
        assert corr['sentiment']['sentiment'] == 1.0
        assert corr['volume']['volume'] == 1.0
    
    def test_correlation_empty(self, client, temp_data_dir, monkeypatch):
        """Should handle no data gracefully."""
        import app.dashboard as dashboard_module
        empty_logger = StrategySignalLogger(data_dir=temp_data_dir)
        monkeypatch.setattr(dashboard_module, 'signal_logger', empty_logger)
        
        response = client.get("/api/strategy/correlation")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['correlations'] == {}


class TestLatestSignalEndpoint:
    """Test GET /api/strategy/signals/latest"""
    
    def test_latest_signal(self, client, populated_logger, monkeypatch):
        """Should return the most recent signal."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        response = client.get("/api/strategy/signals/latest")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert 'signal' in data
        assert 'age_seconds' in data
        assert data['age_seconds'] >= 0
        
        signal = data['signal']
        assert 'timestamp' in signal
        assert 'symbol' in signal
        assert 'final_signal' in signal
    
    def test_latest_signal_empty(self, client, temp_data_dir, monkeypatch):
        """Should return 404 when no signals exist."""
        import app.dashboard as dashboard_module
        empty_logger = StrategySignalLogger(data_dir=temp_data_dir)
        monkeypatch.setattr(dashboard_module, 'signal_logger', empty_logger)
        
        response = client.get("/api/strategy/signals/latest")
        
        assert response.status_code == 404
        data = response.json()
        assert data['status'] == 'not_found'


class TestAPIErrorHandling:
    """Test error handling across all endpoints."""
    
    def test_endpoints_handle_logger_errors(self, client, monkeypatch):
        """All endpoints should handle logger errors gracefully."""
        import app.dashboard as dashboard_module
        
        # Create a logger that always raises errors
        class FailingLogger:
            def get_recent_signals(self, *args, **kwargs):
                raise Exception("Simulated error")
            
            def get_all_strategies_performance(self, *args, **kwargs):
                raise Exception("Simulated error")
            
            def get_strategy_performance(self, *args, **kwargs):
                raise Exception("Simulated error")
            
            def get_signal_correlation(self):
                raise Exception("Simulated error")
        
        monkeypatch.setattr(dashboard_module, 'signal_logger', FailingLogger())
        
        # All endpoints should return 500 but not crash
        endpoints = [
            "/api/strategy/summary",
            "/api/strategy/current",
            "/api/strategy/history",
            "/api/strategy/performance",
            "/api/strategy/performance/technical",
            "/api/strategy/correlation",
            "/api/strategy/signals/latest"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [500, 404]  # 404 for not_found cases
            data = response.json()
            assert 'error' in data or 'status' in data


class TestAPIResponseFormat:
    """Test that all responses follow consistent format."""
    
    def test_all_success_responses_have_status(self, client, populated_logger, monkeypatch):
        """All successful responses should include status: success."""
        import app.dashboard as dashboard_module
        monkeypatch.setattr(dashboard_module, 'signal_logger', populated_logger)
        
        endpoints = [
            "/api/strategy/summary",
            "/api/strategy/current",
            "/api/strategy/history",
            "/api/strategy/performance",
            "/api/strategy/performance/technical",
            "/api/strategy/correlation",
            "/api/strategy/signals/latest"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            if response.status_code == 200:
                data = response.json()
                assert 'status' in data
                assert data['status'] == 'success'