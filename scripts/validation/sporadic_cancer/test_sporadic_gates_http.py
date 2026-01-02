#!/usr/bin/env python3
"""
Test Sporadic Gates: Validate that IO boost and PARP rescue apply correctly.

Tests:
1. TMB-high patient → IO boost applied to checkpoint inhibitors
2. HRD-high patient → PARP rescue applied to PARP inhibitors
"""

import sys
import asyncio
import httpx
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "oncology-coPilot" / "oncology-backend-minimal"))


async def test_tmb_high_io_boost():
    """Test that TMB-high patients get IO boost for checkpoint inhibitors."""
    print("\n🧪 Test 1: TMB-High → IO Boost")
    print("=" * 60)
    
    api_root = "http://127.0.0.1:8000"
    
    # Create TMB-high patient (TMB >= 20)
    test_patient = {
        "mutations": [
            {
                "gene": "TP53",
                "chrom": "17",
                "pos": 7577539,
                "ref": "G",
                "alt": "A",
                "hgvs_p": "R248Q",
                "build": "GRCh37"
            }
        ],
        "tumor_context": {
            "tmb": 25.0,  # High TMB (>= 20)
            "level": "L1",
            "completeness_score": 0.33,
            "priors_used": False
        }
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{api_root}/api/efficacy/predict",
            json={
                "model_id": "evo2_1b",
                "mutations": test_patient["mutations"],
                "disease": "ovarian_cancer",
                "tumor_context": test_patient["tumor_context"],
                "options": {"adaptive": True}
            }
        )
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        data = response.json()
        drugs = data.get("drugs", [])
        
        # Find checkpoint inhibitors (pembrolizumab, nivolumab, etc.)
        io_drugs = [
            d for d in drugs 
            if "pembrolizumab" in d.get("name", "").lower() or 
               "nivolumab" in d.get("name", "").lower() or
               "checkpoint" in d.get("moa", "").lower() or
               "pd-1" in d.get("moa", "").lower() or
               "pd-l1" in d.get("moa", "").lower()
        ]
        
        if not io_drugs:
            print("⚠️  No checkpoint inhibitors found in drug panel")
            return False
        
        top_io_drug = io_drugs[0]
        efficacy_score = top_io_drug.get("efficacy_score", 0.0)
        confidence = top_io_drug.get("confidence", 0.0)
        
        # Check for sporadic gates provenance
        sporadic_gates = top_io_drug.get("sporadic_gates_provenance")
        
        print(f"   Top IO Drug: {top_io_drug.get('name')}")
        print(f"   Efficacy Score: {efficacy_score:.3f}")
        print(f"   Confidence: {confidence:.3f}")
        
        if sporadic_gates:
            gates_applied = sporadic_gates.get("gates_applied", [])
            io_boost_applied = any("io" in gate.lower() or "tmb" in gate.lower() for gate in gates_applied)
            
            if io_boost_applied:
                print(f"   ✅ IO Boost Applied: {gates_applied}")
                print(f"   Efficacy Delta: {sporadic_gates.get('efficacy_delta', 0):.3f}")
                return True
            else:
                print(f"   ⚠️  Sporadic gates applied but no IO boost: {gates_applied}")
                return False
        else:
            print("   ⚠️  No sporadic gates provenance found")
            return False


async def test_hrd_high_parp_rescue():
    """Test that HRD-high patients get PARP rescue for PARP inhibitors."""
    print("\n🧪 Test 2: HRD-High → PARP Rescue")
    print("=" * 60)
    
    api_root = "http://127.0.0.1:8000"
    
    # Create HRD-high patient (HRD >= 42)
    test_patient = {
        "mutations": [
            {
                "gene": "BRCA1",
                "chrom": "17",
                "pos": 43044295,
                "ref": "G",
                "alt": "A",
                "hgvs_p": "R1751*",
                "build": "GRCh37"
            }
        ],
        "tumor_context": {
            "hrd_score": 50.0,  # High HRD (>= 42)
            "level": "L1",
            "completeness_score": 0.33,
            "priors_used": False
        }
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{api_root}/api/efficacy/predict",
            json={
                "model_id": "evo2_1b",
                "mutations": test_patient["mutations"],
                "disease": "ovarian_cancer",
                "tumor_context": test_patient["tumor_context"],
                "options": {"adaptive": True}
            }
        )
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        data = response.json()
        drugs = data.get("drugs", [])
        
        # Find PARP inhibitors (olaparib, niraparib, rucaparib)
        parp_drugs = [
            d for d in drugs 
            if "olaparib" in d.get("name", "").lower() or 
               "niraparib" in d.get("name", "").lower() or
               "rucaparib" in d.get("name", "").lower() or
               "parp" in d.get("moa", "").lower()
        ]
        
        if not parp_drugs:
            print("⚠️  No PARP inhibitors found in drug panel")
            return False
        
        top_parp_drug = parp_drugs[0]
        efficacy_score = top_parp_drug.get("efficacy_score", 0.0)
        confidence = top_parp_drug.get("confidence", 0.0)
        
        # Check for sporadic gates provenance
        sporadic_gates = top_parp_drug.get("sporadic_gates_provenance")
        
        print(f"   Top PARP Drug: {top_parp_drug.get('name')}")
        print(f"   Efficacy Score: {efficacy_score:.3f}")
        print(f"   Confidence: {confidence:.3f}")
        
        if sporadic_gates:
            gates_applied = sporadic_gates.get("gates_applied", [])
            parp_rescue_applied = any("parp" in gate.lower() or "hrd" in gate.lower() for gate in gates_applied)
            
            if parp_rescue_applied:
                print(f"   ✅ PARP Rescue Applied: {gates_applied}")
                print(f"   Efficacy Delta: {sporadic_gates.get('efficacy_delta', 0):.3f}")
                return True
            else:
                print(f"   ⚠️  Sporadic gates applied but no PARP rescue: {gates_applied}")
                return False
        else:
            print("   ⚠️  No sporadic gates provenance found")
            return False


async def main():
    """Run all sporadic gates tests."""
    print("🧪 SPORADIC GATES VALIDATION")
    print("=" * 60)
    print("Testing that biomarker-based gates apply correctly...")
    
    results = []
    
    # Test 1: TMB-high → IO boost
    try:
        result1 = await test_tmb_high_io_boost()
        results.append(("TMB-High IO Boost", result1))
    except Exception as e:
        print(f"❌ Test 1 failed with error: {e}")
        results.append(("TMB-High IO Boost", False))
    
    # Test 2: HRD-high → PARP rescue
    try:
        result2 = await test_hrd_high_parp_rescue()
        results.append(("HRD-High PARP Rescue", result2))
    except Exception as e:
        print(f"❌ Test 2 failed with error: {e}")
        results.append(("HRD-High PARP Rescue", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✅ All sporadic gates tests PASSED")
        return 0
    else:
        print("\n❌ Some sporadic gates tests FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

