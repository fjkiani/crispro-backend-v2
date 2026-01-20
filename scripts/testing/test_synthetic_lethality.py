#!/usr/bin/env python3
"""
🔬 SYNTHETIC LETHALITY DETECTIVE - Backend Smoke Test

Tests the /api/guidance/synthetic_lethality endpoint with BRCA1/BRCA2 mutations
to demonstrate the complete S/P/E framework solving Dr. Lustberg's use case.
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx

API_ROOT = "http://127.0.0.1:8000"

# Test cases: BRCA1/BRCA2 mutations (Dr. Lustberg's exact use case)
TEST_CASES = [
    {
        "name": "BRCA1 C61G - RING Domain Disruption",
        "disease": "Ovarian Cancer",
        "mutations": [{
            "gene": "BRCA1",
            "hgvs_p": "C61G",
            "chrom": "17",
            "pos": 43104911,
            "ref": "T",
            "alt": "G",
            "consequence": "missense_variant",
            "build": "GRCh38"
        }],
        "expected_therapy": "platinum"
    },
    {
        "name": "BRCA1 185delAG - Founder Mutation",
        "disease": "Breast Cancer",
        "mutations": [{
            "gene": "BRCA1",
            "hgvs_p": "185delAG",
            "chrom": "17",
            "pos": 43124027,
            "ref": "AG",
            "alt": "",
            "consequence": "frameshift_variant",
            "build": "GRCh38"
        }],
        "expected_therapy": "platinum"
    },
    {
        "name": "BRCA2 6174delT - Founder Mutation",
        "disease": "Ovarian Cancer",
        "mutations": [{
            "gene": "BRCA2",
            "hgvs_p": "6174delT",
            "chrom": "13",
            "pos": 32340301,
            "ref": "T",
            "alt": "",
            "consequence": "frameshift_variant",
            "build": "GRCh38"
        }],
        "expected_therapy": "platinum"
    },
    {
        "name": "ATM R248W - DNA Damage Response",
        "disease": "Breast Cancer",
        "mutations": [{
            "gene": "ATM",
            "hgvs_p": "R248W",
            "chrom": "11",
            "pos": 108236123,
            "ref": "C",
            "alt": "T",
            "consequence": "missense_variant",
            "build": "GRCh38"
        }],
        "expected_therapy": "platinum"
    }
]

async def test_synthetic_lethality(test_case: dict) -> dict:
    """Run synthetic lethality analysis for a test case."""
    print(f"\n{'='*80}")
    print(f"🧬 TEST: {test_case['name']}")
    print(f"{'='*80}")
    
    payload = {
        "disease": test_case["disease"],
        "mutations": test_case["mutations"],
        "api_base": API_ROOT
    }
    
    print(f"📤 Sending request to {API_ROOT}/api/guidance/synthetic_lethality")
    print(f"📝 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minutes for full S/P/E analysis
            response = await client.post(
                f"{API_ROOT}/api/guidance/synthetic_lethality",
                json=payload
            )
            
            if response.status_code != 200:
                print(f"❌ ERROR: HTTP {response.status_code}")
                print(f"Response: {response.text}")
                return {"status": "failed", "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            
            # Validate result
            suggested = result.get("suggested_therapy", "").lower()
            expected = test_case["expected_therapy"]
            
            print(f"\n✅ SUCCESS")
            print(f"{'─'*80}")
            print(f"🎯 Suggested Therapy: {suggested.upper()}")
            print(f"🧪 Expected Therapy: {expected.upper()}")
            print(f"✓ Match: {'YES ✅' if expected in suggested else 'NO ❌'}")
            
            # Print analysis details
            print(f"\n📊 ANALYSIS DETAILS:")
            print(f"{'─'*80}")
            damage_count = len(result.get("damage_report", []))
            ess_count = len(result.get("essentiality_report", []))
            print(f"• Damage Analysis: {damage_count} variant(s)")
            print(f"• Essentiality Analysis: {ess_count} gene(s)")
            
            if damage_count > 0:
                dmg = result["damage_report"][0]
                func_score = dmg.get("functionality", {}).get("functionality_score")
                if func_score is not None:
                    print(f"• Functionality Score: {func_score:.2f}")
            
            if ess_count > 0:
                ess = result["essentiality_report"][0]
                ess_score = ess.get("result", {}).get("essentiality_score")
                if ess_score is not None:
                    print(f"• Essentiality Score: {ess_score:.2f}")
            
            # Print guidance if available
            if result.get("guidance"):
                guidance = result["guidance"]
                print(f"\n📋 GUIDANCE:")
                print(f"{'─'*80}")
                print(f"• Tier: {guidance.get('tier', 'N/A')}")
                print(f"• Strength: {guidance.get('strength', 'N/A')}")
                print(f"• Confidence: {guidance.get('confidence', 'N/A')}")
                print(f"• Efficacy Score: {guidance.get('efficacy_score', 'N/A')}")
            
            return {
                "status": "passed" if expected in suggested else "failed",
                "suggested_therapy": suggested,
                "expected_therapy": expected,
                "result": result
            }
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

async def main():
    """Run all synthetic lethality tests."""
    print(f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║       🔬 SYNTHETIC LETHALITY DETECTIVE - Backend Smoke Test                  ║
║                                                                               ║
║  Testing S/P/E Framework for Dr. Lustberg's Use Case:                        ║
║  "Which therapy will work for BRCA1/BRCA2 mutations?"                        ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    print(f"🌐 API Root: {API_ROOT}")
    print(f"📊 Total Tests: {len(TEST_CASES)}")
    
    # Check if backend is running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_ROOT}/health")
            if response.status_code != 200:
                print(f"\n❌ Backend health check failed: HTTP {response.status_code}")
                print(f"Please start the backend server first:")
                print(f"  cd oncology-coPilot/oncology-backend-minimal")
                print(f"  uvicorn api.main:app --reload")
                sys.exit(1)
            print(f"✅ Backend is healthy")
    except Exception as e:
        print(f"\n❌ Cannot connect to backend: {e}")
        print(f"Please start the backend server first:")
        print(f"  cd oncology-coPilot/oncology-backend-minimal")
        print(f"  uvicorn api.main:app --reload")
        sys.exit(1)
    
    # Run tests
    results = []
    for test_case in TEST_CASES:
        result = await test_synthetic_lethality(test_case)
        results.append({
            "name": test_case["name"],
            "status": result["status"],
            "suggested": result.get("suggested_therapy", "N/A"),
            "expected": result.get("expected_therapy", "N/A")
        })
    
    # Summary
    print(f"\n\n{'='*80}")
    print(f"📊 TEST SUMMARY")
    print(f"{'='*80}")
    
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] in ["failed", "error"])
    total = len(results)
    
    for r in results:
        status_emoji = "✅" if r["status"] == "passed" else "❌"
        print(f"{status_emoji} {r['name']}: {r['suggested']} (expected: {r['expected']})")
    
    print(f"\n{'─'*80}")
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    
    if passed == total:
        print(f"\n🎉 ALL TESTS PASSED! 🎉")
        print(f"✅ Synthetic Lethality Detective is ready for demo!")
        print(f"\n🚀 Next Steps:")
        print(f"  1. Start frontend: cd oncology-coPilot/oncology-frontend && npm run dev")
        print(f"  2. Navigate to: http://localhost:5173/synthetic-lethality")
        print(f"  3. Run the demo for Dr. Lustberg!")
        sys.exit(0)
    else:
        print(f"\n⚠️  SOME TESTS FAILED")
        print(f"Please check the errors above and fix them.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

