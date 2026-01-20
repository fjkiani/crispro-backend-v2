#!/usr/bin/env python3
"""
Test Orchestrator Schema Validation

Tests that the OrchestratePipelineResponse schema includes nutrition_plan and synthetic_lethality_result
without requiring a running server.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.schemas.orchestrate import (
    OrchestratePipelineResponse,
    NutritionPlanResponse,
    SyntheticLethalityResponse,
    PipelinePhase
)


def test_nutrition_plan_response_schema():
    """Test that NutritionPlanResponse schema exists and is valid."""
    print("\n" + "-"*80)
    print("TEST: NutritionPlanResponse Schema")
    print("-"*80)
    
    try:
        # Create a sample nutrition plan response
        nutrition_plan = NutritionPlanResponse(
            patient_id="TEST-001",
            treatment="first-line",
            supplements=[
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
            foods_to_prioritize=[
                {
                    "food": "Cruciferous vegetables",
                    "reason": "Supports DNA repair",
                    "evidence_level": "B"
                }
            ],
            foods_to_avoid=[
                {
                    "food": "Grapefruit",
                    "reason": "CYP3A4 interaction",
                    "evidence_level": "A"
                }
            ],
            drug_food_interactions=[
                {
                    "drug": "olaparib",
                    "food": "Grapefruit",
                    "interaction_type": "CYP3A4 inhibition",
                    "severity": "MODERATE",
                    "management": "Avoid grapefruit"
                }
            ],
            timing_rules={"general": "Take with food"},
            provenance={"method": "NutritionAgent", "timestamp": "2025-01-28T10:00:00Z"}
        )
        
        print("✅ NutritionPlanResponse schema is valid")
        print(f"   patient_id: {nutrition_plan.patient_id}")
        print(f"   treatment: {nutrition_plan.treatment}")
        print(f"   supplements: {len(nutrition_plan.supplements)} items")
        print(f"   foods_to_prioritize: {len(nutrition_plan.foods_to_prioritize)} items")
        print(f"   foods_to_avoid: {len(nutrition_plan.foods_to_avoid)} items")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_synthetic_lethality_response_schema():
    """Test that SyntheticLethalityResponse schema exists and is valid."""
    print("\n" + "-"*80)
    print("TEST: SyntheticLethalityResponse Schema")
    print("-"*80)
    
    try:
        # Create a sample synthetic lethality response
        sl_result = SyntheticLethalityResponse(
            patient_id="TEST-001",
            disease="ovarian",
            synthetic_lethality_detected=True,
            double_hit_description="BER + checkpoint loss",
            essentiality_scores=[
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
            broken_pathways=[
                {
                    "pathway_name": "DNA Damage Response",
                    "pathway_id": "DDR",
                    "status": "NON_FUNCTIONAL",
                    "genes_affected": ["BRCA1"],
                    "disruption_score": 0.9,
                    "description": "DDR pathway compromised"
                }
            ],
            essential_pathways=[
                {
                    "pathway_name": "Homologous Recombination",
                    "pathway_id": "HRR",
                    "status": "FUNCTIONAL",
                    "genes_affected": [],
                    "disruption_score": 0.1,
                    "description": "HRR pathway intact"
                }
            ],
            recommended_drugs=[
                {
                    "drug_name": "olaparib",
                    "drug_class": "PARP inhibitor",
                    "rationale": "Synthetic lethal with BRCA1 loss",
                    "evidence_level": "VALIDATED"
                }
            ],
            suggested_therapy="platinum",
            explanation={
                "summary": "BRCA1 loss creates synthetic lethality with PARP inhibition",
                "confidence": 0.95
            }
        )
        
        print("✅ SyntheticLethalityResponse schema is valid")
        print(f"   patient_id: {sl_result.patient_id}")
        print(f"   disease: {sl_result.disease}")
        print(f"   synthetic_lethality_detected: {sl_result.synthetic_lethality_detected}")
        print(f"   essentiality_scores: {len(sl_result.essentiality_scores)} items")
        print(f"   broken_pathways: {len(sl_result.broken_pathways)} items")
        print(f"   recommended_drugs: {len(sl_result.recommended_drugs)} items")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_orchestrate_pipeline_response_schema():
    """Test that OrchestratePipelineResponse includes the new fields."""
    print("\n" + "-"*80)
    print("TEST: OrchestratePipelineResponse Schema (with new fields)")
    print("-"*80)
    
    try:
        # Create a sample response with nutrition_plan and synthetic_lethality_result
        nutrition_plan = NutritionPlanResponse(
            patient_id="TEST-001",
            treatment="first-line",
            supplements=[],
            foods_to_prioritize=[],
            foods_to_avoid=[],
            drug_food_interactions=[],
            timing_rules={},
            provenance={}
        )
        
        sl_result = SyntheticLethalityResponse(
            patient_id="TEST-001",
            disease="ovarian",
            synthetic_lethality_detected=False,
            double_hit_description=None,
            essentiality_scores=[],
            broken_pathways=[],
            essential_pathways=[],
            recommended_drugs=[],
            suggested_therapy="platinum"
        )
        
        response = OrchestratePipelineResponse(
            patient_id="TEST-001",
            disease="ovarian",
            phase=PipelinePhase.COMPLETE,
            progress_percent=100,
            completed_agents=["biomarker", "resistance", "drug_efficacy", "trial_matching", "nutrition", "synthetic_lethality"],
            created_at="2025-01-28T10:00:00Z",
            updated_at="2025-01-28T10:01:30Z",
            duration_ms=90000,
            mutation_count=2,
            mechanism_vector=[0.8, 0.1, 0.1, 0.0, 0.0, 0.0, 0.0],
            biomarker_profile=None,
            resistance_prediction=None,
            drug_ranking=None,
            trial_matches=None,
            care_plan=None,
            nutrition_plan=nutrition_plan,
            synthetic_lethality_result=sl_result,
            data_quality_flags=[],
            alerts=[]
        )
        
        print("✅ OrchestratePipelineResponse schema is valid with new fields")
        print(f"   nutrition_plan: {'present' if response.nutrition_plan else 'None'}")
        print(f"   synthetic_lethality_result: {'present' if response.synthetic_lethality_result else 'None'}")
        
        # Verify fields are accessible
        assert hasattr(response, 'nutrition_plan'), "nutrition_plan field should exist"
        assert hasattr(response, 'synthetic_lethality_result'), "synthetic_lethality_result field should exist"
        
        print("✅ Both new fields are accessible in the response")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_schema_imports():
    """Test that all required schemas can be imported."""
    print("\n" + "-"*80)
    print("TEST: Schema Imports")
    print("-"*80)
    
    try:
        from api.schemas.orchestrate import (
            OrchestratePipelineResponse,
            NutritionPlanResponse,
            SyntheticLethalityResponse
        )
        
        print("✅ All schemas imported successfully")
        print("   - OrchestratePipelineResponse")
        print("   - NutritionPlanResponse")
        print("   - SyntheticLethalityResponse")
        return True
        
    except ImportError as e:
        print(f"❌ IMPORT ERROR: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 Testing Orchestrator Schema Validation")
    print("   This test verifies that the schemas include nutrition_plan and")
    print("   synthetic_lethality_result fields without requiring a running server.")
    print("="*80)
    
    results = []
    
    results.append(("Schema Imports", test_schema_imports()))
    results.append(("NutritionPlanResponse Schema", test_nutrition_plan_response_schema()))
    results.append(("SyntheticLethalityResponse Schema", test_synthetic_lethality_response_schema()))
    results.append(("OrchestratePipelineResponse with new fields", test_orchestrate_pipeline_response_schema()))
    
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
        print("\n✅ ALL SCHEMA TESTS PASSED")
        print("   The backend schemas are correctly configured with the new fields.")
    else:
        print("\n❌ SOME SCHEMA TESTS FAILED")
        print("   Please check the errors above.")
    
    sys.exit(0 if passed == total else 1)

