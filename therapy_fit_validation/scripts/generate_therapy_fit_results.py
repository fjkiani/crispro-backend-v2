#!/usr/bin/env python3
"""
Generate Therapy Fit Results from Test Cases

DEMO/SMOKE ONLY (NOT OUTCOME VALIDATION)
---------------------------------------
This script calls the real `/api/efficacy/predict` endpoint for a few hand-picked
mutation profiles so you can inspect response structure and ranking sanity.

It is **not** outcome-linked validation and must not be used to claim clinical
benefit. For outcome-linked validation on real TCGA-OV platinum labels, use:
`validate_therapy_fit_tcga_ov_platinum.py` (emits receipts under receipts/latest/).

Usage:
    python scripts/generate_therapy_fit_results.py
    python scripts/generate_therapy_fit_results.py --test-case AYESHA-001
    python scripts/generate_therapy_fit_results.py --all --output results.json
"""

import argparse
import asyncio
import httpx
import json
import sys
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 300.0  # 5 minutes for Evo2 scoring


# Demo test cases (hand-picked). These are not "expected outcome" assertions.
TEST_CASES = [
    {
        "name": "Ayesha (MBD4+TP53 HGSOC)",
        "patient_id": "AYESHA-001",
        "disease": "ovarian_cancer",
        "treatment_line": "1L",
        "mutations": [
            {
                "gene": "MBD4",
                "hgvs_p": "p.Q346*",
                "hgvs_c": "MBD4:c.1036C>T",
                "chrom": "3",
                "pos": 129149435,
                "ref": "C",
                "alt": "T",
                "consequence": "stop_gained",
                "vaf": 0.48,
                "zygosity": "heterozygous"
            },
            {
                "gene": "TP53",
                "hgvs_p": "p.R273H",
                "hgvs_c": "TP53:c.818G>A",
                "chrom": "17",
                "pos": 7673802,
                "ref": "G",
                "alt": "A",
                "consequence": "missense_variant",
                "vaf": 0.52,
                "zygosity": "heterozygous"
            }
        ],
        "expected": {}  # deprecated (do not use for validation)
    },
    {
        "name": "Multiple Myeloma Patient (KRAS G12D)",
        "patient_id": "MM-001",
        "disease": "multiple_myeloma",
        "treatment_line": "2L",
        "mutations": [
            {
                "gene": "KRAS",
                "hgvs_p": "p.G12D",
                "hgvs_c": "KRAS:c.35G>A",
                "chrom": "12",
                "pos": 25398284,
                "ref": "G",
                "alt": "A",
                "consequence": "missense_variant",
                "vaf": 0.45,
                "zygosity": "heterozygous"
            }
        ],
        "expected": {}  # deprecated (do not use for validation)
    },
    {
        "name": "Melanoma Patient (BRAF V600E)",
        "patient_id": "MEL-001",
        "disease": "melanoma",
        "treatment_line": "1L",
        "mutations": [
            {
                "gene": "BRAF",
                "hgvs_p": "p.V600E",
                "hgvs_c": "BRAF:c.1799T>A",
                "chrom": "7",
                "pos": 140753336,
                "ref": "T",
                "alt": "A",
                "consequence": "missense_variant",
                "vaf": 0.55,
                "zygosity": "heterozygous"
            }
        ],
        "expected": {}  # deprecated (do not use for validation)
    },
    {
        "name": "Ovarian Cancer Patient (BRCA1 Truncation)",
        "patient_id": "OV-002",
        "disease": "ovarian_cancer",
        "treatment_line": "1L",
        "mutations": [
            {
                "gene": "BRCA1",
                "hgvs_p": "p.E1685fs",
                "hgvs_c": "BRCA1:c.5053delA",
                "chrom": "17",
                "pos": 43057051,
                "ref": "A",
                "alt": "del",
                "consequence": "frameshift_variant",
                "vaf": 0.48,
                "zygosity": "heterozygous"
            }
        ],
        "expected": {}  # deprecated (do not use for validation)
    },
    {
        "name": "Multiple Myeloma Patient (5 MAPK Variants)",
        "patient_id": "MM-002",
        "disease": "multiple_myeloma",
        "treatment_line": "1L",
        "mutations": [
            {
                "gene": "KRAS",
                "hgvs_p": "p.G12D",
                "hgvs_c": "KRAS:c.35G>A",
                "chrom": "12",
                "pos": 25398284,
                "ref": "G",
                "alt": "A",
                "consequence": "missense_variant",
                "vaf": 0.45
            },
            {
                "gene": "NRAS",
                "hgvs_p": "p.Q61K",
                "hgvs_c": "NRAS:c.181C>A",
                "chrom": "1",
                "pos": 115258747,
                "ref": "C",
                "alt": "A",
                "consequence": "missense_variant",
                "vaf": 0.38
            },
            {
                "gene": "BRAF",
                "hgvs_p": "p.V600E",
                "hgvs_c": "BRAF:c.1799T>A",
                "chrom": "7",
                "pos": 140753336,
                "ref": "T",
                "alt": "A",
                "consequence": "missense_variant",
                "vaf": 0.42
            },
            {
                "gene": "MAP2K1",
                "hgvs_p": "p.K57N",
                "hgvs_c": "MAP2K1:c.171A>T",
                "chrom": "15",
                "pos": 66727460,
                "ref": "A",
                "alt": "T",
                "consequence": "missense_variant",
                "vaf": 0.35
            },
            {
                "gene": "MAPK1",
                "hgvs_p": "p.E322K",
                "hgvs_c": "MAPK1:c.964G>A",
                "chrom": "22",
                "pos": 21227400,
                "ref": "G",
                "alt": "A",
                "consequence": "missense_variant",
                "vaf": 0.28
            }
        ],
        "expected": {}  # deprecated (do not use for validation)
    }
]


