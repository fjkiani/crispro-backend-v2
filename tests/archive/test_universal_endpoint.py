"""
Test Unified Universal Endpoint

Tests the /api/complete_care/universal endpoint.
"""

import asyncio
import httpx
import json

API_BASE = "http://localhost:8000"

# Test profile
TEST_PROFILE = {
    "patient_id": "test_universal_001",
    "name": "Universal Test Patient",
    "disease": "ovarian_cancer_hgs",
    "stage": "IVB",
    "treatment_line": "first-line",
    "location": "New York",
    "zip_code": "10001",
    "biomarkers": {
        "ca125_value": 1500.0,
        "germline_status": "negative"
    },
    "tumor_context": {
        "somatic_mutations": [
            {
                "gene": "BRCA1",
                "hgvs_p": "p.Arg1835Ter",
                "consequence": "stop_gained"
            }
        ],
        "hrd_score": 35.0
    }
}


async def test_universal_endpoint():
    """Test the unified universal endpoint."""
    print("\n" + "="*80)
    print("TEST: Unified Universal Endpoint (/api/complete_care/universal)")
    print("="*80)
    
    request_payload = {
        "patient_profile": TEST_PROFILE,
        "include_trials": True,
        "include_soc": True,
        "include_biomarker": True,
        "include_wiwfm": True,
        "max_trials": 5
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            print(f"📤 Sending request to /api/complete_care/universal...")
            
            response = await client.post(
                f"{API_BASE}/api/complete_care/universal",
                json=request_payload
            )
            
            print(f"📥 Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"\n✅ Unified endpoint works!")
                print(f"\n📊 Response summary:")
                
                summary = data.get("summary", {})
                print(f"   • Components: {len(summary.get('components_included', []))}")
                print(f"   • NGS Status: {summary.get('ngs_status', 'N/A')}")
                print(f"   • Confidence: {summary.get('confidence_level', 'N/A')}")
                
                provenance = data.get("provenance", {})
                print(f"\n📋 Provenance:")
                print(f"   • Orchestrator: {provenance.get('orchestrator', 'N/A')}")
                print(f"   • Endpoints Called: {len(provenance.get('endpoints_called', []))}")
                
                # Verify key components
                checks = {
                    "Trials": data.get("trials") is not None,
                    "SOC": data.get("soc_recommendation") is not None,
                    "Biomarker": data.get("biomarker_intelligence") is not None,
                    "WIWFM": data.get("wiwfm") is not None,
                    "SAE Features": data.get("sae_features") is not None
                }
                
                print(f"\n✅ Component Checks:")
                for component, present in checks.items():
                    status = "✓" if present else "✗"
                    print(f"   {status} {component}")
                
                return True
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
                
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run test."""
    success = await test_universal_endpoint()
    
    print(f"\n{'='*80}")
    if success:
        print("✅ TEST PASSED: Unified universal endpoint is working!")
    else:
        print("❌ TEST FAILED: Check the output above for details.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(main())
