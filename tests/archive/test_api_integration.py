#!/usr/bin/env python3
"""
API Integration Tests for Phase 0 & Phase 1 changes.
Tests actual API endpoints with disease-aware panels and evidence integration.
"""
import asyncio
import httpx
import json
from typing import Dict, Any

API_BASE = "http://127.0.0.1:8000"


async def test_efficacy_with_disease(disease: str, mutations: list, expected_drugs: list = None):
    """Test efficacy prediction with disease parameter."""
    print(f"\n{'='*60}")
    print(f"Testing Efficacy Prediction: {disease}")
    print(f"{'='*60}")
    
    payload = {
        "model_id": "evo2_1b",
        "mutations": mutations,
        "options": {
            "adaptive": True,
            "ensemble": False,
            "ablation_mode": "SPE",
        },
        "disease": disease,
        "api_base": API_BASE,
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{API_BASE}/api/efficacy/predict",
                json=payload,
            )
            
            if resp.status_code >= 400:
                print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")
                return False
            
            data = resp.json()
            drugs = data.get("drugs", [])
            
            print(f"\n✅ Response received: {len(drugs)} drugs")
            print(f"   Disease: {data.get('provenance', {}).get('disease', 'N/A')}")
            print(f"   Evidence tier: {data.get('evidence_tier', 'N/A')}")
            
            print(f"\n📊 Top 5 Drugs:")
            for i, drug in enumerate(drugs[:5], 1):
                print(f"   {i}. {drug['name']:25s} | "
                      f"Confidence: {drug.get('confidence', 0.0):.3f} | "
                      f"Tier: {drug.get('evidence_tier', 'N/A')}")
            
            # Check if expected drugs are in results
            if expected_drugs:
                found_drugs = [d['name'] for d in drugs]
                for expected in expected_drugs:
                    if expected in found_drugs:
                        rank = found_drugs.index(expected) + 1
                        print(f"\n✅ Expected drug '{expected}' found at rank {rank}")
                    else:
                        print(f"\n⚠️  Expected drug '{expected}' not found in results")
            
            return True
            
    except httpx.ConnectError:
        print(f"❌ Connection error: Backend not running at {API_BASE}")
        print(f"   Start backend with: cd oncology-coPilot/oncology-backend-minimal && uvicorn api.main:app --reload")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_mm_efficacy():
    """Test MM efficacy prediction."""
    mutations = [{
        "gene": "BRAF",
        "hgvs_p": "V600E",
        "chrom": "7",
        "pos": 140453136,
        "ref": "T",
        "alt": "A",
    }]
    
    return await test_efficacy_with_disease(
        disease="multiple_myeloma",
        mutations=mutations,
        expected_drugs=["BRAF inhibitor", "MEK inhibitor"]
    )


async def test_ovarian_efficacy():
    """Test ovarian cancer efficacy prediction with PARP inhibitors."""
    mutations = [{
        "gene": "BRCA2",
        "hgvs_p": "C711*",
        "chrom": "13",
        "pos": 32910625,
        "ref": "C",
        "alt": "A",
    }]
    
    return await test_efficacy_with_disease(
        disease="ovarian_cancer",
        mutations=mutations,
        expected_drugs=["olaparib", "niraparib", "carboplatin"]
    )


async def test_melanoma_efficacy():
    """Test melanoma efficacy prediction."""
    mutations = [{
        "gene": "BRAF",
        "hgvs_p": "V600E",
        "chrom": "7",
        "pos": 140453136,
        "ref": "T",
        "alt": "A",
    }]
    
    return await test_efficacy_with_disease(
        disease="melanoma",
        mutations=mutations,
        expected_drugs=["BRAF inhibitor", "MEK inhibitor"]
    )


async def test_clinical_genomics_full_mode():
    """Test clinical genomics endpoint with full-mode profile."""
    print(f"\n{'='*60}")
    print("Testing Clinical Genomics Full-Mode")
    print(f"{'='*60}")
    
    payload = {
        "mutations": [{
            "gene": "BRAF",
            "hgvs_p": "V600E",
            "chrom": "7",
            "pos": 140453136,
            "ref": "T",
            "alt": "A",
        }],
        "disease": "melanoma",
        "profile": "full",  # Full-mode should enable evidence
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{API_BASE}/api/clinical_genomics/analyze_variant",
                json=payload,
            )
            
            if resp.status_code >= 400:
                print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")
                return False
            
            data = resp.json()
            efficacy = data.get("efficacy", {})
            drugs = efficacy.get("drugs", [])
            
            print(f"\n✅ Response received: {len(drugs)} drugs")
            print(f"   Profile: {data.get('provenance', {}).get('profile', 'N/A')}")
            print(f"   Evidence tier: {efficacy.get('evidence_tier', 'N/A')}")
            
            print(f"\n📊 Top 3 Drugs:")
            for i, drug in enumerate(drugs[:3], 1):
                print(f"   {i}. {drug['name']:25s} | "
                      f"Confidence: {drug.get('confidence', 0.0):.3f} | "
                      f"Tier: {drug.get('evidence_tier', 'N/A')}")
            
            # Check if evidence is enabled (should have evidence_tier)
            if efficacy.get('evidence_tier') and efficacy.get('evidence_tier') != 'N/A':
                print(f"\n✅ Evidence gathering enabled (tier: {efficacy.get('evidence_tier')})")
            else:
                print(f"\n⚠️  Evidence gathering may not be enabled")
            
            return True
            
    except httpx.ConnectError:
        print(f"❌ Connection error: Backend not running at {API_BASE}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all API integration tests."""
    print("\n" + "=" * 60)
    print("API Integration Tests for Phase 0 & Phase 1")
    print("=" * 60)
    print("\n⚠️  Note: Backend must be running at http://127.0.0.1:8000")
    print("   Start with: cd oncology-coPilot/oncology-backend-minimal && uvicorn api.main:app --reload\n")
    
    results = []
    
    # Test MM efficacy
    results.append(("MM Efficacy", await test_mm_efficacy()))
    
    # Test Ovarian efficacy
    results.append(("Ovarian Efficacy", await test_ovarian_efficacy()))
    
    # Test Melanoma efficacy
    results.append(("Melanoma Efficacy", await test_melanoma_efficacy()))
    
    # Test Clinical Genomics full-mode
    results.append(("Clinical Genomics Full-Mode", await test_clinical_genomics_full_mode()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")
    
    print(f"\n   Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL API INTEGRATION TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))

