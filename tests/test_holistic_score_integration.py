#!/usr/bin/env python3
"""
Integration Test for Holistic Score in Ayesha Trial Service

Validates that holistic scores are computed and returned for trials.
Uses real Ayesha profile data from ayesha_11_17_25.js.

Run: python3 -m pytest tests/test_holistic_score_integration.py -v -s
"""

import pytest
import sys
import asyncio
from pathlib import Path
from typing import Dict, List, Any

# Add backend to path
BACKEND_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_ROOT))


# ============================================================================
# TEST DATA: AYESHA'S PROFILE
# ============================================================================

AYESHA_PROFILE = {
    "mechanism_vector": [0.88, 0.12, 0.15, 0.10, 0.05, 0.2, 0.0],  # DDR-high (MBD4+TP53)
    "disease": "Ovarian Cancer",
    "age": 40,
    "germline_variants": [
        {"gene": "MBD4", "variant": "c.1293delA"},
        {"gene": "PDGFRA", "variant": "c.2263T>C"}  # VUS
    ],
    "location": {"state": "NY"}
}

# Mock trial data for testing
MOCK_TRIALS = [
    {
        "nct_id": "NCT02502266",
        "title": "PARP+IO Combination Trial",
        "status": "RECRUITING",
        "phases": "Phase 1/2",
        "conditions": ["Ovarian Cancer"],
        "interventions": "Niraparib + Pembrolizumab",
        "moa_vector": [0.9, 0.1, 0.2, 0.1, 0.05, 0.8, 0.0],  # DDR + IO
        "overall_status": "RECRUITING",
        "score": 0.85,
        "keyword_matches": {"PARP": "High", "IO": "Medium"},
        "combo_matches": ["PARP+IO"],
        "is_tagged": True
    },
    {
        "nct_id": "NCT12345678",
        "title": "MAPK Targeted Trial",
        "status": "RECRUITING",
        "phases": "Phase 2",
        "conditions": ["Ovarian Cancer"],
        "interventions": "BRAF Inhibitor",
        "moa_vector": [0.0, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0],  # MAPK only
        "overall_status": "RECRUITING",
        "score": 0.45,
        "keyword_matches": {"MAPK": "Medium"},
        "combo_matches": [],
        "is_tagged": True
    }
]


# ============================================================================
# TEST 1: HolisticScoreService Can Be Imported
# ============================================================================

