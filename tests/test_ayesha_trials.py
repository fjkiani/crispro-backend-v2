"""
Unit Tests for Ayesha Trials Service

Testing REAL clinical decision support for AK (Stage IVB ovarian cancer).
NOT a demo. These tests validate life-or-death filtering logic.

Author: Zo
Date: January 13, 2025
Purpose: Ensure Ayesha gets the RIGHT trials, not just any trials
"""

import pytest
from api.services.ca125_intelligence import get_ca125_service


class TestCA125Intelligence:
    """Test CA-125 Intelligence Service"""
    
    def test_burden_classification_extensive(self):
        """Test Ayesha's CA-125 2,842 → EXTENSIVE"""
        service = get_ca125_service()
        result = service.analyze_ca125(current_value=2842.0)
        
        assert result["burden_class"] == "EXTENSIVE"
        assert result["burden_score"] > 0.7  # Very high burden
    
    def test_burden_classification_moderate(self):
        """Test moderate burden (100-500)"""
        service = get_ca125_service()
        result = service.analyze_ca125(current_value=250.0)
        
        assert result["burden_class"] == "MODERATE"
    
    def test_burden_classification_minimal(self):
        """Test minimal burden (<100)"""
        service = get_ca125_service()
        result = service.analyze_ca125(current_value=50.0)
        
        assert result["burden_class"] == "MINIMAL"
    
    def test_forecast_without_baseline(self):
        """Test forecast when baseline not provided (pre-treatment)"""
        service = get_ca125_service()
        result = service.analyze_ca125(current_value=2842.0)
        
        assert "forecast" in result
        assert result["forecast"]["complete_response_target"] == 35
        assert "note" in result["forecast"]  # Note about missing baseline
    
    def test_forecast_with_baseline_cycle3(self):
        """Test forecast with baseline and cycle 3 assessment"""
        service = get_ca125_service()
        result = service.analyze_ca125(
            current_value=850.0,  # 70% drop from 2842
            baseline_value=2842.0,
            cycle=3
        )
        
        assert "forecast" in result
        assert result["forecast"]["cycle3_status"] == "ON_TRACK"
        assert result["forecast"]["actual_drop_percent"] >= 70
    
    def test_forecast_with_baseline_below_expected(self):
        """Test forecast when response is below expected (resistance signal)"""
        service = get_ca125_service()
        result = service.analyze_ca125(
            current_value=2000.0,  # Only 30% drop from 2842
            baseline_value=2842.0,
            cycle=3
        )
        
        assert "forecast" in result
        assert result["forecast"]["cycle3_status"] == "BELOW_EXPECTED"
        assert result["forecast"]["actual_drop_percent"] < 70
    
    def test_resistance_signal_on_therapy_rise(self):
        """Test resistance detection: CA-125 rising on therapy"""
        service = get_ca125_service()
        result = service.analyze_ca125(
            current_value=3000.0,  # Higher than baseline
            baseline_value=2842.0,
            cycle=2,
            treatment_ongoing=True
        )
        
        assert len(result["resistance_signals"]) > 0
        assert any(sig["type"] == "ON_THERAPY_RISE" for sig in result["resistance_signals"])
        assert any(sig["severity"] == "HIGH" for sig in result["resistance_signals"])
    
    def test_resistance_signal_inadequate_response(self):
        """Test resistance detection: <50% drop by cycle 3"""
        service = get_ca125_service()
        result = service.analyze_ca125(
            current_value=1500.0,  # 47% drop from 2842 (below 50% threshold)
            baseline_value=2842.0,
            cycle=3,
            treatment_ongoing=True
        )
        
        assert len(result["resistance_signals"]) > 0
        assert any(sig["type"] == "INADEQUATE_RESPONSE_CYCLE3" for sig in result["resistance_signals"])
    
    def test_resistance_signal_minimal_response(self):
        """Test resistance detection: minimal drop (<30%)"""
        service = get_ca125_service()
        result = service.analyze_ca125(
            current_value=2400.0,  # 16% drop from 2842
            baseline_value=2842.0,
            cycle=2,
            treatment_ongoing=True
        )
        
        assert len(result["resistance_signals"]) > 0
        assert any(sig["type"] == "MINIMAL_RESPONSE" for sig in result["resistance_signals"])
    
    def test_no_resistance_signals_good_response(self):
        """Test no resistance signals when response is good"""
        service = get_ca125_service()
        result = service.analyze_ca125(
            current_value=500.0,  # 82% drop from 2842
            baseline_value=2842.0,
            cycle=3,
            treatment_ongoing=True
        )
        
        assert len(result["resistance_signals"]) == 0  # No resistance signals
    
    def test_monitoring_strategy_extensive_pretreatment(self):
        """Test monitoring strategy for EXTENSIVE burden pre-treatment"""
        service = get_ca125_service()
        result = service.analyze_ca125(current_value=2842.0, treatment_ongoing=False)
        
        assert "monitoring_strategy" in result
        assert result["monitoring_strategy"]["frequency"] == "every_2_weeks"
        assert "high baseline" in result["monitoring_strategy"]["rationale"].lower()
    
    def test_monitoring_strategy_on_treatment(self):
        """Test monitoring strategy during treatment"""
        service = get_ca125_service()
        result = service.analyze_ca125(current_value=2842.0, treatment_ongoing=True)
        
        assert "monitoring_strategy" in result
        assert result["monitoring_strategy"]["frequency"] == "every_3_weeks"
        assert "response kinetics" in result["monitoring_strategy"]["rationale"].lower()
    
    def test_clinical_notes_generation(self):
        """Test clinical notes are generated and meaningful"""
        service = get_ca125_service()
        result = service.analyze_ca125(current_value=2842.0)
        
        assert "clinical_notes" in result
        assert len(result["clinical_notes"]) > 0
        assert "2842" in result["clinical_notes"]  # Includes actual value
        assert "EXTENSIVE" in result["clinical_notes"]  # Includes burden class
    
    def test_provenance_tracking(self):
        """Test provenance includes data sources and methods"""
        service = get_ca125_service()
        result = service.analyze_ca125(current_value=2842.0)
        
        assert "provenance" in result
        assert "method" in result["provenance"]
        assert "data_sources" in result["provenance"]
        assert "GOG-218" in result["provenance"]["data_sources"]
        assert "ICON7" in result["provenance"]["data_sources"]
        assert "run_id" in result["provenance"]


