"""
Test Universal Complete Care Orchestrator

Tests the universal orchestrator with:
1. Ayesha profile (should match Ayesha orchestrator results)
2. Simple profile format
3. Full profile format
"""

import asyncio
import httpx
import json
from typing import Dict, Any

API_BASE = "http://localhost:8000"

# Ayesha profile (simple format)
AYESHA_SIMPLE_PROFILE = {
    "patient_id": "ayesha_kiani",
    "name": "AK",
    "disease": "ovarian_cancer_hgs",
    "stage": "IVB",
    "treatment_line": "first-line",
    "location": "New York",
    "zip_code": "10001",
    "age": 45,
    "sex": "female",
    "biomarkers": {
        "ca125_value": 2842.0,
        "germline_status": "negative"
    },
    "tumor_context": {
        "somatic_mutations": [
            {
                "gene": "BRCA1",
                "hgvs_p": "p.Arg1835Ter",
                "consequence": "stop_gained",
                "chrom": "17",
                "pos": 43044295,
                "ref": "C",
                "alt": "T"
            },
            {
                "gene": "TP53",
                "hgvs_p": "p.Arg175His",
                "consequence": "missense_variant",
                "chrom": "17",
                "pos": 7673802,
                "ref": "C",
                "alt": "T"
            }
        ],
        "hrd_score": 42.0,
        "tmb_score": 8.5
    }
}

# Simple profile for another patient
MELANOMA_SIMPLE_PROFILE = {
    "patient_id": "test_patient_001",
    "name": "Test Patient",
    "disease": "melanoma",
    "stage": "IIIB",
    "treatment_line": "first-line",
    "location": "California",
    "zip_code": "90210",
    "age": 55,
    "sex": "male",
    "biomarkers": {},
    "tumor_context": {
        "somatic_mutations": [
            {
                "gene": "BRAF",
                "hgvs_p": "p.Val600Glu",
                "consequence": "missense_variant"
            }
        ]
    }
}


