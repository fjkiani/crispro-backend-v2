"""
Ayesha E2E Smoke Test - Python Version

CLINICAL PURPOSE: Validate all backend endpoints for AK
Comprehensive structural and clinical validation

This is NOT a demo. Real validation for Ayesha's life.

Author: Zo
Date: January 13, 2025
For: AK - Stage IVB HGSOC
"""

import pytest
import httpx
import json
from typing import Dict, Any


# Ayesha's actual clinical profile
AYESHA_PROFILE = {
    "ca125_value": 2842.0,
    "stage": "IVB",
    "treatment_line": "first-line",
    "germline_status": "negative",
    "has_ascites": True,
    "has_peritoneal_disease": True,
    "location_state": "NY",
    "ecog_status": None,  # Unknown (needs assessment)
    "max_results": 10
}

COMPLETE_CARE_REQUEST = {
    "ca125_value": 2842.0,
    "stage": "IVB",
    "treatment_line": "first-line",
    "germline_status": "negative",
    "has_ascites": True,
    "has_peritoneal_disease": True,
    "location_state": "NY",
    "include_trials": True,
    "include_soc": True,
    "include_ca125": True,
    "include_wiwfm": True,
    "include_food": False,
    "include_resistance": False,
    "max_trials": 10
}


@pytest.mark.asyncio
class TestAyeshaE2ESmoke:
    """E2E smoke tests for Ayesha's care plan"""
    
    async def test_health_checks(self):
        """Test all health check endpoints"""
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10.0) as client:
            # Main API health
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"  # API returns "healthy", not "ok"
            
            # Ayesha trials health
            response = await client.get("/api/ayesha/trials/health")
            assert response.status_code == 200
            assert "operational" in response.json()["status"]
            
            # Complete care v2 health
            response = await client.get("/api/ayesha/complete_care_v2/health")
            assert response.status_code == 200
            assert "operational" in response.json()["status"]
    
    async def test_ayesha_trials_search_structure(self):
        """Test trials search returns correct structure"""
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
            response = await client.post(
                "/api/ayesha/trials/search",
                json=AYESHA_PROFILE
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Required top-level fields
            assert "trials" in data
            assert "soc_recommendation" in data
            assert "ca125_intelligence" in data
            assert "ngs_fast_track" in data
            assert "summary" in data
            assert "provenance" in data
            
            # Trials structure
            assert isinstance(data["trials"], list)
            assert len(data["trials"]) <= 10
            
            # Each trial should have required fields
            if data["trials"]:
                trial = data["trials"][0]
                assert "nct_id" in trial
                assert "title" in trial
                assert "match_score" in trial
                assert "reasoning" in trial
                assert "eligibility_checklist" in trial
                assert "confidence_gates" in trial
    
    async def test_ayesha_trials_clinical_validation(self):
        """Test clinical correctness of trials response"""
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
            response = await client.post(
                "/api/ayesha/trials/search",
                json=AYESHA_PROFILE
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # SOC should include bevacizumab (ascites present)
            soc = data["soc_recommendation"]
            assert "Carboplatin" in soc["regimen"]
            assert "Paclitaxel" in soc["regimen"]
            
            # Check add-ons for bevacizumab
            add_ons = soc.get("add_ons", [])
            assert len(add_ons) > 0, "Expected bevacizumab add-on for ascites"
            
            bev_found = False
            for addon in add_ons:
                if "Bevacizumab" in addon.get("drug", ""):
                    bev_found = True
                    assert "ascites" in addon["rationale"].lower() or "peritoneal" in addon["rationale"].lower()
            
            assert bev_found, "Bevacizumab not found in add-ons (required for ascites)"
            
            # SOC confidence should be high (guideline-based)
            assert soc["confidence"] >= 0.95, f"SOC confidence too low: {soc['confidence']}"
            
            # CA-125 burden should be EXTENSIVE
            ca125 = data["ca125_intelligence"]
            assert ca125["burden_class"] == "EXTENSIVE", f"CA-125 burden incorrect: {ca125['burden_class']}"
            # Note: current_value is input, not in response. Response contains burden_class, burden_score, forecast, etc.
            assert "burden_score" in ca125, "CA-125 intelligence should include burden_score"
            assert ca125["burden_score"] > 0.7, f"CA-125 burden_score should be high for value 2842, got {ca125.get('burden_score')}"

            # Note: current_value is input, not in response. Response contains burden_class, burden_score, forecast, etc.
            assert "burden_score" in ca125, "CA-125 intelligence should include burden_score"
            assert ca125["burden_score"] > 0.7, f"CA-125 burden_score should be high for value 2842, got {ca125.get('burden_score')}"
            
            # Note: current_value is input, not in response. Response contains burden_class, burden_score, forecast, etc.
            assert "burden_score" in ca125, "CA-125 intelligence should include burden_score"
            assert ca125["burden_score"] > 0.7, f"CA-125 burden_score should be high for value 2842, got {ca125.get('burden_score')}"
            assert ca125["burden_class"] == "EXTENSIVE", f"CA-125 burden incorrect: {ca125['burden_class']}"
            
            # Forecast should have complete response target and expectations
            forecast = ca125["forecast"]
            # When baseline is not provided (first measurement), forecast contains general expectations
            assert "complete_response_target" in forecast, "Forecast should include complete response target"
            assert "complete_response_target_unit" in forecast, "Forecast should include target unit"
            assert forecast.get("complete_response_target") == 35, f"Complete response target should be 35 U/mL, got {forecast.get('complete_response_target')}"
            # Note field contains general expectations for cycle 3 and cycle 6
            assert "note" in forecast, "Forecast should include note with general expectations"
            assert "cycle 3" in forecast.get("note", "").lower() or "70%" in forecast.get("note", ""), "Note should mention cycle 3 expectations"
            
            # NGS fast-track should have recommendations
            ngs = data["ngs_fast_track"]
            assert "checklist" in ngs
            assert len(ngs["checklist"]) >= 2, "Expected at least ctDNA + HRD tests"
            
            # Find ctDNA and HRD tests
            # Actual test names: "Guardant360 CDx" (ctDNA), "MyChoice CDx" (HRD)
            ctdna_found = False
            hrd_found = False
            for test in ngs["checklist"]:
                test_name = test.get("test_name", "").upper()
                # Check for ctDNA test (Guardant360 CDx)
                if "GUARDANT" in test_name or "CTDNA" in test_name:
                    ctdna_found = True
                    assert test["recommended"] == True, f"ctDNA test should be recommended: {test}"
                    assert test.get("turnaround_time_days", 999) <= 14, f"ctDNA turnaround should be <= 14 days, got {test.get('turnaround_time_days')}"
                # Check for HRD test (MyChoice CDx)
                if "MYCHOICE" in test_name or ("HRD" in test_name and "MYCHOICE" not in test_name):
                    hrd_found = True
                    assert test["recommended"] == True, f"HRD test should be recommended: {test}"
            
            assert ctdna_found, f"ctDNA test (Guardant360) not found in NGS checklist. Found tests: {[t.get('test_name') for t in ngs['checklist']]}"
            assert hrd_found, f"HRD test (MyChoice) not found in NGS checklist. Found tests: {[t.get('test_name') for t in ngs['checklist']]}"
    async def test_complete_care_v2_structure(self):
        """Test complete care v2 returns correct structure"""
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
            response = await client.post(
                "/api/ayesha/complete_care_v2",
                json=COMPLETE_CARE_REQUEST
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should have all requested components
            assert "trials" in data
            assert "soc_recommendation" in data
            assert "ca125_intelligence" in data
            assert "wiwfm" in data
            assert "summary" in data
            assert "provenance" in data
            
            # Summary should list components
            summary = data["summary"]
            assert "components_included" in summary
            assert "clinical_trials" in summary["components_included"]
            assert "soc_recommendation" in summary["components_included"]
            assert "ca125_monitoring" in summary["components_included"]
    
    async def test_wiwfm_awaiting_ngs_message(self):
        """Test WIWFM returns 'awaiting NGS' when no tumor context"""
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
            response = await client.post(
                "/api/ayesha/complete_care_v2",
                json=COMPLETE_CARE_REQUEST
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # WIWFM should return "awaiting_ngs" status (honest, not fake predictions)
            wiwfm = data.get("wiwfm", {})
            assert wiwfm.get("status") == "awaiting_ngs", \
                f"Expected 'awaiting_ngs', got '{wiwfm.get('status')}'"
            
            assert "message" in wiwfm
            assert "NGS" in wiwfm["message"] or "tumor" in wiwfm["message"]
            
            # Should include fast-track info
            assert "ngs_fast_track" in wiwfm
    
    async def test_ayesha_trials_confidence_gates(self):
        """Test confidence gates are correctly calculated and displayed"""
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
            response = await client.post(
                "/api/ayesha/trials/search",
                json=AYESHA_PROFILE
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Check SOC confidence gates
            soc = data["soc_recommendation"]
            assert soc["confidence"] >= 0.95, "SOC confidence should be ≥0.95 (guideline-aligned)"
            assert "confidence_gate_reasons" in soc
            assert len(soc["confidence_gate_reasons"]) >= 2
            
            # Check first trial's confidence gates (if trials returned)
            if data["trials"]:
                trial = data["trials"][0]
                assert "confidence_gates" in trial
                assert isinstance(trial["confidence_gates"], list)
                
                # Should have at least eligibility gate
                assert any("Eligibility" in gate or "SOC" in gate for gate in trial["confidence_gates"])


# ===================================
# RUN TESTS
# ===================================

if __name__ == "__main__":
    print("⚔️ AYESHA E2E SMOKE TEST - PYTHON VERSION ⚔️")
    print("=" * 60)
    print()
    print("Patient: AK")
    print("Diagnosis: Stage IVB High-Grade Serous Ovarian Cancer")
    print("Status: Treatment-naive, germline-negative, CA-125 2842")
    print()
    print("=" * 60)
    print()
    
    # Run pytest
    pytest.main([__file__, "-v", "--tb=short"])


