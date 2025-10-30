"""
Test configuration API endpoints.
"""
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestConfigAPI:
    """Test configuration management endpoints."""
    
    def test_get_config_returns_defaults(self):
        """Test GET /api/config returns configuration with defaults."""
        response = client.get("/api/config")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "config" in data
        
        config = data["config"]
        
        # Verify required fields exist
        assert "trading_fee_percent" in config
        assert "trading_mode" in config
        assert "strategies" in config
        assert "risk_management" in config
        assert "aggregation" in config
    
    def test_get_config_has_strategy_settings(self):
        """Test config includes individual strategy settings."""
        response = client.get("/api/config")
        config = response.json()["config"]
        
        # Check strategy settings
        assert "sentiment" in config["strategies"]
        assert "technical" in config["strategies"]
        assert "volume" in config["strategies"]
        
        # Each strategy should have enabled and weight
        for strategy in ["sentiment", "technical", "volume"]:
            assert "enabled" in config["strategies"][strategy]
            assert "weight" in config["strategies"][strategy]
            assert isinstance(config["strategies"][strategy]["enabled"], bool)
            assert isinstance(config["strategies"][strategy]["weight"], (int, float))
    
    def test_get_config_has_risk_management(self):
        """Test config includes risk management settings."""
        response = client.get("/api/config")
        config = response.json()["config"]
        
        risk = config["risk_management"]
        
        assert "position_size_percent" in risk
        assert "max_daily_loss_percent" in risk
        assert "max_open_positions" in risk
        
        assert isinstance(risk["position_size_percent"], (int, float))
        assert isinstance(risk["max_daily_loss_percent"], (int, float))
    
    def test_get_config_has_aggregation_settings(self):
        """Test config includes aggregation settings."""
        response = client.get("/api/config")
        config = response.json()["config"]
        
        agg = config["aggregation"]
        
        assert "method" in agg
        assert "min_confidence" in agg
        
        assert agg["method"] in ["weighted_vote", "highest_confidence", "unanimous"]
        assert 0 <= agg["min_confidence"] <= 1
    
    def test_update_config_strategy_weight(self):
        """Test updating strategy weight."""
        # Get current config
        current = client.get("/api/config").json()["config"]
        
        # Update sentiment weight
        new_config = {
            "strategies": {
                "sentiment": {"enabled": True, "weight": 1.5},
                "technical": current["strategies"]["technical"],
                "volume": current["strategies"]["volume"]
            }
        }
        
        response = client.post("/api/config", json={"config": new_config})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["config"]["strategies"]["sentiment"]["weight"] == 1.5
    
    def test_update_config_min_confidence(self):
        """Test updating minimum confidence threshold."""
        new_config = {
            "aggregation": {
                "method": "weighted_vote",
                "min_confidence": 0.6
            }
        }
        
        response = client.post("/api/config", json={"config": new_config})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["config"]["aggregation"]["min_confidence"] == 0.6
    
    def test_update_config_risk_management(self):
        """Test updating risk management settings."""
        new_config = {
            "risk_management": {
                "position_size_percent": 5.0,
                "max_daily_loss_percent": 10.0,
                "max_open_positions": 5
            }
        }
        
        response = client.post("/api/config", json={"config": new_config})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["config"]["risk_management"]["position_size_percent"] == 5.0
        assert data["config"]["risk_management"]["max_daily_loss_percent"] == 10.0
        assert data["config"]["risk_management"]["max_open_positions"] == 5
    
    def test_update_config_rejects_invalid_trading_mode(self):
        """Test that invalid trading mode is rejected."""
        new_config = {
            "trading_mode": "invalid_mode"
        }
        
        response = client.post("/api/config", json={"config": new_config})
        
        assert response.status_code == 400
        assert "error" in response.json()
    
    def test_update_config_accepts_valid_trading_mode(self):
        """Test that valid trading modes are accepted."""
        for mode in ["paper", "live"]:
            response = client.post("/api/config", json={"config": {"trading_mode": mode}})
            
            assert response.status_code == 200
            assert response.json()["config"]["trading_mode"] == mode
    
    def test_disable_strategy(self):
        """Test disabling a strategy."""
        new_config = {
            "strategies": {
                "volume": {"enabled": False, "weight": 0.8}
            }
        }
        
        response = client.post("/api/config", json={"config": new_config})
        
        assert response.status_code == 200
        assert response.json()["config"]["strategies"]["volume"]["enabled"] is False
    