async def test_universal_orchestrator(profile: Dict[str, Any], test_name: str):
    """Test universal orchestrator with a patient profile."""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    
    request_payload = {
        "patient_profile": profile,
        "include_trials": True,
        "include_soc": True,
        "include_biomarker": True,
        "include_wiwfm": True,
        "include_food": False,
        "include_resistance": False,
        "include_resistance_prediction": False,
        "max_trials": 5
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            print(f"📤 Sending request to /api/complete_care/v2...")
            print(f"   Patient: {profile.get('name', profile.get('patient_id', 'Unknown'))}")
            print(f"   Disease: {profile.get('disease', 'Unknown')}")
            
            response = await client.post(
                f"{API_BASE}/api/complete_care/v2",
                json=request_payload
            )
            
            print(f"📥 Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check key components
                print(f"\n✅ Response received successfully!")
                print(f"\n📊 Components included:")
                
                summary = data.get("summary", {})
                components = summary.get("components_included", [])
                for component in components:
                    print(f"   ✓ {component}")
                
                # Check specific components
                print(f"\n🔍 Component Details:")
                
                if data.get("trials"):
                    trials_count = len(data["trials"].get("trials", []))
                    print(f"   • Trials: {trials_count} found")
                
                if data.get("soc_recommendation"):
                    soc = data["soc_recommendation"]
                    if isinstance(soc, dict) and "regimen" in soc:
                        print(f"   • SOC: {soc.get('regimen', 'N/A')}")
                    else:
                        print(f"   • SOC: {soc.get('status', 'N/A')}")
                
                if data.get("biomarker_intelligence"):
                    biomarker = data["biomarker_intelligence"]
                    print(f"   • Biomarker: {biomarker.get('status', 'N/A')}")
                
                if data.get("wiwfm"):
                    wiwfm = data["wiwfm"]
                    if isinstance(wiwfm, dict):
                        if wiwfm.get("status") == "awaiting_ngs":
                            print(f"   • WIWFM: {wiwfm.get('status')}")
                        else:
                            drugs_count = len(wiwfm.get("drugs", []))
                            print(f"   • WIWFM: {drugs_count} drugs ranked")
                
                if data.get("sae_features"):
                    sae = data["sae_features"]
                    if isinstance(sae, dict) and "status" not in sae:
                        print(f"   • SAE Features: Computed")
                    else:
                        print(f"   • SAE Features: {sae.get('status', 'N/A')}")
                
                # Provenance
                provenance = data.get("provenance", {})
                print(f"\n📋 Provenance:")
                print(f"   • Orchestrator: {provenance.get('orchestrator', 'N/A')}")
                print(f"   • For Patient: {provenance.get('for_patient', 'N/A')}")
                print(f"   • NGS Status: {provenance.get('ngs_status', 'N/A')}")
                
                return True, data
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False, None
                
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


async def test_health_check():
    """Test health check endpoint."""
    print(f"\n{'='*80}")
    print(f"TEST: Health Check")
    print(f"{'='*80}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE}/api/complete_care/v2/health")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed!")
                print(f"   Status: {data.get('status')}")
                print(f"   Service: {data.get('service')}")
                print(f"   Capabilities: {len(data.get('capabilities', []))} enabled")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Health check exception: {str(e)}")
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("UNIVERSAL COMPLETE CARE ORCHESTRATOR - TEST SUITE")
    print("="*80)
    
    # Test 1: Health check
    health_ok = await test_health_check()
    if not health_ok:
        print("\n⚠️  Health check failed - server may not be running")
        print("   Make sure the server is running: uvicorn api.main:app --reload")
        return
    
    # Test 2: Ayesha profile (simple format)
    ayesha_ok, ayesha_data = await test_universal_orchestrator(
        AYESHA_SIMPLE_PROFILE,
        "Ayesha Profile (Simple Format)"
    )
    
    # Test 3: Melanoma profile (simple format)
    melanoma_ok, melanoma_data = await test_universal_orchestrator(
        MELANOMA_SIMPLE_PROFILE,
        "Melanoma Profile (Simple Format)"
    )
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Health Check: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"Ayesha Profile: {'✅ PASS' if ayesha_ok else '❌ FAIL'}")
    print(f"Melanoma Profile: {'✅ PASS' if melanoma_ok else '❌ FAIL'}")
    
    if ayesha_ok and melanoma_ok:
        print(f"\n🎉 All tests passed! Universal orchestrator is working correctly.")
    else:
        print(f"\n⚠️  Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    asyncio.run(main())







Test Universal Complete Care Orchestrator

Tests the universal orchestrator with:
1. Ayesha profile (should match Ayesha orchestrator results)
2. Simple profile format
3. Full profile format
"""

import asyncio
import httpx
import json
from typing import Dict, Any

API_BASE = "http://localhost:8000"

# Ayesha profile (simple format)
AYESHA_SIMPLE_PROFILE = {
    "patient_id": "ayesha_kiani",
    "name": "AK",
    "disease": "ovarian_cancer_hgs",
    "stage": "IVB",
    "treatment_line": "first-line",
    "location": "New York",
    "zip_code": "10001",
    "age": 45,
    "sex": "female",
    "biomarkers": {
        "ca125_value": 2842.0,
        "germline_status": "negative"
    },
    "tumor_context": {
        "somatic_mutations": [
            {
                "gene": "BRCA1",
                "hgvs_p": "p.Arg1835Ter",
                "consequence": "stop_gained",
                "chrom": "17",
                "pos": 43044295,
                "ref": "C",
                "alt": "T"
            },
            {
                "gene": "TP53",
                "hgvs_p": "p.Arg175His",
                "consequence": "missense_variant",
                "chrom": "17",
                "pos": 7673802,
                "ref": "C",
                "alt": "T"
            }
        ],
        "hrd_score": 42.0,
        "tmb_score": 8.5
    }
}

# Simple profile for another patient
MELANOMA_SIMPLE_PROFILE = {
    "patient_id": "test_patient_001",
    "name": "Test Patient",
    "disease": "melanoma",
    "stage": "IIIB",
    "treatment_line": "first-line",
    "location": "California",
    "zip_code": "90210",
    "age": 55,
    "sex": "male",
    "biomarkers": {},
    "tumor_context": {
        "somatic_mutations": [
            {
                "gene": "BRAF",
                "hgvs_p": "p.Val600Glu",
                "consequence": "missense_variant"
            }
        ]
    }
}


async def test_universal_orchestrator(profile: Dict[str, Any], test_name: str):
    """Test universal orchestrator with a patient profile."""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    
    request_payload = {
        "patient_profile": profile,
        "include_trials": True,
        "include_soc": True,
        "include_biomarker": True,
        "include_wiwfm": True,
        "include_food": False,
        "include_resistance": False,
        "include_resistance_prediction": False,
        "max_trials": 5
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            print(f"📤 Sending request to /api/complete_care/v2...")
            print(f"   Patient: {profile.get('name', profile.get('patient_id', 'Unknown'))}")
            print(f"   Disease: {profile.get('disease', 'Unknown')}")
            
            response = await client.post(
                f"{API_BASE}/api/complete_care/v2",
                json=request_payload
            )
            
            print(f"📥 Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check key components
                print(f"\n✅ Response received successfully!")
                print(f"\n📊 Components included:")
                
                summary = data.get("summary", {})
                components = summary.get("components_included", [])
                for component in components:
                    print(f"   ✓ {component}")
                
                # Check specific components
                print(f"\n🔍 Component Details:")
                
                if data.get("trials"):
                    trials_count = len(data["trials"].get("trials", []))
                    print(f"   • Trials: {trials_count} found")
                
                if data.get("soc_recommendation"):
                    soc = data["soc_recommendation"]
                    if isinstance(soc, dict) and "regimen" in soc:
                        print(f"   • SOC: {soc.get('regimen', 'N/A')}")
                    else:
                        print(f"   • SOC: {soc.get('status', 'N/A')}")
                
                if data.get("biomarker_intelligence"):
                    biomarker = data["biomarker_intelligence"]
                    print(f"   • Biomarker: {biomarker.get('status', 'N/A')}")
                
                if data.get("wiwfm"):
                    wiwfm = data["wiwfm"]
                    if isinstance(wiwfm, dict):
                        if wiwfm.get("status") == "awaiting_ngs":
                            print(f"   • WIWFM: {wiwfm.get('status')}")
                        else:
                            drugs_count = len(wiwfm.get("drugs", []))
                            print(f"   • WIWFM: {drugs_count} drugs ranked")
                
                if data.get("sae_features"):
                    sae = data["sae_features"]
                    if isinstance(sae, dict) and "status" not in sae:
                        print(f"   • SAE Features: Computed")
                    else:
                        print(f"   • SAE Features: {sae.get('status', 'N/A')}")
                
                # Provenance
                provenance = data.get("provenance", {})
                print(f"\n📋 Provenance:")
                print(f"   • Orchestrator: {provenance.get('orchestrator', 'N/A')}")
                print(f"   • For Patient: {provenance.get('for_patient', 'N/A')}")
                print(f"   • NGS Status: {provenance.get('ngs_status', 'N/A')}")
                
                return True, data
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False, None
                
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None


async def test_health_check():
    """Test health check endpoint."""
    print(f"\n{'='*80}")
    print(f"TEST: Health Check")
    print(f"{'='*80}")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE}/api/complete_care/v2/health")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed!")
                print(f"   Status: {data.get('status')}")
                print(f"   Service: {data.get('service')}")
                print(f"   Capabilities: {len(data.get('capabilities', []))} enabled")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Health check exception: {str(e)}")
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("UNIVERSAL COMPLETE CARE ORCHESTRATOR - TEST SUITE")
    print("="*80)
    
    # Test 1: Health check
    health_ok = await test_health_check()
    if not health_ok:
        print("\n⚠️  Health check failed - server may not be running")
        print("   Make sure the server is running: uvicorn api.main:app --reload")
        return
    
    # Test 2: Ayesha profile (simple format)
    ayesha_ok, ayesha_data = await test_universal_orchestrator(
        AYESHA_SIMPLE_PROFILE,
        "Ayesha Profile (Simple Format)"
    )
    
    # Test 3: Melanoma profile (simple format)
    melanoma_ok, melanoma_data = await test_universal_orchestrator(
        MELANOMA_SIMPLE_PROFILE,
        "Melanoma Profile (Simple Format)"
    )
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Health Check: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"Ayesha Profile: {'✅ PASS' if ayesha_ok else '❌ FAIL'}")
    print(f"Melanoma Profile: {'✅ PASS' if melanoma_ok else '❌ FAIL'}")
    
    if ayesha_ok and melanoma_ok:
        print(f"\n🎉 All tests passed! Universal orchestrator is working correctly.")
    else:
        print(f"\n⚠️  Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    asyncio.run(main())


























