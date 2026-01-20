#!/usr/bin/env python3
"""
Test Both Orchestrators Comparison

Validates that both orchestrator endpoints exist and can handle requests.
This test does NOT require a running server - it validates schemas and imports.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_both_orchestrators_exist():
    """Test that both orchestrator endpoints can be imported."""
    print("\n" + "="*80)
    print("TEST: Both Orchestrator Endpoints Exist")
    print("="*80)
    
    try:
        # Test legacy endpoint
        from api.routers.complete_care_universal import (
            router as legacy_router,
            CompleteCareUniversalRequest,
            CompleteCareUniversalResponse,
            get_complete_care_v2
        )
        print("✅ Legacy endpoint (`/api/complete_care/v2`) imports successfully")
        print(f"   - Router: {legacy_router}")
        print(f"   - Request Schema: CompleteCareUniversalRequest")
        print(f"   - Response Schema: CompleteCareUniversalResponse")
        print(f"   - Handler: get_complete_care_v2")
        
        # Test new endpoint
        from api.routers.orchestrate import (
            router as new_router,
            OrchestratePipelineRequest,
            OrchestratePipelineResponse,
            run_full_pipeline
        )
        print("\n✅ New endpoint (`/api/orchestrate/full`) imports successfully")
        print(f"   - Router: {new_router}")
        print(f"   - Request Schema: OrchestratePipelineRequest")
        print(f"   - Response Schema: OrchestratePipelineResponse")
        print(f"   - Handler: run_full_pipeline")
        
        # Test that new endpoint includes nutrition_plan and synthetic_lethality_result
        from api.schemas.orchestrate import (
            NutritionPlanResponse,
            SyntheticLethalityResponse
        )
        print("\n✅ New endpoint includes required fields:")
        print(f"   - NutritionPlanResponse schema exists")
        print(f"   - SyntheticLethalityResponse schema exists")
        
        # Verify response schema includes these fields
        response_fields = OrchestratePipelineResponse.model_fields.keys()
        has_nutrition = 'nutrition_plan' in response_fields
        has_synthetic = 'synthetic_lethality_result' in response_fields
        
        print(f"\n✅ OrchestratePipelineResponse fields:")
        print(f"   - nutrition_plan: {'✅' if has_nutrition else '❌'}")
        print(f"   - synthetic_lethality_result: {'✅' if has_synthetic else '❌'}")
        
        if not has_nutrition or not has_synthetic:
            print("\n❌ ERROR: Required fields missing from OrchestratePipelineResponse")
            return False
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED")
        print("="*80)
        print("\n📋 RECOMMENDATION:")
        print("   - Keep both endpoints operational")
        print("   - Migrate UniversalCompleteCare.jsx to use /api/orchestrate/full")
        print("   - Use orchestratorMapper.js for data transformation")
        print("   - Deprecate /api/complete_care/v2 after migration complete")
        
        return True
        
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_both_orchestrators_exist()
    sys.exit(0 if success else 1)