class TestAyeshaTrialsRouterLogic:
    """
    Test Ayesha Trials Router logic (without hitting actual API).
    
    These tests validate the filtering, boosting, and reasoning logic
    that determines which trials Ayesha should see.
    """
    
    def test_hard_filter_stage_eligible(self):
        """Test hard filter: Stage IV eligibility"""
        from api.routers.ayesha_trials import _apply_ayesha_hard_filters, AyeshaTrialSearchRequest
        
        mock_trials = [
            {
                "nct_id": "NCT001",
                "title": "Frontline trial for advanced ovarian cancer",
                "eligibility_text": "Stage III-IV ovarian cancer, first-line",
                "status": "Recruiting",
                "locations": [{"state": "NY", "city": "New York"}]
            }
        ]
        
        request = AyeshaTrialSearchRequest(
            ca125_value=2842.0,
            stage="IVB",
            treatment_line="first-line",
            germline_status="negative",
            has_ascites=True,
            has_peritoneal_disease=True
        )
        
        filtered = _apply_ayesha_hard_filters(mock_trials, request)
        
        assert len(filtered) == 1
        assert filtered[0]["hard_pass"] is True
        assert filtered[0]["hard_flags"]["stage_eligible"] is True
    
    def test_hard_filter_frontline_detection(self):
        """Test hard filter: Frontline trial detection"""
        from api.routers.ayesha_trials import _apply_ayesha_hard_filters, AyeshaTrialSearchRequest
        
        mock_trials = [
            {
                "nct_id": "NCT001",
                "title": "First-line platinum-based therapy",
                "eligibility_text": "Treatment-naive patients",
                "status": "Recruiting",
                "locations": [{"state": "NY"}]
            },
            {
                "nct_id": "NCT002",
                "title": "Second-line PARP inhibitor study",
                "eligibility_text": "Platinum-resistant recurrent disease",
                "status": "Recruiting",
                "locations": [{"state": "NY"}]
            }
        ]
        
        request = AyeshaTrialSearchRequest(
            ca125_value=2842.0,
            stage="IVB",
            treatment_line="first-line",
            germline_status="negative"
        )
        
        filtered = _apply_ayesha_hard_filters(mock_trials, request)
        
        # Should only include NCT001 (frontline)
        assert len(filtered) == 1
        assert filtered[0]["nct_id"] == "NCT001"
        assert filtered[0]["hard_flags"]["frontline_eligible"] is True
    
    def test_hard_filter_nyc_metro_location(self):
        """Test hard filter: NYC metro location (NY/NJ/CT)"""
        from api.routers.ayesha_trials import _apply_ayesha_hard_filters, AyeshaTrialSearchRequest
        
        mock_trials = [
            {
                "nct_id": "NCT001",
                "title": "Frontline trial",
                "eligibility_text": "first-line",
                "status": "Recruiting",
                "locations": [{"state": "NY", "city": "New York"}]
            },
            {
                "nct_id": "NCT002",
                "title": "Frontline trial",
                "eligibility_text": "first-line",
                "status": "Recruiting",
                "locations": [{"state": "CA", "city": "San Francisco"}]
            },
            {
                "nct_id": "NCT003",
                "title": "Frontline trial",
                "eligibility_text": "first-line",
                "status": "Recruiting",
                "locations": [{"state": "NJ", "city": "Newark"}]
            }
        ]
        
        request = AyeshaTrialSearchRequest(
            ca125_value=2842.0,
            stage="IVB",
            treatment_line="first-line",
            germline_status="negative"
        )
        
        filtered = _apply_ayesha_hard_filters(mock_trials, request)
        
        # Should only include NCT001 and NCT003 (NY/NJ)
        assert len(filtered) == 2
        assert all(t["hard_flags"]["nyc_metro"] for t in filtered)
    
    def test_soft_boost_bevacizumab_with_ascites(self):
        """Test soft boost: Bevacizumab arm gets +0.15 if ascites present"""
        from api.routers.ayesha_trials import _apply_ayesha_soft_boosts, AyeshaTrialSearchRequest
        
        mock_trials = [
            {
                "nct_id": "NCT001",
                "title": "Carboplatin + Paclitaxel + Bevacizumab",
                "eligibility_text": "first-line",
                "interventions": ["Carboplatin", "Paclitaxel", "Bevacizumab"],
                "optimization_score": 0.5,
                "hard_flags": {"frontline_eligible": True}
            },
            {
                "nct_id": "NCT002",
                "title": "Carboplatin + Paclitaxel only",
                "eligibility_text": "first-line",
                "interventions": ["Carboplatin", "Paclitaxel"],
                "optimization_score": 0.5,
                "hard_flags": {"frontline_eligible": True}
            }
        ]
        
        request = AyeshaTrialSearchRequest(
            ca125_value=2842.0,
            stage="IVB",
            treatment_line="first-line",
            germline_status="negative",
            has_ascites=True  # Ascites present
        )
        
        boosted = _apply_ayesha_soft_boosts(mock_trials, request)
        
        # NCT001 (with bevacizumab) should score higher
        nct001 = next(t for t in boosted if t["nct_id"] == "NCT001")
        nct002 = next(t for t in boosted if t["nct_id"] == "NCT002")
        
        assert nct001["match_score"] > nct002["match_score"]
        
        # Check bevacizumab boost was applied
        bev_boosts = [b for b in nct001["boosts"] if b["type"] == "bevacizumab_ascites"]
        assert len(bev_boosts) == 1
        assert bev_boosts[0]["value"] == 0.15
    
    def test_eligibility_checklist_hard_soft_split(self):
        """Test eligibility checklist: hard/soft criteria split"""
        from api.routers.ayesha_trials import _generate_eligibility_checklist, AyeshaTrialSearchRequest
        
        mock_trial = {
            "nct_id": "NCT001",
            "status": "Recruiting",
            "hard_flags": {
                "stage_eligible": True,
                "frontline_eligible": True,
                "recruiting": True,
                "nyc_metro": True
            }
        }
        
        request = AyeshaTrialSearchRequest(
            ca125_value=2842.0,
            stage="IVB",
            treatment_line="first-line",
            germline_status="negative",
            ecog_status=1  # Provided
        )
        
        checklist = _generate_eligibility_checklist(mock_trial, request)
        
        assert len(checklist["hard_criteria"]) == 4  # Stage, frontline, recruiting, location
        assert checklist["hard_pass_count"] == 4
        assert all(c["status"] == "PASS" for c in checklist["hard_criteria"])
        
        assert len(checklist["soft_criteria"]) == 4  # ECOG, age, organ, surgeries
        assert checklist["soft_pass_count"] >= 2  # ECOG and age should pass
    
    def test_confidence_gate_calculation(self):
        """Test confidence gate calculation: max(gates) with hard/soft split"""
        from api.routers.ayesha_trials import _generate_eligibility_checklist, AyeshaTrialSearchRequest
        
        mock_trial = {
            "nct_id": "NCT001",
            "status": "Recruiting",
            "hard_flags": {
                "stage_eligible": True,
                "frontline_eligible": True,
                "recruiting": True,
                "nyc_metro": True
            }
        }
        
        # Scenario 1: All hard pass, 100% soft (ECOG provided, age OK)
        request1 = AyeshaTrialSearchRequest(
            ca125_value=2842.0,
            stage="IVB",
            treatment_line="first-line",
            germline_status="negative",
            ecog_status=1
        )
        checklist1 = _generate_eligibility_checklist(mock_trial, request1)
        assert checklist1["confidence_gate"] >= 0.85  # Should be 0.85-0.90
        
        # Scenario 2: All hard pass, but ECOG unknown
        request2 = AyeshaTrialSearchRequest(
            ca125_value=2842.0,
            stage="IVB",
            treatment_line="first-line",
            germline_status="negative",
            ecog_status=None  # Unknown
        )
        checklist2 = _generate_eligibility_checklist(mock_trial, request2)
        assert checklist2["confidence_gate"] >= 0.75  # Lower due to unknowns
        assert checklist2["confidence_gate"] < 0.90


# Smoke test for full endpoint (requires running backend)
# Uncomment when backend is running
"""
@pytest.mark.asyncio
async def test_ayesha_trials_endpoint_smoke():
    '''Smoke test: Full Ayesha trials endpoint'''
    from httpx import AsyncClient
    from api.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/ayesha/trials/search", json={
            "ca125_value": 2842.0,
            "stage": "IVB",
            "treatment_line": "first-line",
            "germline_status": "negative",
            "has_ascites": True,
            "has_peritoneal_disease": True,
            "ecog_status": 1,
            "max_results": 10
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "trials" in data
        assert "soc_recommendation" in data
        assert "ca125_intelligence" in data
        assert len(data["trials"]) <= 10
        
        # Validate SOC
        soc = data["soc_recommendation"]
        assert soc["confidence"] >= 0.95
        assert "Carboplatin" in soc["regimen"]
        assert "Paclitaxel" in soc["regimen"]
        assert len(soc["add_ons"]) > 0  # Bevacizumab should be added for ascites
        
        # Validate CA-125 intelligence
        ca125 = data["ca125_intelligence"]
        assert ca125["burden_class"] == "EXTENSIVE"
        assert "forecast" in ca125
        assert "monitoring_strategy" in ca125
"""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


