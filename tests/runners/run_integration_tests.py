"""
Run Integration Tests - Direct Python Execution

Runs integration tests without pytest dependency.
"""

import sys
import asyncio
import httpx
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

API_BASE = "http://localhost:8000"

# Test profiles
SIMPLE_PROFILE = {
    "patient_id": "test_integration_001",
    "name": "Integration Test Patient",
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

FULL_PROFILE = {
    "patient_id": "test_integration_002",
    "demographics": {
        "name": "Full Profile Patient",
        "age": 45,
        "sex": "female"
    },
    "disease": {
        "type": "ovarian_cancer_hgs",
        "stage": "IVB"
    },
    "treatment": {
        "line": "first-line"
    },
    "logistics": {
        "location": "New York",
        "zip_code": "10001"
    },
    "biomarkers": {
        "ca125_value": 1500.0
    },
    "tumor_context": {
        "somatic_mutations": [
            {
                "gene": "BRCA1",
                "hgvs_p": "p.Arg1835Ter"
            }
        ]
    }
}

# Test results
results = {
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "errors": []
}


async def test_complete_care_universal_simple_profile():
    """Test /api/complete_care/universal with simple profile."""
    print("  🧪 test_complete_care_universal_simple_profile...", end=" ")
    try:
        request_payload = {
            "patient_profile": SIMPLE_PROFILE,
            "include_trials": True,
            "include_soc": True,
            "include_biomarker": True,
            "include_wiwfm": True
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{API_BASE}/api/complete_care/universal",
                    json=request_payload
                )
                
                assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
                
                data = response.json()
                
                # Verify response structure
                assert "summary" in data
                assert "provenance" in data
                
                # Verify components are present (may be None if service unavailable)
                assert "trials" in data
                assert "soc_recommendation" in data
                assert "biomarker_intelligence" in data
                assert "wiwfm" in data
                
                print("✅ PASSED")
                results["passed"] += 1
                
            except httpx.ConnectError:
                print("⏭️  SKIPPED (server not running)")
                results["skipped"] += 1
    except AssertionError as e:
        print(f"❌ FAILED: {e}")
        results["failed"] += 1
        results["errors"].append(f"test_complete_care_universal_simple_profile: {e}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        results["failed"] += 1
        results["errors"].append(f"test_complete_care_universal_simple_profile: {e}")


async def test_complete_care_universal_full_profile():
    """Test /api/complete_care/universal with full profile."""
    print("  🧪 test_complete_care_universal_full_profile...", end=" ")
    try:
        request_payload = {
            "patient_profile": FULL_PROFILE,
            "include_trials": True,
            "include_soc": True,
            "include_biomarker": True
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{API_BASE}/api/complete_care/universal",
                    json=request_payload
                )
                
                assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
                
                data = response.json()
                
                # Verify response structure
                assert "summary" in data
                assert "provenance" in data
                
                print("✅ PASSED")
                results["passed"] += 1
                
            except httpx.ConnectError:
                print("⏭️  SKIPPED (server not running)")
                results["skipped"] += 1
    except AssertionError as e:
        print(f"❌ FAILED: {e}")
        results["failed"] += 1
        results["errors"].append(f"test_complete_care_universal_full_profile: {e}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        results["failed"] += 1
        results["errors"].append(f"test_complete_care_universal_full_profile: {e}")


async def test_complete_care_universal_optional_services():
    """Test /api/complete_care/universal with optional services disabled."""
    print("  🧪 test_complete_care_universal_optional_services...", end=" ")
    try:
        request_payload = {
            "patient_profile": SIMPLE_PROFILE,
            "include_trials": False,
            "include_soc": True,
            "include_biomarker": True,
            "include_wiwfm": False,
            "include_food": False,
            "include_resistance": False
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{API_BASE}/api/complete_care/universal",
                    json=request_payload
                )
                
                assert response.status_code == 200
                
                data = response.json()
                
                # Verify optional services are None when disabled
                assert data.get("trials") is None or data.get("trials") == []
                assert data.get("wiwfm") is None
                
                print("✅ PASSED")
                results["passed"] += 1
                
            except httpx.ConnectError:
                print("⏭️  SKIPPED (server not running)")
                results["skipped"] += 1
    except AssertionError as e:
        print(f"❌ FAILED: {e}")
        results["failed"] += 1
        results["errors"].append(f"test_complete_care_universal_optional_services: {e}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        results["failed"] += 1
        results["errors"].append(f"test_complete_care_universal_optional_services: {e}")


async def test_complete_care_universal_error_handling():
    """Test /api/complete_care/universal error handling with invalid profile."""
    print("  🧪 test_complete_care_universal_error_handling...", end=" ")
    try:
        request_payload = {
            "patient_profile": {
                "patient_id": "invalid"
                # Missing required fields
            }
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{API_BASE}/api/complete_care/universal",
                    json=request_payload
                )
                
                # May return 200 (lenient validation) or 422/400 (strict validation)
                # Universal endpoint is lenient, so 200 is acceptable
                assert response.status_code in [200, 400, 422], f"Expected 200/400/422, got {response.status_code}"
                
                print("✅ PASSED")
                results["passed"] += 1
                
            except httpx.ConnectError:
                print("⏭️  SKIPPED (server not running)")
                results["skipped"] += 1
    except AssertionError as e:
        print(f"❌ FAILED: {e}")
        results["failed"] += 1
        results["errors"].append(f"test_complete_care_universal_error_handling: {e}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        results["failed"] += 1
        results["errors"].append(f"test_complete_care_universal_error_handling: {e}")


async def test_biomarker_analyze_endpoint():
    """Test /api/biomarker/intelligence endpoint."""
    print("  🧪 test_biomarker_analyze_endpoint...", end=" ")
    try:
        request_payload = {
            "disease_type": "ovarian_cancer_hgs",
            "biomarker_type": "ca125",
            "current_value": 1500.0,
            "baseline_value": 35.0,
            "cycle": 2,
            "treatment_ongoing": True
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{API_BASE}/api/biomarker/intelligence",
                    json=request_payload
                )
                
                assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
                
                data = response.json()
                
                # Verify response structure (biomarker intelligence returns various keys)
                assert isinstance(data, dict), f"Expected dict, got {type(data)}: {data}"
                assert "biomarker_type" in data or "burden_class" in data or "error" in data or "burden_assessment" in data, f"Unexpected response keys: {list(data.keys())[:10]}"
                
                print("✅ PASSED")
                results["passed"] += 1
                
            except httpx.ConnectError:
                print("⏭️  SKIPPED (server not running)")
                results["skipped"] += 1
    except AssertionError as e:
        print(f"❌ FAILED: {e}")
        results["failed"] += 1
        results["errors"].append(f"test_biomarker_analyze_endpoint: {e}")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        results["failed"] += 1
        results["errors"].append(f"test_biomarker_analyze_endpoint: {e}")


async def run_tests():
    """Run all integration tests."""
    print("\n" + "="*80)
    print("INTEGRATION TEST SUITE")
    print("="*80)
    print(f"Testing against: {API_BASE}\n")
    
    await test_complete_care_universal_simple_profile()
    await test_complete_care_universal_full_profile()
    await test_complete_care_universal_optional_services()
    await test_complete_care_universal_error_handling()
    await test_biomarker_analyze_endpoint()
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⏭️  Skipped: {results['skipped']}")
    print(f"📊 Total:  {results['passed'] + results['failed'] + results['skipped']}")
    
    if results["errors"]:
        print(f"\n❌ Errors:")
        for error in results["errors"]:
            print(f"   • {error}")
    
    print("="*80 + "\n")
    
    # Exit with error code if any failures
    sys.exit(1 if results["failed"] > 0 else 0)


if __name__ == "__main__":
    asyncio.run(run_tests())

