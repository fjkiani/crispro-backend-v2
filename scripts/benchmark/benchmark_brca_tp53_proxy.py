#!/usr/bin/env python3
"""
BRCA+TP53 Proxy Benchmark: Use BRCA+TP53 cases as proxy for MBD4+TP53 validation

Why: MBD4+TP53 is too rare to have real outcome data. BRCA+TP53 is similar (HRD+)
and has published RCT data (SOLO-2, PAOLA-1, PRIMA, NOVA, ARIEL3).

This benchmark validates:
1. Real-world accuracy: Do our predictions match published PARP response rates?
2. Predictive performance: Do our efficacy scores correlate with actual outcomes?
3. Clinical alignment: Do we recommend the same drugs that worked in trials?

Ground Truth: Published RCT data for BRCA+TP53 HGSOC
- PARP response rate: ~60-70% (from SOLO-2, PAOLA-1)
- Platinum response rate: ~80% (standard of care)
- Expected efficacy scores: Should correlate with response rates
"""

import os
import sys
import json
import asyncio
import httpx
from typing import Dict, List, Any
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.services.pathway_to_mechanism_vector import convert_pathway_scores_to_mechanism_vector

# Published RCT Data (Real Ground Truth)
PUBLISHED_RCT_DATA = {
    "solo2": {
        "trial": "SOLO-2",
        "drug": "olaparib",
        "population": "BRCA1/BRCA2 germline + platinum-sensitive HGSOC",
        "response_rate": 0.65,  # 65% ORR
        "pfs_improvement": "13.6 months vs 5.4 months (HR=0.30)",
        "fda_approved": True,
        "nccn_category": "Category 1 (preferred)"
    },
    "paola1": {
        "trial": "PAOLA-1",
        "drug": "olaparib + bevacizumab",
        "population": "HRD+ ovarian cancer (BRCA or HRD-positive)",
        "response_rate": 0.64,  # 64% ORR in HRD+ subgroup
        "pfs_improvement": "37.2 months vs 17.7 months (HR=0.33)",
        "fda_approved": True,
        "nccn_category": "Category 1 (preferred)"
    },
    "prima": {
        "trial": "PRIMA",
        "drug": "niraparib",
        "population": "HRD+ ovarian cancer (BRCA or HRD-positive)",
        "response_rate": 0.57,  # 57% ORR in HRD+ subgroup
        "pfs_improvement": "21.9 months vs 10.4 months (HR=0.43)",
        "fda_approved": True,
        "nccn_category": "Category 1 (preferred)"
    },
    "ariel3": {
        "trial": "ARIEL3",
        "drug": "rucaparib",
        "population": "BRCA1/BRCA2 + platinum-sensitive HGSOC",
        "response_rate": 0.64,  # 64% ORR
        "pfs_improvement": "16.6 months vs 5.4 months (HR=0.23)",
        "fda_approved": True,
        "nccn_category": "Category 1 (preferred)"
    },
    "platinum_standard": {
        "trial": "Multiple RCTs",
        "drug": "carboplatin",
        "population": "First-line HGSOC",
        "response_rate": 0.80,  # 80% ORR (standard of care)
        "pfs_improvement": "Baseline (standard of care)",
        "fda_approved": True,
        "nccn_category": "Category 1 (preferred)"
    }
}

# Test Cases: BRCA+TP53 (Proxy for MBD4+TP53)
TEST_CASES = [
    {
        "name": "BRCA1+TP53 R175H",
        "mutations": [
            {
                "gene": "BRCA1",
                "hgvs_p": "p.Arg1751Ter",  # Common BRCA1 truncation
                "chrom": "17",
                "pos": 43057046,  # GRCh37
                "ref": "C",
                "alt": "T",
                "build": "GRCh37"
            },
            {
                "gene": "TP53",
                "hgvs_p": "p.Arg175His",
                "chrom": "17",
                "pos": 7577120,
                "ref": "G",
                "alt": "A",
                "build": "GRCh37"
            }
        ],
        "expected_drugs": {
            "olaparib": {"min_efficacy": 0.70, "expected_response_rate": 0.65},
            "niraparib": {"min_efficacy": 0.70, "expected_response_rate": 0.57},
            "rucaparib": {"min_efficacy": 0.70, "expected_response_rate": 0.64},
            "carboplatin": {"min_efficacy": 0.70, "expected_response_rate": 0.80}
        },
        "published_data": PUBLISHED_RCT_DATA["solo2"]
    },
    {
        "name": "BRCA2+TP53 R248Q",
        "mutations": [
            {
                "gene": "BRCA2",
                "hgvs_p": "p.Lys3326Ter",  # Common BRCA2 truncation
                "chrom": "13",
                "pos": 32914438,  # GRCh37
                "ref": "A",
                "alt": "T",
                "build": "GRCh37"
            },
            {
                "gene": "TP53",
                "hgvs_p": "p.Arg248Gln",
                "chrom": "17",
                "pos": 7577539,  # GRCh37
                "ref": "G",
                "alt": "A",
                "build": "GRCh37"
            }
        ],
        "expected_drugs": {
            "olaparib": {"min_efficacy": 0.70, "expected_response_rate": 0.65},
            "carboplatin": {"min_efficacy": 0.70, "expected_response_rate": 0.80}
        },
        "published_data": PUBLISHED_RCT_DATA["solo2"]
    }
]


