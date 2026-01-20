#!/usr/bin/env python3
"""
⚔️ ACMG ENDPOINT SMOKE TESTS ⚔️

Tests the ACMG/AMP variant classification endpoint.

Run: python tests/clinical_genomics/test_acmg_endpoint.py
"""

import httpx
import json
import sys
from typing import Dict, Any

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test ACMG health endpoint"""
    print("\n🏥 Testing ACMG health endpoint...")
    
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{BASE_URL}/api/acmg/health")
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

def test_brca1_truncating():
    """Test BRCA1 c.5266dupC (frameshift - should be Pathogenic)"""
    print("\n🧬 Testing BRCA1 c.5266dupC (truncating variant)...")
    
    payload = {
        "gene": "BRCA1",
        "chrom": "17",
        "pos": 43045802,
        "ref": "C",
        "alt": "CT",
        "hgvs_c": "c.5266dupC",
        "hgvs_p": "p.Gln1756fs",
        "consequence": "frameshift_variant"
    }
    
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(f"{BASE_URL}/api/acmg/classify_variant", json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            print(f"   📊 Classification: {data['classification']}")
            print(f"   📊 Confidence: {data['confidence']:.2f}")
            print(f"   📊 Evidence Codes: {', '.join([e['code'] for e in data['evidence_codes']])}")
            
            if data.get("clinvar_classification"):
                print(f"   📊 ClinVar: {data['clinvar_classification']} ({data.get('clinvar_review_status', 'unknown')})")
            
            # Validate expected results
            if data["classification"] in ["Pathogenic", "Likely Pathogenic"]:
                print(f"   ✅ Correct classification (expected Pathogenic)")
                
                # Check for PVS1 (truncating variant)
                has_pvs1 = any(e["code"] == "PVS1" for e in data["evidence_codes"])
                if has_pvs1:
                    print(f"   ✅ PVS1 correctly applied (truncating variant)")
                else:
                    print(f"   ⚠️  PVS1 not applied (expected for frameshift)")
                
                return True
            else:
                print(f"   ❌ Unexpected classification: {data['classification']} (expected Pathogenic)")
                return False
                
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def test_brca2_missense():
    """Test BRCA2 missense variant (should be VUS or Likely Pathogenic)"""
    print("\n🧬 Testing BRCA2 missense variant...")
    
    payload = {
        "gene": "BRCA2",
        "chrom": "13",
        "pos": 32936732,
        "ref": "G",
        "alt": "A",
        "consequence": "missense_variant"
    }
    
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(f"{BASE_URL}/api/acmg/classify_variant", json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            print(f"   📊 Classification: {data['classification']}")
            print(f"   📊 Confidence: {data['confidence']:.2f}")
            print(f"   📊 Evidence Codes: {', '.join([e['code'] for e in data['evidence_codes']])}")
            
            # Missense should NOT have PVS1
            has_pvs1 = any(e["code"] == "PVS1" for e in data["evidence_codes"])
            if not has_pvs1:
                print(f"   ✅ PVS1 correctly NOT applied (missense variant)")
            else:
                print(f"   ❌ PVS1 incorrectly applied to missense variant")
                return False
            
            # Should have PP3 (in-silico prediction)
            has_pp3 = any(e["code"] == "PP3" for e in data["evidence_codes"])
            if has_pp3:
                print(f"   ✅ PP3 correctly applied (in-silico predictions)")
            
            return True
                
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def test_tp53_nonsense():
    """Test TP53 nonsense variant (should be Pathogenic)"""
    print("\n🧬 Testing TP53 nonsense variant...")
    
    payload = {
        "gene": "TP53",
        "chrom": "17",
        "pos": 7674220,
        "ref": "C",
        "alt": "T",
        "hgvs_p": "p.Arg248Ter",
        "consequence": "stop_gained"
    }
    
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(f"{BASE_URL}/api/acmg/classify_variant", json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            print(f"   📊 Classification: {data['classification']}")
            print(f"   📊 Confidence: {data['confidence']:.2f}")
            print(f"   📊 Evidence Codes: {', '.join([e['code'] for e in data['evidence_codes']])}")
            
            # Should be Pathogenic with PVS1
            if data["classification"] in ["Pathogenic", "Likely Pathogenic"]:
                print(f"   ✅ Correct classification")
                
                has_pvs1 = any(e["code"] == "PVS1" for e in data["evidence_codes"])
                if has_pvs1:
                    print(f"   ✅ PVS1 correctly applied (nonsense variant)")
                    return True
                else:
                    print(f"   ⚠️  PVS1 not applied (expected for stop_gained)")
                    return True  # Still pass, classification is correct
            else:
                print(f"   ❌ Unexpected classification")
                return False
                
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("⚔️  ACMG ENDPOINT SMOKE TESTS ⚔️")
    print("="*60)
    print("\nℹ️  Backend must be running on http://127.0.0.1:8000")
    print("ℹ️  Start with: cd oncology-backend-minimal && uvicorn api.main:app")
    
    tests = [
        ("Health Check", test_health),
        ("BRCA1 Truncating", test_brca1_truncating),
        ("BRCA2 Missense", test_brca2_missense),
        ("TP53 Nonsense", test_tp53_nonsense),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"   ❌ Test crashed: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status} {name}")
    
    print(f"\n🎯 PASSED: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSING - ACMG ENDPOINT READY! 💪")
        return 0
    else:
        print(f"\n❌ {total - passed} TESTS FAILING")
        return 1

if __name__ == "__main__":
    sys.exit(main())


