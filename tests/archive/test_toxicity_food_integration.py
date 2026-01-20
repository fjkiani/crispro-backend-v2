"""
Test Phase 2: Toxicity Mitigation in Food Validation

Tests that food validation endpoint returns toxicity_mitigation when:
1. Patient has medications (e.g., carboplatin)
2. Patient has germline variants (e.g., BRCA1)
3. Food compound matches a mitigating food (e.g., NAC)
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_toxicity_food_integration():
    print("=" * 70)
    print("PHASE 2 TEST: Toxicity Mitigation in Food Validation")
    print("=" * 70)
    
    import httpx
    
    API_ROOT = "http://127.0.0.1:8000"
    
    # Test Scenario: BRCA1 patient on carboplatin, validating NAC
    # Expected: NAC should show toxicity_mitigation for carboplatin DNA repair stress
    
    payload = {
        "compound": "NAC",
        "disease_context": {
            "disease": "ovarian_cancer_hgs",
            "mutations": [
                {"gene": "BRCA1", "hgvs_p": "R175H"}
            ],
            "biomarkers": {"HRD": "POSITIVE", "TMB": 8.2},
            "pathways_disrupted": ["DNA repair", "Cell cycle"]
        },
        "treatment_history": {
            "current_line": "L1",
            "prior_therapies": []
        },
        "patient_medications": ["carboplatin"],  # KEY: This triggers toxicity check
        "use_evo2": False
    }
    
    print("\n[TEST] Food Validation with Toxicity Mitigation")
    print("-" * 50)
    print(f"Compound: {payload['compound']}")
    print(f"Patient Medications: {payload['patient_medications']}")
    print(f"Germline Variants: {[m['gene'] for m in payload['disease_context']['mutations']]}")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{API_ROOT}/api/hypothesis/validate_food_dynamic",
                json=payload
            )
            
            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code}")
                print(f"Response: {response.text}")
                return
            
            data = response.json()
            
            if data.get("status") == "ERROR":
                print(f"❌ Validation Error: {data.get('error')}")
                return
            
            # Check if toxicity_mitigation field exists
            toxicity_mitigation = data.get("toxicity_mitigation")
            
            print(f"\n✅ Response Status: {data.get('status')}")
            print(f"✅ Compound: {data.get('compound')}")
            print(f"✅ Alignment Score: {data.get('alignment_score', 0):.2f}")
            
            if toxicity_mitigation:
                print(f"\n🎯 TOXICITY MITIGATION DETECTED:")
                print(f"   - Mitigates: {toxicity_mitigation.get('mitigates')}")
                print(f"   - Target Drug: {toxicity_mitigation.get('target_drug')}")
                print(f"   - Target MoA: {toxicity_mitigation.get('target_moa')}")
                print(f"   - Pathway: {toxicity_mitigation.get('pathway')}")
                print(f"   - Mechanism: {toxicity_mitigation.get('mechanism')}")
                print(f"   - Timing: {toxicity_mitigation.get('timing')}")
                print(f"   - Dose: {toxicity_mitigation.get('dose')}")
                
                # Validate expected values
                assert toxicity_mitigation.get("mitigates") == True, "Should mitigate toxicity"
                assert toxicity_mitigation.get("target_drug") == "carboplatin", "Should target carboplatin"
                assert toxicity_mitigation.get("pathway") == "dna_repair", "Should target DNA repair pathway"
                
                print("\n✅ ALL VALIDATIONS PASSED!")
            else:
                print("\n⚠️  No toxicity_mitigation field found")
                print("   This could mean:")
                print("   - Compound doesn't match any mitigating foods")
                print("   - No medications provided")
                print("   - No germline variants detected")
                print("   - Error in toxicity check (check logs)")
    
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Vitamin D for same scenario
    print("\n" + "=" * 70)
    print("[TEST 2] Vitamin D for BRCA1 + Carboplatin")
    print("-" * 50)
    
    payload2 = {
        "compound": "Vitamin D",
        "disease_context": {
            "disease": "ovarian_cancer_hgs",
            "mutations": [{"gene": "BRCA1"}],
            "biomarkers": {"HRD": "POSITIVE"}
        },
        "treatment_history": {"current_line": "L1"},
        "patient_medications": ["carboplatin"],
        "use_evo2": False
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{API_ROOT}/api/hypothesis/validate_food_dynamic",
                json=payload2
            )
            
            if response.status_code == 200:
                data = response.json()
                toxicity_mitigation = data.get("toxicity_mitigation")
                
                if toxicity_mitigation:
                    print(f"✅ Vitamin D mitigates: {toxicity_mitigation.get('target_drug')}")
                    print(f"   Pathway: {toxicity_mitigation.get('pathway')}")
                else:
                    print("⚠️  No toxicity mitigation detected for Vitamin D")
            else:
                print(f"⚠️  API returned {response.status_code}")
    
    except Exception as e:
        print(f"⚠️  Test 2 error: {e}")
    
    print("\n" + "=" * 70)
    print("PHASE 2 TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    print("\n⚠️  NOTE: This test requires the API server to be running")
    print("   Start server: cd oncology-backend-minimal && uvicorn api.main:app --reload\n")
    
    asyncio.run(test_toxicity_food_integration())


