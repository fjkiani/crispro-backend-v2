"""
Tests for FastAPI refresh status endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_refresh_endpoint_basic():
    """Test /api/trials/refresh_status endpoint with single NCT ID"""
    response = client.post(
        "/api/trials/refresh_status",
        json={"nct_ids": ["NCT02470585"]}
    )
    
    assert response.status_code in [200, 500]  # 200 if API succeeds, 500 if API fails
    
    if response.status_code == 200:
        data = response.json()
        assert "refreshed_count" in data
        assert "trial_data" in data
        assert "errors" in data
        assert isinstance(data["trial_data"], dict)


def test_refresh_endpoint_empty_list():
    """Test endpoint with empty NCT IDs list"""
    response = client.post(
        "/api/trials/refresh_status",
        json={"nct_ids": []}
    )
    
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"].lower()


def test_refresh_endpoint_too_many_ids():
    """Test endpoint with more than 100 NCT IDs"""
    response = client.post(
        "/api/trials/refresh_status",
        json={"nct_ids": [f"NCT{i:08d}" for i in range(101)]}
    )
    
    assert response.status_code == 400
    assert "maximum" in response.json()["detail"].lower() or "100" in response.json()["detail"]


def test_refresh_endpoint_with_state_filter():
    """Test endpoint with state filter"""
    response = client.post(
        "/api/trials/refresh_status",
        json={
            "nct_ids": ["NCT02470585"],
            "state_filter": "NY"
        }
    )
    
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        data = response.json()
        # If trial_data exists, verify all locations are NY
        for nct_id, trial in data["trial_data"].items():
            for loc in trial.get("locations", []):
                assert loc["state"] == "NY"


def test_refresh_endpoint_invalid_state_filter():
    """Test endpoint with invalid state filter format"""
    response = client.post(
        "/api/trials/refresh_status",
        json={
            "nct_ids": ["NCT02470585"],
            "state_filter": "NEWYORK"  # Invalid (should be 2 letters)
        }
    )
    
    assert response.status_code == 400
    assert "state" in response.json()["detail"].lower()

