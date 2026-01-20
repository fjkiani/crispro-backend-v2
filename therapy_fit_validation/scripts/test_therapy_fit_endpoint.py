#!/usr/bin/env python3
"""
End-to-End Test Script for Therapy Fit Endpoint

Tests the /api/efficacy/predict endpoint with real requests.
Validates response structure, insights chips, S/P/E breakdown, and drug rankings.

Deliverable #1: Full Ownership - ZO
"""

import asyncio
import httpx
import json
import sys
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 300.0  # 5 minutes for Evo2 scoring


# Test Cases
TEST_CASES = [
    {
        "name": "Multiple Myeloma - KRAS G12D",
        "disease": "multiple_myeloma",
        "mutations": [
            {
                "gene": "KRAS",
                "hgvs_p": "p.G12D",
                "hgvs_c": "c.35G>A",
                "chrom": "12",
                "pos": 25398284,
                "ref": "G",
                "alt": "A",
                "consequence": "missense_variant"
            }
        ],
        "expected": {
            "top_drug_contains": ["MEK", "MEK inhibitor"],
            "min_confidence": 0.3,
            "max_confidence": 1.0,
            "has_insights": True,
            "has_spe_breakdown": True
        }
    },
    {
        "name": "Ovarian Cancer - MBD4+TP53",
        "disease": "ovarian_cancer",
        "mutations": [
            {
                "gene": "MBD4",
                "hgvs_p": "p.Q346*",
                "chrom": "3",
                "pos": 129149435,
                "ref": "C",
                "alt": "T",
                "consequence": "stop_gained"
            },
            {
                "gene": "TP53",
                "hgvs_p": "p.R273H",
                "chrom": "17",
                "pos": 7673802,
                "ref": "G",
                "alt": "A",
                "consequence": "missense_variant"
            }
        ],
        "expected": {
            "top_drug_contains": ["PARP", "olaparib", "niraparib"],
            "min_confidence": 0.3,
            "max_confidence": 1.0,
            "has_insights": True,
            "has_spe_breakdown": True
        }
    },
    {
        "name": "Melanoma - BRAF V600E",
        "disease": "melanoma",
        "mutations": [
            {
                "gene": "BRAF",
                "hgvs_p": "p.V600E",
                "hgvs_c": "c.1799T>A",
                "chrom": "7",
                "pos": 140753336,
                "ref": "T",
                "alt": "A",
                "consequence": "missense_variant"
            }
        ],
        "expected": {
            "top_drug_contains": ["BRAF", "BRAF inhibitor"],
            "min_confidence": 0.3,
            "max_confidence": 1.0,
            "has_insights": True,
            "has_spe_breakdown": True
        }
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
        print(f"❌ HTTP Error: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        print(f"❌ Error calling API: {e}")
        return None


def validate_response_structure(response: Dict[str, Any], test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Validate response structure and content."""
    results = {
        "has_drugs": False,
        "drugs_count": 0,
        "has_insights": False,
        "has_spe_breakdown": False,
        "confidence_valid": False,
        "evidence_tier_valid": False,
        "top_drug_match": False,
        "errors": []
    }
    
    # Check drugs exist
    if "drugs" not in response:
        results["errors"].append("Missing 'drugs' field in response")
        return results
    
    drugs = response.get("drugs", [])
    if not isinstance(drugs, list) or len(drugs) == 0:
        results["errors"].append("'drugs' field is empty or not a list")
        return results
    
    results["has_drugs"] = True
    results["drugs_count"] = len(drugs)
    
    # Check first drug structure
    top_drug = drugs[0]
    
    # Check required fields
    required_fields = ["name", "efficacy_score", "confidence", "evidence_tier"]
    for field in required_fields:
        if field not in top_drug:
            results["errors"].append(f"Missing required field '{field}' in top drug")
    
    # Check insights chips (this was the bug we fixed)
    if "insights" in top_drug:
        results["has_insights"] = True
        insights = top_drug["insights"]
        if isinstance(insights, dict) and len(insights) > 0:
            # Check for expected insight types
            expected_insights = ["functionality", "chromatin", "essentiality", "regulatory"]
            found_insights = [k for k in expected_insights if k in insights]
            if found_insights:
                results["has_insights"] = True
            else:
                results["errors"].append(f"Insights present but no expected keys found. Found: {list(insights.keys())}")
        else:
            results["errors"].append("Insights field exists but is empty or not a dict")
    else:
        results["errors"].append("Missing 'insights' field in top drug (BUG: This should be fixed!)")
    
    # Check S/P/E breakdown in provenance
    if "provenance" in response:
        provenance = response["provenance"]
        if "confidence_breakdown" in provenance:
            breakdown = provenance["confidence_breakdown"]
            spe_fields = ["S_contribution", "P_contribution", "E_contribution"]
            found_spe = [f for f in spe_fields if f in breakdown]
            if len(found_spe) >= 2:  # At least 2 of 3 should be present
                results["has_spe_breakdown"] = True
            else:
                results["errors"].append(f"S/P/E breakdown incomplete. Found: {found_spe}")
        else:
            results["errors"].append("Missing 'confidence_breakdown' in provenance")
    else:
        results["errors"].append("Missing 'provenance' field in response")
    
    # Validate confidence score
    confidence = top_drug.get("confidence", 0)
    expected = test_case["expected"]
    if isinstance(confidence, (int, float)) and expected["min_confidence"] <= confidence <= expected["max_confidence"]:
        results["confidence_valid"] = True
    else:
        results["errors"].append(f"Confidence {confidence} outside expected range [{expected['min_confidence']}, {expected['max_confidence']}]")
    
    # Validate evidence tier
    evidence_tier = top_drug.get("evidence_tier", "")
    valid_tiers = ["supported", "consider", "insufficient"]
    if evidence_tier.lower() in valid_tiers:
        results["evidence_tier_valid"] = True
    else:
        results["errors"].append(f"Invalid evidence_tier: {evidence_tier}")
    
    # Check top drug matches expected
    drug_name = top_drug.get("name", "").upper()
    expected_keywords = [kw.upper() for kw in expected["top_drug_contains"]]
    if any(kw in drug_name for kw in expected_keywords):
        results["top_drug_match"] = True
    else:
        results["errors"].append(f"Top drug '{drug_name}' doesn't match expected keywords: {expected['top_drug_contains']}")
    
    return results


async def run_test_case(test_case: Dict[str, Any], client: httpx.AsyncClient) -> Dict[str, Any]:
    """Run a single test case."""
    print(f"\n{'='*60}")
    print(f"Testing: {test_case['name']}")
    print(f"{'='*60}")
    print(f"Disease: {test_case['disease']}")
    print(f"Mutations: {len(test_case['mutations'])}")
    
    # Call API
    print("\n📡 Calling /api/efficacy/predict...")
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
            "status": "FAILED",
            "error": "API call failed",
            "elapsed_seconds": elapsed
        }
    
    print(f"✅ Response received ({elapsed:.2f}s)")
    print(f"   Drugs returned: {len(response.get('drugs', []))}")
    
    # Validate response
    print("\n🔍 Validating response...")
    validation = validate_response_structure(response, test_case)
    
    # Print validation results
    checks = [
        ("Has drugs", validation["has_drugs"]),
        ("Drugs count > 0", validation["drugs_count"] > 0),
        ("Has insights chips", validation["has_insights"]),
        ("Has S/P/E breakdown", validation["has_spe_breakdown"]),
        ("Confidence valid", validation["confidence_valid"]),
        ("Evidence tier valid", validation["evidence_tier_valid"]),
        ("Top drug matches expected", validation["top_drug_match"])
    ]
    
    for check_name, check_result in checks:
        status = "✅" if check_result else "❌"
        print(f"   {status} {check_name}")
    
    if validation["errors"]:
        print("\n⚠️  Errors found:")
        for error in validation["errors"]:
            print(f"   - {error}")
    
    # Print top drug details
    if validation["has_drugs"]:
        top_drug = response["drugs"][0]
        print(f"\n📊 Top Drug:")
        print(f"   Name: {top_drug.get('name', 'N/A')}")
        print(f"   Efficacy Score: {top_drug.get('efficacy_score', 'N/A')}")
        print(f"   Confidence: {top_drug.get('confidence', 'N/A')}")
        print(f"   Evidence Tier: {top_drug.get('evidence_tier', 'N/A')}")
        print(f"   Badges: {top_drug.get('badges', [])}")
        if "insights" in top_drug:
            print(f"   Insights: {list(top_drug['insights'].keys())}")
    
    # Determine overall status
    all_checks_passed = all([
        validation["has_drugs"],
        validation["has_insights"],
        validation["has_spe_breakdown"],
        validation["confidence_valid"],
        validation["evidence_tier_valid"],
        validation["top_drug_match"]
    ])
    
    return {
        "test_case": test_case["name"],
        "status": "PASSED" if all_checks_passed else "FAILED",
        "validation": validation,
        "elapsed_seconds": elapsed,
        "top_drug": response["drugs"][0] if validation["has_drugs"] else None
    }


async def main():
    """Run all test cases."""
    print("="*60)
    print("THERAPY FIT ENDPOINT TEST SUITE")
    print("="*60)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Cases: {len(TEST_CASES)}")
    print(f"Timeout: {TIMEOUT}s per request")
    
    results = []
    
    async with httpx.AsyncClient() as client:
        for test_case in TEST_CASES:
            result = await run_test_case(test_case, client)
            results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results if r["status"] == "PASSED")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    
    print(f"\nTotal Tests: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    print("\nDetailed Results:")
    for result in results:
        status_icon = "✅" if result["status"] == "PASSED" else "❌"
        print(f"   {status_icon} {result['test_case']} ({result.get('elapsed_seconds', 0):.2f}s)")
        if result["status"] == "FAILED" and "validation" in result:
            for error in result["validation"].get("errors", []):
                print(f"      - {error}")
    
    # Save results to file
    output_file = Path(__file__).parent / "therapy_fit_endpoint_test_results.json"
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "api_base_url": API_BASE_URL,
            "test_cases": len(TEST_CASES),
            "passed": passed,
            "failed": failed,
            "results": results
        }, f, indent=2)
    
    print(f"\n📄 Results saved to: {output_file}")
    
    # Exit code
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