async def call_efficacy_predict(
    client: httpx.AsyncClient,
    mutations: List[Dict[str, Any]],
    disease: str,
    model_id: str = "evo2_1b"
) -> Optional[Dict[str, Any]]:
    """Call /api/efficacy/predict endpoint."""
    url = f"{API_BASE_URL}/api/efficacy/predict"
    
    payload = {
        "model_id": model_id,
        "mutations": mutations,
        "disease": disease,
        "options": {
            "adaptive": True,
            "ensemble": False
        }
    }
    
    try:
        response = await client.post(url, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   Response: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ Error calling API: {e}")
        return None


def extract_pathway_scores(response: Dict[str, Any]) -> Dict[str, float]:
    """Extract pathway scores from response."""
    pathway_scores = {}
    
    if "provenance" in response:
        provenance = response["provenance"]
        if "confidence_breakdown" in provenance:
            breakdown = provenance["confidence_breakdown"]
            pathway_disruption = breakdown.get("pathway_disruption", {})
            
            # Map to standard pathway names
            pathway_mapping = {
                "ddr": "DDR",
                "ras_mapk": "RAS/MAPK",
                "mapk": "RAS/MAPK",
                "pi3k": "PI3K",
                "vegf": "VEGF",
                "her2": "HER2"
            }
            
            for key, value in pathway_disruption.items():
                pathway_name = pathway_mapping.get(key.lower(), key)
                pathway_scores[pathway_name] = float(value) if value is not None else 0.0
    
    return pathway_scores


def format_results(response: Dict[str, Any], test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Format results for display and comparison."""
    drugs = response.get("drugs", [])
    
    result = {
        "test_case": test_case["name"],
        "patient_id": test_case["patient_id"],
        "disease": test_case["disease"],
        "mutations_count": len(test_case["mutations"]),
        "drugs_returned": len(drugs),
        "top_drugs": [],
        "pathway_scores": extract_pathway_scores(response),
        "comparison": {}
    }
    
    # Top 3 drugs
    for i, drug in enumerate(drugs[:3], 1):
        result["top_drugs"].append({
            "rank": i,
            "name": drug.get("name", "N/A"),
            "efficacy_score": drug.get("efficacy_score", 0.0),
            "confidence": drug.get("confidence", 0.0),
            "evidence_tier": drug.get("evidence_tier", "N/A"),
            "badges": drug.get("badges", []),
            "has_insights": "insights" in drug and len(drug.get("insights", {})) > 0
        })
    
    # Compare to expected
    if drugs and "expected" in test_case:
        expected = test_case["expected"]
        top_drug = drugs[0]
        
        # Top drug match
        actual_name = top_drug.get("name", "").upper()
        expected_name = expected.get("top_drug", "").upper()
        result["comparison"]["top_drug_match"] = expected_name in actual_name or any(
            word in actual_name for word in expected_name.split() if len(word) > 3
        )
        
        # Confidence range
        confidence = top_drug.get("confidence", 0.0)
        if "confidence_min" in expected and "confidence_max" in expected:
            result["comparison"]["confidence_in_range"] = (
                expected["confidence_min"] <= confidence <= expected["confidence_max"]
            )
            result["comparison"]["confidence_actual"] = confidence
            result["comparison"]["confidence_expected"] = f"[{expected['confidence_min']}, {expected['confidence_max']}]"
        
        # Evidence tier
        actual_tier = top_drug.get("evidence_tier", "").lower()
        expected_tier = expected.get("evidence_tier", "").lower()
        result["comparison"]["evidence_tier_match"] = actual_tier == expected_tier
        result["comparison"]["evidence_tier_actual"] = actual_tier
        result["comparison"]["evidence_tier_expected"] = expected_tier
        
        # Pathway alignment
        if "pathway_alignment" in expected:
            result["comparison"]["pathway_alignment"] = {}
            for pathway_name, expected_range in expected["pathway_alignment"].items():
                actual_score = result["pathway_scores"].get(pathway_name, 0.0)
                # Try to find matching pathway
                for key, value in result["pathway_scores"].items():
                    if pathway_name.lower() in key.lower() or key.lower() in pathway_name.lower():
                        actual_score = value
                        break
                
                in_range = expected_range["min"] <= actual_score <= expected_range["max"]
                result["comparison"]["pathway_alignment"][pathway_name] = {
                    "passed": in_range,
                    "actual": actual_score,
                    "expected": f"[{expected_range['min']}, {expected_range['max']}]"
                }
    
    return result


async def run_test_case(test_case: Dict[str, Any], client: httpx.AsyncClient) -> Dict[str, Any]:
    """Run a single test case and return formatted results."""
    print(f"\n{'='*60}")
    print(f"Test Case: {test_case['name']}")
    print(f"Patient ID: {test_case['patient_id']}")
    print(f"Disease: {test_case['disease']}")
    print(f"Mutations: {len(test_case['mutations'])}")
    for i, mut in enumerate(test_case['mutations'], 1):
        print(f"  {i}. {mut.get('gene', 'N/A')} {mut.get('hgvs_p', 'N/A')}")
    print(f"{'='*60}")
    
    # Call API
    print(f"\n📡 Calling /api/efficacy/predict...")
    start_time = datetime.now()
    response = await call_efficacy_predict(
        client,
        test_case["mutations"],
        test_case["disease"]
    )
    elapsed = (datetime.now() - start_time).total_seconds()
    
    if response is None:
        return {
            "test_case": test_case["name"],
            "patient_id": test_case["patient_id"],
            "status": "FAILED",
            "error": "API call failed",
            "elapsed_seconds": elapsed
        }
    
    print(f"✅ Response received ({elapsed:.2f}s)")
    
    # Format results
    formatted = format_results(response, test_case)
    formatted["elapsed_seconds"] = elapsed
    formatted["status"] = "SUCCESS"
    
    # Display results
    if formatted["top_drugs"]:
        print(f"\n📊 Top Drugs:")
        for drug in formatted["top_drugs"]:
            print(f"   {drug['rank']}. {drug['name']}")
            print(f"      Efficacy: {drug['efficacy_score']:.3f}")
            print(f"      Confidence: {drug['confidence']:.3f}")
            print(f"      Tier: {drug['evidence_tier']}")
            print(f"      Badges: {drug['badges']}")
            print(f"      Insights: {'✅' if drug['has_insights'] else '❌'}")
    
    # Pathway scores
    if formatted["pathway_scores"]:
        print(f"\n🛤️  Pathway Scores:")
        for pathway, score in formatted["pathway_scores"].items():
            print(f"   {pathway}: {score:.3f}")
    
    # Comparison
    if formatted["comparison"]:
        print(f"\n🔍 Comparison to Expected:")
        comp = formatted["comparison"]
        
        if "top_drug_match" in comp:
            status = "✅" if comp["top_drug_match"] else "❌"
            print(f"   {status} Top Drug Match: {comp['top_drug_match']}")
        
        if "confidence_in_range" in comp:
            status = "✅" if comp["confidence_in_range"] else "❌"
            print(f"   {status} Confidence: {comp.get('confidence_actual', 'N/A'):.3f} (expected {comp.get('confidence_expected', 'N/A')})")
        
        if "evidence_tier_match" in comp:
            status = "✅" if comp["evidence_tier_match"] else "❌"
            print(f"   {status} Evidence Tier: {comp.get('evidence_tier_actual', 'N/A')} (expected {comp.get('evidence_tier_expected', 'N/A')})")
        
        if "pathway_alignment" in comp:
            print(f"   Pathway Alignment:")
            for pathway, check in comp["pathway_alignment"].items():
                status = "✅" if check["passed"] else "❌"
                print(f"      {status} {pathway}: {check['actual']:.3f} (expected {check['expected']})")
    
    return formatted


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Generate Therapy Fit results from test cases")
    parser.add_argument("--test-case", type=str, help="Run specific test case by patient ID (e.g., AYESHA-001)")
    parser.add_argument("--all", action="store_true", help="Run all test cases")
    parser.add_argument("--output", type=str, default="therapy_fit_generated_results.json", help="Output JSON file")
    args = parser.parse_args()
    
    print("="*60)
    print("THERAPY FIT TEST CASES - RESULT GENERATOR")
    print("="*60)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Cases Available: {len(TEST_CASES)}")
    
    # Filter test cases
    test_cases_to_run = TEST_CASES
    if args.test_case:
        test_cases_to_run = [tc for tc in TEST_CASES if tc["patient_id"] == args.test_case]
        if not test_cases_to_run:
            print(f"❌ Test case '{args.test_case}' not found")
            print(f"   Available IDs: {[tc['patient_id'] for tc in TEST_CASES]}")
            sys.exit(1)
    
    if not args.test_case and not args.all:
        print("\n⚠️  No test case specified. Use --test-case <ID> or --all")
        print(f"   Available IDs: {[tc['patient_id'] for tc in TEST_CASES]}")
        sys.exit(1)
    
    print(f"\n📋 Running {len(test_cases_to_run)} test case(s)...")
    
    # Run test cases
    results = []
    
    async with httpx.AsyncClient() as client:
        for test_case in test_cases_to_run:
            result = await run_test_case(test_case, client)
            results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    successful = sum(1 for r in results if r.get("status") == "SUCCESS")
    failed = len(results) - successful
    
    print(f"\nTotal Tests: {len(results)}")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    
    # Save results
    output_path = Path(__file__).parent / args.output
    with open(output_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "api_base_url": API_BASE_URL,
            "test_cases_run": len(results),
            "successful": successful,
            "failed": failed,
            "results": results
        }, f, indent=2)
    
    print(f"\n📄 Results saved to: {output_path}")
    print(f"\n💡 Next Steps:")
    print(f"   1. Review results in: {output_path}")
    print(f"   2. Compare actual vs. expected results")
    print(f"   3. Update THERAPY_FIT_TEST_CASES.md with actual results if needed")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