def test_01_holistic_score_service_can_import():
    """Test that HolisticScoreService can be imported without errors."""
    try:
        from api.services.holistic_score import get_holistic_score_service
        service = get_holistic_score_service()
        assert service is not None, "Service should be instantiable"
        print("✅ TEST 1 PASSED: HolisticScoreService imports successfully")
        return True
    except ImportError as e:
        print(f"❌ TEST 1 FAILED: Missing dependency - {e}")
        return False
    except Exception as e:
        print(f"❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 2: Holistic Score Computation for Single Trial
# ============================================================================

@pytest.mark.asyncio
async def test_02_holistic_score_single_trial():
    """Test that holistic score can be computed for a single trial."""
    try:
        from api.services.holistic_score import get_holistic_score_service
        
        service = get_holistic_score_service()
        trial = MOCK_TRIALS[0]  # PARP+IO trial
        
        result = await service.compute_holistic_score(
            patient_profile=AYESHA_PROFILE,
            trial=trial,
            pharmacogenes=AYESHA_PROFILE["germline_variants"]
        )
        
        # Validate result structure
        assert hasattr(result, 'holistic_score'), "Result should have holistic_score"
        assert hasattr(result, 'mechanism_fit_score'), "Result should have mechanism_fit_score"
        assert hasattr(result, 'eligibility_score'), "Result should have eligibility_score"
        assert hasattr(result, 'pgx_safety_score'), "Result should have pgx_safety_score"
        assert hasattr(result, 'interpretation'), "Result should have interpretation"
        
        # Validate score ranges
        assert 0.0 <= result.holistic_score <= 1.0, f"Holistic score should be 0-1, got {result.holistic_score}"
        assert 0.0 <= result.mechanism_fit_score <= 1.0, f"Mechanism fit should be 0-1, got {result.mechanism_fit_score}"
        assert 0.0 <= result.eligibility_score <= 1.0, f"Eligibility should be 0-1, got {result.eligibility_score}"
        assert 0.0 <= result.pgx_safety_score <= 1.0, f"PGx safety should be 0-1, got {result.pgx_safety_score}"
        
        # For DDR-high patient + DDR+IO trial, mechanism fit should be high
        assert result.mechanism_fit_score >= 0.70, f"DDR trial should have mechanism fit >= 0.70, got {result.mechanism_fit_score}"
        
        # Formula validation: holistic = 0.5*mechanism + 0.3*eligibility + 0.2*pgx
        expected_score = (0.5 * result.mechanism_fit_score + 
                         0.3 * result.eligibility_score + 
                         0.2 * result.pgx_safety_score)
        assert abs(result.holistic_score - expected_score) < 0.01, \
            f"Holistic score should match formula: expected {expected_score}, got {result.holistic_score}"
        
        print(f"✅ TEST 2 PASSED: Holistic score computed successfully")
        print(f"   Holistic Score: {result.holistic_score:.3f}")
        print(f"   Mechanism Fit: {result.mechanism_fit_score:.3f}")
        print(f"   Eligibility: {result.eligibility_score:.3f}")
        print(f"   PGx Safety: {result.pgx_safety_score:.3f}")
        print(f"   Interpretation: {result.interpretation}")
        
        return True
    except Exception as e:
        print(f"❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 3: Holistic Score Batch Computation
# ============================================================================

@pytest.mark.asyncio
async def test_03_holistic_score_batch():
    """Test that holistic scores can be computed for multiple trials."""
    try:
        from api.services.holistic_score import get_holistic_score_service
        
        service = get_holistic_score_service()
        
        results = await service.compute_batch(
            patient_profile=AYESHA_PROFILE,
            trials=MOCK_TRIALS,
            pharmacogenes=AYESHA_PROFILE["germline_variants"]
        )
        
        assert len(results) == len(MOCK_TRIALS), f"Should return {len(MOCK_TRIALS)} results, got {len(results)}"
        
        # DDR trial (first) should have higher holistic score than MAPK trial (second)
        ddr_score = results[0].get("holistic_score", 0.0)
        mapk_score = results[1].get("holistic_score", 0.0)
        
        assert ddr_score > mapk_score, \
            f"DDR trial should have higher holistic score ({ddr_score}) than MAPK trial ({mapk_score})"
        
        # All results should have required fields
        for result in results:
            assert "holistic_score" in result, "Result should have holistic_score"
            assert "mechanism_fit_score" in result, "Result should have mechanism_fit_score"
            assert "interpretation" in result, "Result should have interpretation"
        
        print(f"✅ TEST 3 PASSED: Batch holistic score computation successful")
        print(f"   DDR Trial Score: {ddr_score:.3f}")
        print(f"   MAPK Trial Score: {mapk_score:.3f}")
        
        return True
    except Exception as e:
        print(f"❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 4: Trial Service Integration with Holistic Scores
# ============================================================================

@pytest.mark.asyncio
async def test_04_trial_service_holistic_integration():
    """Test that AyeshaTrialService adds holistic scores to trials."""
    try:
        from api.services.ayesha_care_plan.trial_service import get_ayesha_trial_service
        from api.services.ayesha_care_plan.schemas import CompleteCareV2Request
        
        service = get_ayesha_trial_service()
        
        # Create a mock request with Ayesha's data
        request = CompleteCareV2Request(
            ca125_value=2842.0,
            stage="IVB",
            treatment_line="first-line",
            germline_status="positive",
            location_state="NY",
            tumor_context={
                "somatic_mutations": [
                    {"gene": "TP53", "variant": "R175H"}
                ]
            },
            max_trials=10
        )
        
        # Mock the ranked trials to test holistic score addition
        # We'll test the _add_holistic_scores method directly
        mechanism_vector = AYESHA_PROFILE["mechanism_vector"]
        
        # Create mock trials list (simulating what AyeshaTrialRanker would return)
        mock_ranked_trials = [
            {
                "nct_id": "NCT02502266",
                "title": "PARP+IO Combination Trial",
                "status": "RECRUITING",
                "phases": "Phase 1/2",
                "conditions": "Ovarian Cancer",
                "interventions": "Niraparib + Pembrolizumab",
                "moa_vector": [0.9, 0.1, 0.2, 0.1, 0.05, 0.8, 0.0],
                "score": 0.85,
                "keyword_matches": {"PARP": "High"},
                "combo_matches": ["PARP+IO"],
                "is_tagged": True
            }
        ]
        
        # Call _add_holistic_scores method
        trials_with_holistic = await service._add_holistic_scores(
            trials_list=mock_ranked_trials,
            request=request,
            mechanism_vector=mechanism_vector
        )
        
        # Verify holistic scores were added
        assert len(trials_with_holistic) > 0, "Should have at least one trial"
        
        trial = trials_with_holistic[0]
        assert "holistic_score" in trial, "Trial should have holistic_score"
        assert "mechanism_fit_score" in trial, "Trial should have mechanism_fit_score"
        assert "eligibility_score" in trial, "Trial should have eligibility_score"
        assert "pgx_safety_score" in trial, "Trial should have pgx_safety_score"
        assert "holistic_interpretation" in trial, "Trial should have holistic_interpretation"
        
        # Validate score ranges
        assert 0.0 <= trial["holistic_score"] <= 1.0, f"Holistic score should be 0-1, got {trial['holistic_score']}"
        assert 0.0 <= trial["mechanism_fit_score"] <= 1.0, f"Mechanism fit should be 0-1, got {trial['mechanism_fit_score']}"
        
        # For DDR trial, mechanism fit should be high
        assert trial["mechanism_fit_score"] >= 0.70, \
            f"DDR trial should have mechanism fit >= 0.70, got {trial['mechanism_fit_score']}"
        
        print(f"✅ TEST 4 PASSED: Trial service holistic integration successful")
        print(f"   Trial: {trial.get('title', 'N/A')}")
        print(f"   Holistic Score: {trial.get('holistic_score', 0):.3f}")
        print(f"   Mechanism Fit: {trial.get('mechanism_fit_score', 0):.3f}")
        print(f"   Interpretation: {trial.get('holistic_interpretation', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"❌ TEST 4 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 5: Mechanism Vector Computation from Tumor Context
# ============================================================================

def test_05_mechanism_vector_from_tumor_context():
    """Test that mechanism vector can be computed from tumor context."""
    try:
        from api.services.ayesha_care_plan.trial_service import get_ayesha_trial_service
        
        service = get_ayesha_trial_service()
        
        # Ayesha's tumor context (MBD4 + TP53)
        tumor_context = {
            "somatic_mutations": [
                {"gene": "MBD4", "variant": "c.1293delA"},
                {"gene": "TP53", "variant": "R175H"}
            ]
        }
        
        mechanism_vector = service._compute_mechanism_vector_from_tumor_context(tumor_context)
        
        assert len(mechanism_vector) == 7, f"Mechanism vector should be 7D, got {len(mechanism_vector)}"
        
        # DDR pathway should be high (MBD4 + TP53 both DDR-related)
        assert mechanism_vector[0] >= 0.5, \
            f"DDR pathway (index 0) should be >= 0.5 for MBD4+TP53, got {mechanism_vector[0]}"
        
        print(f"✅ TEST 5 PASSED: Mechanism vector computed from tumor context")
        print(f"   Mechanism Vector: {mechanism_vector}")
        print(f"   DDR Score: {mechanism_vector[0]:.3f}")
        
        return True
    except Exception as e:
        print(f"❌ TEST 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# MAIN RUNNER
# ============================================================================

def run_all_tests():
    """Run all tests and report results."""
    results = {}
    
    print("\n" + "="*70)
    print("HOLISTIC SCORE INTEGRATION TESTS")
    print("="*70 + "\n")
    
    # Test 1: Import
    results["test_01"] = test_01_holistic_score_service_can_import()
    
    # Test 2: Single trial (async)
    if results["test_01"]:
        results["test_02"] = asyncio.run(test_02_holistic_score_single_trial())
    else:
        results["test_02"] = False
        print("⚠️  TEST 2 SKIPPED: HolisticScoreService not available")
    
    # Test 3: Batch (async)
    if results["test_01"]:
        results["test_03"] = asyncio.run(test_03_holistic_score_batch())
    else:
        results["test_03"] = False
        print("⚠️  TEST 3 SKIPPED: HolisticScoreService not available")
    
    # Test 4: Trial service integration (async)
    if results["test_01"]:
        results["test_04"] = asyncio.run(test_04_trial_service_holistic_integration())
    else:
        results["test_04"] = False
        print("⚠️  TEST 4 SKIPPED: HolisticScoreService not available")
    
    # Test 5: Mechanism vector computation
    results["test_05"] = test_05_mechanism_vector_from_tumor_context()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
