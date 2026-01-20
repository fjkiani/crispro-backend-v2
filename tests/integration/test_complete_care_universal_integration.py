"""
Integration Tests for Universal Complete Care Orchestrator

Tests the complete care orchestrator endpoint with real API calls.
Requires server to be running.
"""

import pytest
import httpx
import asyncio
from typing import Dict, Any


API_BASE = "http://localhost:8000"


# Test profiles
SIMPLE_PROFILE = {
    "patient_id": "test_integration_001",
    "name": "Integration Test Patient",
    "disease": "ovarian_cancer_hgs",
    "stage": "IVB",
    "treatment_line": "first-line",
    "location": "New York",
    "zip_code": "10001",
    "biomarkers": {
        "ca125_value": 1500.0,
        "germline_status": "negative"
    },
    "tumor_context": {
        "somatic_mutations": [
            {
                "gene": "BRCA1",
                "hgvs_p": "p.Arg1835Ter",
                "consequence": "stop_gained"
            }
        ],
        "hrd_score": 35.0
    }
}

FULL_PROFILE = {
    "patient_id": "test_integration_002",
    "demographics": {
        "name": "Full Profile Patient",
        "age": 45,
        "sex": "female"
    },
    "disease": {
        "type": "ovarian_cancer_hgs",
        "stage": "IVB"
    },
    "treatment": {
        "line": "first-line"
    },
    "logistics": {
        "location": "New York",
        "zip_code": "10001"
    },
    "biomarkers": {
        "ca125_value": 1500.0
    },
    "tumor_context": {
        "somatic_mutations": [
            {
                "gene": "BRCA1",
                "hgvs_p": "p.Arg1835Ter"
            }
        ]
    }
}


@pytest.mark.asyncio
async def test_complete_care_universal_simple_profile():
    """Test /api/complete_care/universal with simple profile."""
    request_payload = {
        "patient_profile": SIMPLE_PROFILE,
        "include_trials": True,
        "include_soc": True,
        "include_biomarker": True,
        "include_wiwfm": True
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{API_BASE}/api/complete_care/universal",
                json=request_payload
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
            
            data = response.json()
            
            # Verify response structure
            assert "summary" in data
            assert "provenance" in data
            
            # Verify components are present (may be None if service unavailable)
            assert "trials" in data
            assert "soc_recommendation" in data
            assert "biomarker_intelligence" in data
            assert "wiwfm" in data
            
        except httpx.ConnectError:
            pytest.skip("Server not running - skipping integration test")


@pytest.mark.asyncio
async def test_complete_care_universal_full_profile():
    """Test /api/complete_care/universal with full profile."""
    request_payload = {
        "patient_profile": FULL_PROFILE,
        "include_trials": True,
        "include_soc": True,
        "include_biomarker": True
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{API_BASE}/api/complete_care/universal",
                json=request_payload
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
            
            data = response.json()
            
            # Verify response structure
            assert "summary" in data
            assert "provenance" in data
            
        except httpx.ConnectError:
            pytest.skip("Server not running - skipping integration test")


@pytest.mark.asyncio
async def test_complete_care_universal_optional_services():
    """Test /api/complete_care/universal with optional services disabled."""
    request_payload = {
        "patient_profile": SIMPLE_PROFILE,
        "include_trials": False,
        "include_soc": True,
        "include_biomarker": True,
        "include_wiwfm": False,
        "include_food": False,
        "include_resistance": False
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{API_BASE}/api/complete_care/universal",
                json=request_payload
            )
            
            assert response.status_code == 200
            
            data = response.json()
            
            # Verify optional services are None when disabled
            assert data.get("trials") is None or data.get("trials") == []
            assert data.get("wiwfm") is None
            
        except httpx.ConnectError:
            pytest.skip("Server not running - skipping integration test")


@pytest.mark.asyncio
async def test_complete_care_universal_error_handling():
    """Test /api/complete_care/universal error handling with invalid profile."""
    request_payload = {
        "patient_profile": {
            "patient_id": "invalid"
            # Missing required fields
        }
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{API_BASE}/api/complete_care/universal",
                json=request_payload
            )
            
            # Should return 422 (validation error) or 400 (bad request)
            assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
            
        except httpx.ConnectError:
            pytest.skip("Server not running - skipping integration test")


@pytest.mark.asyncio
async def test_biomarker_analyze_endpoint():
    """Test /api/biomarker/intelligence endpoint."""
    request_payload = {
        "disease_type": "ovarian_cancer_hgs",
        "biomarker_type": "ca125",
        "current_value": 1500.0,
        "baseline_value": 35.0,
        "cycle": 2,
        "treatment_ongoing": True
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{API_BASE}/api/biomarker/intelligence",
                json=request_payload
            )
            
            assert response.status_code == 200
            
            data = response.json()
            
            # Verify response structure
            assert "burden_assessment" in data or "analysis" in data
            
        except httpx.ConnectError:
            pytest.skip("Server not running - skipping integration test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


