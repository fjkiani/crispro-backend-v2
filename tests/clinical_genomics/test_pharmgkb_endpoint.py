#!/usr/bin/env python3
"""
⚔️ PHARMGKB ENDPOINT SMOKE TESTS ⚔️

Tests the PharmGKB pharmacogenomics endpoints.

Run: python tests/clinical_genomics/test_pharmgkb_endpoint.py
"""

import httpx
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test PharmGKB health endpoint"""
    print("\n🏥 Testing PharmGKB health endpoint...")
    
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{BASE_URL}/api/pharmgkb/health")
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("status") == "operational":
                print(f"   ✅ Health check passed")
                return True
            else:
                print(f"   ❌ Unexpected health status: {data}")
                return False
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False

def test_metabolizer_status_cyp2d6_poor():
    """Test CYP2D6 poor metabolizer classification"""
    print("\n🧬 Testing CYP2D6 poor metabolizer (*4/*4)...")
    
    payload = {
        "gene": "CYP2D6",
        "diplotype": "*4/*4"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{BASE_URL}/api/pharmgkb/metabolizer_status",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            print(f"   Gene: {data.get('gene')}")
            print(f"   Status: {data.get('metabolizer_status')}")
            print(f"   Confidence: {data.get('confidence'):.2f}")
            print(f"   Activity Score: {data.get('activity_score')}")
            print(f"   Drugs Affected: {', '.join(data.get('drugs_affected', []))}")
            
            # Validate
            if data.get("metabolizer_status") == "Poor Metabolizer":
                print(f"   ✅ Correct poor metabolizer classification")
                return True
            else:
                print(f"   ❌ Unexpected status: {data.get('metabolizer_status')}")
                return False
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def test_metabolizer_status_cyp2c19_ultrarapid():
    """Test CYP2C19 ultrarapid metabolizer classification"""
    print("\n🧬 Testing CYP2C19 ultrarapid metabolizer (*17/*17)...")
    
    payload = {
        "gene": "CYP2C19",
        "diplotype": "*17/*17"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{BASE_URL}/api/pharmgkb/metabolizer_status",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            print(f"   Gene: {data.get('gene')}")
            print(f"   Status: {data.get('metabolizer_status')}")
            print(f"   Confidence: {data.get('confidence'):.2f}")
            print(f"   Activity Score: {data.get('activity_score')}")
            
            # Validate
            if data.get("metabolizer_status") == "Ultrarapid Metabolizer":
                print(f"   ✅ Correct ultrarapid metabolizer classification")
                return True
            else:
                print(f"   ❌ Unexpected status: {data.get('metabolizer_status')}")
                return False
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def test_drug_interaction_tamoxifen_cyp2d6():
    """Test tamoxifen-CYP2D6 interaction"""
    print("\n💊 Testing tamoxifen-CYP2D6 interaction...")
    
    payload = {
        "drug_name": "tamoxifen",
        "gene": "CYP2D6"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{BASE_URL}/api/pharmgkb/drug_interaction",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            print(f"   Drug: {data.get('drug_name')}")
            print(f"   Gene: {data.get('gene')}")
            print(f"   Interaction Type: {data.get('interaction_type')}")
            print(f"   Significance: {data.get('clinical_significance')}")
            print(f"   Recommendation: {data.get('recommendation')[:100]}...")
            
            # Validate
            if data.get("clinical_significance") == "High":
                print(f"   ✅ High significance interaction detected")
                return True
            else:
                print(f"   ❌ Unexpected significance: {data.get('clinical_significance')}")
                return False
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def test_drug_interaction_clopidogrel_cyp2c19():
    """Test clopidogrel-CYP2C19 interaction"""
    print("\n💊 Testing clopidogrel-CYP2C19 interaction...")
    
    payload = {
        "drug_name": "clopidogrel",
        "gene": "CYP2C19"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{BASE_URL}/api/pharmgkb/drug_interaction",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            print(f"   Drug: {data.get('drug_name')}")
            print(f"   Gene: {data.get('gene')}")
            print(f"   Interaction Type: {data.get('interaction_type')}")
            print(f"   Significance: {data.get('clinical_significance')}")
            print(f"   Recommendation: {data.get('recommendation')[:100]}...")
            
            # Validate
            if data.get("interaction_type") == "Efficacy":
                print(f"   ✅ Efficacy interaction detected")
                return True
            else:
                print(f"   ❌ Unexpected interaction type: {data.get('interaction_type')}")
                return False
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("⚔️ PHARMGKB ENDPOINT SMOKE TESTS")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    results.append(("CYP2D6 Poor Metabolizer", test_metabolizer_status_cyp2d6_poor()))
    results.append(("CYP2C19 Ultrarapid Metabolizer", test_metabolizer_status_cyp2c19_ultrarapid()))
    results.append(("Tamoxifen-CYP2D6 Interaction", test_drug_interaction_tamoxifen_cyp2d6()))
    results.append(("Clopidogrel-CYP2C19 Interaction", test_drug_interaction_clopidogrel_cyp2c19()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n🎯 TOTAL: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()


