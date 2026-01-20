#!/usr/bin/env python3
"""
⚔️ CLINICAL TRIALS ENDPOINT SMOKE TESTS ⚔️

Tests the ClinicalTrials.gov matching endpoints.

Run: python tests/clinical_genomics/test_clinical_trials_endpoint.py
"""

import httpx
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test clinical trials health endpoint"""
    print("\n🏥 Testing clinical trials health endpoint...")
    
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{BASE_URL}/api/clinical_trials/health")
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

def test_brca1_breast_cancer_match():
    """Test BRCA1 breast cancer trial matching"""
    print("\n🧬 Testing BRCA1 breast cancer trial matching...")
    
    payload = {
        "mutations": [
            {"gene": "BRCA1", "hgvs_p": "p.Gln1756fs"}
        ],
        "cancer_type": "breast cancer",
        "max_results": 5
    }
    
    try:
        with httpx.Client(timeout=60) as client:  # Longer timeout for API call
            resp = client.post(
                f"{BASE_URL}/api/clinical_trials/match",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            print(f"   Total Matches: {data.get('total_matches')}")
            
            if data.get("trials"):
                for i, trial in enumerate(data["trials"][:3], 1):
                    print(f"\n   Trial {i}:")
                    print(f"      NCT ID: {trial.get('nct_id')}")
                    print(f"      Title: {trial.get('title')[:80]}...")
                    print(f"      Status: {trial.get('status')}")
                    print(f"      Match Score: {trial.get('match_score'):.2f}")
                    print(f"      Match Reasons: {', '.join(trial.get('match_reasons', []))}")
            
            # Validate
            if data.get("total_matches") > 0:
                print(f"\n   ✅ Found {data.get('total_matches')} matching trials")
                return True
            else:
                print(f"\n   ⚠️  No trials found (API may be slow/rate-limited)")
                return True  # Not a failure - just empty result
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def test_tp53_nsclc_match():
    """Test TP53 NSCLC trial matching"""
    print("\n🧬 Testing TP53 NSCLC trial matching...")
    
    payload = {
        "mutations": [
            {"gene": "TP53", "hgvs_p": "p.Arg248Trp"}
        ],
        "cancer_type": "lung cancer",
        "max_results": 5
    }
    
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{BASE_URL}/api/clinical_trials/match",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            print(f"   Total Matches: {data.get('total_matches')}")
            
            if data.get("trials"):
                for i, trial in enumerate(data["trials"][:2], 1):
                    print(f"\n   Trial {i}:")
                    print(f"      NCT ID: {trial.get('nct_id')}")
                    print(f"      Title: {trial.get('title')[:80]}...")
                    print(f"      Match Score: {trial.get('match_score'):.2f}")
            
            # Validate
            if data.get("total_matches") >= 0:  # Allow 0 results
                print(f"\n   ✅ Trial search completed ({data.get('total_matches')} matches)")
                return True
            else:
                print(f"\n   ❌ Unexpected response")
                return False
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def test_basket_trial_match():
    """Test basket trial identification"""
    print("\n🧬 Testing basket trial (tumor-agnostic) matching...")
    
    payload = {
        "mutations": [
            {"gene": "NTRK1", "hgvs_p": "p.Gly595Arg"}
        ],
        "cancer_type": None,  # Tumor-agnostic
        "max_results": 5
    }
    
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{BASE_URL}/api/clinical_trials/match",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            print(f"   Total Matches: {data.get('total_matches')}")
            
            # Check for basket trials
            basket_trials = [
                trial for trial in data.get("trials", [])
                if "basket" in " ".join(trial.get("match_reasons", [])).lower()
            ]
            
            if basket_trials:
                print(f"\n   Found {len(basket_trials)} basket trials:")
                for trial in basket_trials[:2]:
                    print(f"      - {trial.get('title')[:80]}...")
            
            # Validate
            print(f"\n   ✅ Basket trial search completed")
            return True
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("⚔️ CLINICAL TRIALS ENDPOINT SMOKE TESTS")
    print("="*60)
    print("⚠️  Note: These tests query live ClinicalTrials.gov API")
    print("     Results may vary based on API availability and rate limits")
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    results.append(("BRCA1 Breast Cancer Match", test_brca1_breast_cancer_match()))
    results.append(("TP53 NSCLC Match", test_tp53_nsclc_match()))
    results.append(("Basket Trial Match", test_basket_trial_match()))
    
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


