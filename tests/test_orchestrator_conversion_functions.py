#!/usr/bin/env python3
"""
Test Orchestrator Conversion Functions

Tests that the _nutrition_plan_to_response and _synthetic_lethality_to_response
functions work correctly.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.routers.orchestrate import (
    _nutrition_plan_to_response,
    _synthetic_lethality_to_response
)
from api.schemas.orchestrate import (
    NutritionPlanResponse,
    SyntheticLethalityResponse
)


def test_nutrition_plan_conversion():
    """Test _nutrition_plan_to_response function."""
    print("\n" + "-"*80)
    print("TEST: _nutrition_plan_to_response Function")
    print("-"*80)
    
    # Test with dict format (as stored in PatientState)
    nutrition_dict = {
        "patient_id": "TEST-001",
        "treatment": "first-line",
        "supplements": [
            {
                "name": "Vitamin D",
                "dosage": "1000 IU",
                "timing": "daily",
                "mechanism": "immune support",
                "evidence_level": "HIGH",
                "pathway": "immune",
                "llm_rationale": "Supports immune function",
                "patient_summary": "Take daily",
                "llm_enhanced": True
            }
        ],
        "foods_to_prioritize": [
            {
                "food": "Cruciferous vegetables",
                "reason": "Supports DNA repair",
                "evidence_level": "B"
            }
        ],
        "foods_to_avoid": [
            {
                "food": "Grapefruit",
                "reason": "CYP3A4 interaction",
                "evidence_level": "A"
            }
        ],
        "drug_food_interactions": [
            {
                "drug": "olaparib",
                "food": "Grapefruit",
                "interaction_type": "CYP3A4 inhibition",
                "severity": "MODERATE",
                "management": "Avoid grapefruit"
            }
        ],
        "timing_rules": {"general": "Take with food"},
        "provenance": {"method": "NutritionAgent", "timestamp": "2025-01-28T10:00:00Z"}
    }
    
    try:
        result = _nutrition_plan_to_response(nutrition_dict)
        
        assert result is not None, "Result should not be None"
        assert isinstance(result, NutritionPlanResponse), "Result should be NutritionPlanResponse"
        assert result.patient_id == "TEST-001", "patient_id should match"
        assert result.treatment == "first-line", "treatment should match"
        assert len(result.supplements) == 1, "Should have 1 supplement"
        assert len(result.foods_to_prioritize) == 1, "Should have 1 food to prioritize"
        assert len(result.foods_to_avoid) == 1, "Should have 1 food to avoid"
        
        print("✅ _nutrition_plan_to_response works correctly with dict input")
        print(f"   patient_id: {result.patient_id}")
        print(f"   treatment: {result.treatment}")
        print(f"   supplements: {len(result.supplements)} items")
        
        # Test with None input
        result_none = _nutrition_plan_to_response(None)
        assert result_none is None, "None input should return None"
        print("✅ _nutrition_plan_to_response handles None input correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_synthetic_lethality_conversion():
    """Test _synthetic_lethality_to_response function."""
    print("\n" + "-"*80)
    print("TEST: _synthetic_lethality_to_response Function")
    print("-"*80)
    
    # Test with dict format (as stored in PatientState)
    sl_dict = {
        "patient_id": "TEST-001",
        "disease": "ovarian",
        "synthetic_lethality_detected": True,
        "double_hit_description": "BER + checkpoint loss",
        "essentiality_scores": [
            {
                "gene": "BRCA1",
                "essentiality_score": 0.75,
                "essentiality_level": "HIGH",
                "sequence_disruption": "truncating",
                "pathway_impact": "DDR NON-FUNCTIONAL",
                "functional_consequence": "loss_of_function",
                "flags": {"truncation": True, "frameshift": False},
                "confidence": 0.95
            }
        ],
        "broken_pathways": [
            {
                "pathway_name": "DNA Damage Response",
                "pathway_id": "DDR",
                "status": "NON_FUNCTIONAL",
                "genes_affected": ["BRCA1"],
                "disruption_score": 0.9,
                "description": "DDR pathway compromised"
            }
        ],
        "essential_pathways": [
            {
                "pathway_name": "Homologous Recombination",
                "pathway_id": "HRR",
                "status": "FUNCTIONAL",
                "genes_affected": [],
                "disruption_score": 0.1,
                "description": "HRR pathway intact"
            }
        ],
        "recommended_drugs": [
            {
                "drug_name": "olaparib",
                "drug_class": "PARP inhibitor",
                "rationale": "Synthetic lethal with BRCA1 loss",
                "evidence_level": "VALIDATED"
            }
        ],
        "suggested_therapy": "platinum",
        "explanation": {
            "summary": "BRCA1 loss creates synthetic lethality with PARP inhibition",
            "confidence": 0.95
        }
    }
    
    try:
        result = _synthetic_lethality_to_response(sl_dict)
        
        assert result is not None, "Result should not be None"
        assert isinstance(result, SyntheticLethalityResponse), "Result should be SyntheticLethalityResponse"
        assert result.patient_id == "TEST-001", "patient_id should match"
        assert result.disease == "ovarian", "disease should match"
        assert result.synthetic_lethality_detected == True, "synthetic_lethality_detected should be True"
        assert len(result.essentiality_scores) == 1, "Should have 1 essentiality score"
        assert len(result.broken_pathways) == 1, "Should have 1 broken pathway"
        assert len(result.recommended_drugs) == 1, "Should have 1 recommended drug"
        
        print("✅ _synthetic_lethality_to_response works correctly with dict input")
        print(f"   patient_id: {result.patient_id}")
        print(f"   disease: {result.disease}")
        print(f"   synthetic_lethality_detected: {result.synthetic_lethality_detected}")
        print(f"   essentiality_scores: {len(result.essentiality_scores)} items")
        
        # Test with None input
        result_none = _synthetic_lethality_to_response(None)
        assert result_none is None, "None input should return None"
        print("✅ _synthetic_lethality_to_response handles None input correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 Testing Orchestrator Conversion Functions")
    print("   This test verifies that the conversion functions work correctly.")
    print("="*80)
    
    results = []
    
    results.append(("_nutrition_plan_to_response", test_nutrition_plan_conversion()))
    results.append(("_synthetic_lethality_to_response", test_synthetic_lethality_conversion()))
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    print(f"\n   Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL CONVERSION FUNCTION TESTS PASSED")
        print("   The conversion functions are working correctly.")
    else:
        print("\n❌ SOME CONVERSION FUNCTION TESTS FAILED")
        print("   Please check the errors above.")
    
    sys.exit(0 if passed == total else 1)