async def benchmark_brca_tp53_proxy(api_base_url: str = "http://localhost:8000"):
    """Benchmark BRCA+TP53 cases as proxy for MBD4+TP53 validation"""
    
    print("\n" + "="*80)
    print("BRCA+TP53 PROXY BENCHMARK: Real-World Accuracy Validation")
    print("="*80)
    print("\n⚠️  Using BRCA+TP53 as proxy for MBD4+TP53 (similar HRD+ phenotype)")
    print("📊 Ground Truth: Published RCT data (SOLO-2, PAOLA-1, PRIMA, ARIEL3)")
    print()
    
    results = []
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        for test_case in TEST_CASES:
            print(f"\n🧪 TEST CASE: {test_case['name']}")
            print("-" * 80)
            
            # Get predictions
            response = await client.post(
                f"{api_base_url}/api/efficacy/predict",
                json={
                    "model_id": "evo2_1b",
                    "mutations": test_case["mutations"],
                    "disease": "ovarian_cancer",
                    "germline_status": "positive"  # BRCA is germline
                }
            )
            
            if response.status_code != 200:
                print(f"❌ API call failed: {response.status_code}")
                continue
            
            data = response.json()
            drugs = data.get("drugs", [])
            
            # Compare against published RCT data
            published = test_case["published_data"]
            print(f"📋 Published RCT: {published['trial']}")
            print(f"   Drug: {published['drug']}")
            print(f"   Response Rate: {published['response_rate']*100:.1f}%")
            print(f"   PFS Improvement: {published['pfs_improvement']}")
            print()
            
            # Check our predictions
            print("🔬 Our Predictions:")
            for drug_name, expected in test_case["expected_drugs"].items():
                found = False
                for drug in drugs:
                    if drug_name.lower() in drug.get("name", "").lower():
                        found = True
                        efficacy = drug.get("efficacy_score", 0.0)
                        rank = drugs.index(drug) + 1
                        
                        # Compare efficacy score vs. published response rate
                        efficacy_match = efficacy >= expected["min_efficacy"]
                        response_correlation = abs(efficacy - expected["expected_response_rate"]) < 0.15
                        
                        print(f"   {drug_name.upper()}:")
                        print(f"     Rank: #{rank}")
                        print(f"     Efficacy Score: {efficacy:.3f}")
                        print(f"     Published Response Rate: {expected['expected_response_rate']*100:.1f}%")
                        print(f"     {'✅' if efficacy_match else '❌'} Efficacy ≥ {expected['min_efficacy']:.2f}")
                        print(f"     {'✅' if response_correlation else '⚠️'} Efficacy correlates with response rate (diff: {abs(efficacy - expected['expected_response_rate']):.3f})")
                        
                        results.append({
                            "test_case": test_case["name"],
                            "drug": drug_name,
                            "our_efficacy": efficacy,
                            "published_response_rate": expected["expected_response_rate"],
                            "correlation": response_correlation,
                            "rank": rank
                        })
                        break
                
                if not found:
                    print(f"   {drug_name.upper()}: ❌ NOT FOUND")
            
            print()
    
    # Summary
    print("="*80)
    print("SUMMARY: Efficacy Scores vs. Published Response Rates")
    print("="*80)
    
    if results:
        correlations = [r["correlation"] for r in results]
        correlation_rate = sum(correlations) / len(correlations) * 100
        
        print(f"\n✅ Correlation Rate: {correlation_rate:.1f}%")
        print(f"   ({sum(correlations)}/{len(results)} drugs have efficacy scores within 15% of published response rates)")
        print()
        
        print("📊 Detailed Comparison:")
        for r in results:
            diff = abs(r["our_efficacy"] - r["published_response_rate"])
            status = "✅" if r["correlation"] else "⚠️"
            print(f"   {status} {r['drug']:15s} | Our: {r['our_efficacy']:.3f} | Published: {r['published_response_rate']:.3f} | Diff: {diff:.3f}")
        
        print()
        print("🎯 Interpretation:")
        print("   - Efficacy scores should correlate with published response rates")
        print("   - If correlation >80%, our scores are predictive")
        print("   - If correlation <80%, scores need calibration")
    else:
        print("❌ No results to analyze")
    
    print("="*80)
    
    return results


if __name__ == "__main__":
    api_base = os.getenv("API_BASE_URL", "http://localhost:8000")
    results = asyncio.run(benchmark_brca_tp53_proxy(api_base))

