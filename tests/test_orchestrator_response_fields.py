#!/usr/bin/env python3
"""
Test Orchestrator API Response Fields

Tests that the /api/orchestrate/full endpoint includes nutrition_plan and synthetic_lethality_result
in the response, as per the recent backend fix.
"""

import asyncio
import httpx
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = "http://localhost:8000"


async def test_orchestrator_response_fields():
    """Test that orchestrator response includes nutrition_plan and synthetic_lethality_result."""
    
    print("\n" + "="*80)
    print("TEST: Orchestrator API Response Fields")
    print("="*80)
    
    # Test request with BRCA1+TP53 mutations (should trigger nutrition and SL agents)
    request_payload = {
        "disease": "ovarian",
        "mutations": [
            {
                "gene": "BRCA1",
                "hgvs_p": "p.Arg1835Ter",
                "hgvs_c": "c.5503C>T",
                "chrom": "17",
                "pos": 43044295,
                "ref": "C",
                "alt": "T",
                "consequence": "stop_gained"
            },
            {
                "gene": "TP53",
                "hgvs_p": "p.Arg175His",
                "hgvs_c": "c.524G>A",
                "chrom": "17",
                "pos": 7673802,
                "ref": "G",
                "alt": "A",
                "consequence": "missense_variant"
            }
        ],
        "treatment_line": 1,
        "prior_therapies": []
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            print(f"\n📤 Sending request to {API_BASE}/api/orchestrate/full")
            print(f"   Disease: {request_payload['disease']}")
            print(f"   Mutations: {len(request_payload['mutations'])}")
            
            response = await client.post(
                f"{API_BASE}/api/orchestrate/full",
                json=request_payload
            )
            
            print(f"\n📥 Response Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ ERROR: {response.status_code}")
                print(f"   {response.text}")
                return False
            
            data = response.json()
            
            # Test 1: Check response structure
            print("\n" + "-"*80)
            print("TEST 1: Response Structure")
            print("-"*80)
            
            required_fields = [
                "patient_id",
                "disease",
                "phase",
                "progress_percent",
                "completed_agents",
                "biomarker_profile",
                "resistance_prediction",
                "drug_ranking",
                "trial_matches",
                "care_plan"
            ]
            
            missing_fields = []
            for field in required_fields:
                if field not in data:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"❌ Missing required fields: {missing_fields}")
                return False
            else:
                print("✅ All required fields present")
            
            # Test 2: Check nutrition_plan field exists
            print("\n" + "-"*80)
            print("TEST 2: nutrition_plan Field")
            print("-"*80)
            
            if "nutrition_plan" not in data:
                print("❌ nutrition_plan field is MISSING from response")
                print(f"   Available fields: {list(data.keys())}")
                return False
            else:
                print("✅ nutrition_plan field exists in response")
                
                if data["nutrition_plan"] is None:
                    print("⚠️  nutrition_plan is None (agent may have been skipped)")
                else:
                    nutrition = data["nutrition_plan"]
                    print(f"   patient_id: {nutrition.get('patient_id', 'N/A')}")
                    print(f"   treatment: {nutrition.get('treatment', 'N/A')}")
                    print(f"   supplements: {len(nutrition.get('supplements', []))} items")
                    print(f"   foods_to_prioritize: {len(nutrition.get('foods_to_prioritize', []))} items")
                    print(f"   foods_to_avoid: {len(nutrition.get('foods_to_avoid', []))} items")
                    print(f"   drug_food_interactions: {len(nutrition.get('drug_food_interactions', []))} items")
            
            # Test 3: Check synthetic_lethality_result field exists
            print("\n" + "-"*80)
            print("TEST 3: synthetic_lethality_result Field")
            print("-"*80)
            
            if "synthetic_lethality_result" not in data:
                print("❌ synthetic_lethality_result field is MISSING from response")
                print(f"   Available fields: {list(data.keys())}")
                return False
            else:
                print("✅ synthetic_lethality_result field exists in response")
                
                if data["synthetic_lethality_result"] is None:
                    print("⚠️  synthetic_lethality_result is None (agent may have been skipped)")
                else:
                    sl_result = data["synthetic_lethality_result"]
                    print(f"   patient_id: {sl_result.get('patient_id', 'N/A')}")
                    print(f"   disease: {sl_result.get('disease', 'N/A')}")
                    print(f"   synthetic_lethality_detected: {sl_result.get('synthetic_lethality_detected', False)}")
                    print(f"   essentiality_scores: {len(sl_result.get('essentiality_scores', []))} items")
                    print(f"   broken_pathways: {len(sl_result.get('broken_pathways', []))} items")
                    print(f"   recommended_drugs: {len(sl_result.get('recommended_drugs', []))} items")
                    print(f"   suggested_therapy: {sl_result.get('suggested_therapy', 'N/A')}")
            
            # Test 4: Verify response schema compatibility
            print("\n" + "-"*80)
            print("TEST 4: Response Schema Validation")
            print("-"*80)
            
            # Check that nutrition_plan has expected structure
            if data.get("nutrition_plan"):
                nutrition = data["nutrition_plan"]
                expected_nutrition_fields = [
                    "patient_id", "treatment", "supplements", 
                    "foods_to_prioritize", "foods_to_avoid", 
                    "drug_food_interactions", "timing_rules", "provenance"
                ]
                missing_nutrition_fields = [f for f in expected_nutrition_fields if f not in nutrition]
                if missing_nutrition_fields:
                    print(f"⚠️  nutrition_plan missing fields: {missing_nutrition_fields}")
                else:
                    print("✅ nutrition_plan has correct structure")
            
            # Check that synthetic_lethality_result has expected structure
            if data.get("synthetic_lethality_result"):
                sl_result = data["synthetic_lethality_result"]
                expected_sl_fields = [
                    "disease", "synthetic_lethality_detected", 
                    "essentiality_scores", "broken_pathways",
                    "essential_pathways", "recommended_drugs", "suggested_therapy"
                ]
                missing_sl_fields = [f for f in expected_sl_fields if f not in sl_result]
                if missing_sl_fields:
                    print(f"⚠️  synthetic_lethality_result missing fields: {missing_sl_fields}")
                else:
                    print("✅ synthetic_lethality_result has correct structure")
            
            # Test 5: Check completed agents
            print("\n" + "-"*80)
            print("TEST 5: Completed Agents")
            print("-"*80)
            
            completed_agents = data.get("completed_agents", [])
            print(f"   Completed agents: {completed_agents}")
            
            if "nutrition" in completed_agents:
                print("✅ nutrition agent completed")
            else:
                print("⚠️  nutrition agent not in completed_agents list")
            
            if "synthetic_lethality" in completed_agents:
                print("✅ synthetic_lethality agent completed")
            else:
                print("⚠️  synthetic_lethality agent not in completed_agents list")
            
            # Summary
            print("\n" + "="*80)
            print("TEST SUMMARY")
            print("="*80)
            
            all_tests_passed = (
                "nutrition_plan" in data and
                "synthetic_lethality_result" in data
            )
            
            if all_tests_passed:
                print("✅ ALL TESTS PASSED")
                print("\n   The orchestrator API response now includes:")
                print("   - nutrition_plan field")
                print("   - synthetic_lethality_result field")
                return True
            else:
                print("❌ SOME TESTS FAILED")
                return False
            
    except httpx.ConnectError:
        print(f"\n❌ ERROR: Could not connect to {API_BASE}")
        print("   Make sure the backend server is running:")
        print("   cd oncology-coPilot/oncology-backend-minimal")
        print("   uvicorn main:app --reload --port 8000")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🧪 Testing Orchestrator API Response Fields")
    print("   This test verifies that nutrition_plan and synthetic_lethality_result")
    print("   are included in the /api/orchestrate/full response.\n")
    
    result = asyncio.run(test_orchestrator_response_fields())
    
    sys.exit(0 if result else 1)

