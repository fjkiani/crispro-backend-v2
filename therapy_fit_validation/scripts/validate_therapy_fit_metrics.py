#!/usr/bin/env python3
"""
Metric Validation Script for Therapy Fit

DEMO METRIC CHECKS (NOT OUTCOME VALIDATION)
------------------------------------------
This script checks that the endpoint returns a sane structure and that pathway
scores / rankings are non-empty for a few hand-picked mutation profiles.

It is **not** outcome-linked validation. Do not use its output to claim clinical
benefit or calibrated confidence levels.

For outcome-linked validation using real TCGA-OV platinum response labels, use:
`validate_therapy_fit_tcga_ov_platinum.py` (emits receipts under receipts/latest/).

Deliverable #2: Metric Validation Script
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
TIMEOUT = 300.0


# Documented Metrics (from therapy_fit_contribution.mdc)
DOCUMENTED_METRICS = {
    "multiple_myeloma": {
        "pathway_alignment": {
            "description": "5 MAPK variants → 100% pathway alignment",
            "expected": 1.0,
            "tolerance": 0.05  # Allow 5% tolerance
        },
        "confidence_ranges": {
            "RAS_pathway": {
                "min": 0.83,
                "max": 0.85
            }
        },
        "drug_rankings": {
            "KRAS_G12D": {
                "expected_top_drug": "MEK inhibitor",
                "expected_rank": 1
            }
        },
        "evidence_tiers": {
            "3_of_4_mutations": "supported",
            "2_of_4_mutations": "consider"
        }
    },
    "ovarian_cancer": {
        "pathway_alignment": {
            "description": "MBD4+TP53 → DDR pathway alignment",
            "expected": 0.8,  # High DDR alignment
            "tolerance": 0.1
        },
        "drug_rankings": {
            "MBD4_TP53": {
                "expected_top_drug": "PARP inhibitor",
                "expected_rank": 1
            }
        }
    }
}


# Test Cases for Metric Validation
METRIC_TEST_CASES = [
    {
        "name": "Multiple Myeloma - 5 MAPK Variants",
        "disease": "multiple_myeloma",
        "mutations": [
            {"gene": "KRAS", "hgvs_p": "p.G12D", "chrom": "12", "pos": 25398284, "ref": "G", "alt": "A"},
            {"gene": "NRAS", "hgvs_p": "p.Q61K", "chrom": "1", "pos": 115258747, "ref": "C", "alt": "A"},
            {"gene": "BRAF", "hgvs_p": "p.V600E", "chrom": "7", "pos": 140753336, "ref": "T", "alt": "A"},
            {"gene": "MAP2K1", "hgvs_p": "p.K57N", "chrom": "15", "pos": 66727460, "ref": "A", "alt": "T"},
            {"gene": "MAPK1", "hgvs_p": "p.E322K", "chrom": "22", "pos": 21227400, "ref": "G", "alt": "A"}
        ],
        "metrics_to_validate": [
            "pathway_alignment",
            "confidence_ranges",
            "drug_rankings",
            "evidence_tiers"
        ]
    },
    {
        "name": "Multiple Myeloma - KRAS G12D Single",
        "disease": "multiple_myeloma",
        "mutations": [
            {"gene": "KRAS", "hgvs_p": "p.G12D", "chrom": "12", "pos": 25398284, "ref": "G", "alt": "A"}
        ],
        "metrics_to_validate": [
            "drug_rankings",
            "confidence_ranges"
        ]
    },
    {
        "name": "Ovarian Cancer - MBD4+TP53",
        "disease": "ovarian_cancer",
        "mutations": [
            {"gene": "MBD4", "hgvs_p": "p.Q346*", "chrom": "3", "pos": 129149435, "ref": "C", "alt": "T"},
            {"gene": "TP53", "hgvs_p": "p.R273H", "chrom": "17", "pos": 7673802, "ref": "G", "alt": "A"}
        ],
        "metrics_to_validate": [
            "pathway_alignment",
            "drug_rankings"
        ]
    }
]


async def call_efficacy_predict(
    client: httpx.AsyncClient,
    mutations: List[Dict[str, Any]],
    disease: str
) -> Optional[Dict[str, Any]]:
    """Call /api/efficacy/predict endpoint."""
    url = f"{API_BASE_URL}/api/efficacy/predict"
    
    payload = {
        "model_id": "evo2_1b",
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
    except Exception as e:
        print(f"❌ Error calling API: {e}")
        return None


def calculate_pathway_alignment(response: Dict[str, Any], disease: str) -> float:
    """Calculate pathway alignment from response."""
    # Extract pathway scores from provenance
    if "provenance" not in response:
        return 0.0
    
    provenance = response["provenance"]
    if "confidence_breakdown" not in provenance:
        return 0.0
    
    breakdown = provenance["confidence_breakdown"]
    pathway_scores = breakdown.get("pathway_disruption", {})
    
    # For MM, check MAPK/RAS pathway
    if disease == "multiple_myeloma":
        mapk_score = pathway_scores.get("ras_mapk", 0.0)
        return mapk_score
    
    # For ovarian, check DDR pathway
    elif disease == "ovarian_cancer":
        ddr_score = pathway_scores.get("ddr", 0.0)
        return ddr_score
    
    return 0.0


def validate_metrics(response: Dict[str, Any], test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Validate metrics against documented expectations."""
    disease = test_case["disease"]
    documented = DOCUMENTED_METRICS.get(disease, {})
    
    results = {
        "pathway_alignment": {"passed": False, "actual": 0.0, "expected": 0.0, "error": None},
        "confidence_ranges": {"passed": False, "actual": None, "expected": None, "error": None},
        "drug_rankings": {"passed": False, "actual": None, "expected": None, "error": None},
        "evidence_tiers": {"passed": False, "actual": None, "expected": None, "error": None}
    }
    
    # Validate pathway alignment
    if "pathway_alignment" in test_case["metrics_to_validate"]:
        actual_alignment = calculate_pathway_alignment(response, disease)
        expected_metric = documented.get("pathway_alignment", {})
        expected_value = expected_metric.get("expected", 0.0)
        tolerance = expected_metric.get("tolerance", 0.1)
        
        results["pathway_alignment"] = {
            "passed": abs(actual_alignment - expected_value) <= tolerance,
            "actual": actual_alignment,
            "expected": expected_value,
            "tolerance": tolerance,
            "error": None if abs(actual_alignment - expected_value) <= tolerance else f"Alignment {actual_alignment:.3f} outside expected range [{expected_value - tolerance:.3f}, {expected_value + tolerance:.3f}]"
        }
    
    # Validate drug rankings
    if "drug_rankings" in test_case["metrics_to_validate"]:
        drugs = response.get("drugs", [])
        if drugs:
            top_drug = drugs[0]
            drug_name = top_drug.get("name", "").upper()
            
            # Check if top drug matches expected
            expected_drugs = documented.get("drug_rankings", {})
            for key, expected in expected_drugs.items():
                expected_name = expected.get("expected_top_drug", "").upper()
                if expected_name in drug_name or any(kw in drug_name for kw in expected_name.split()):
                    results["drug_rankings"] = {
                        "passed": True,
                        "actual": drug_name,
                        "expected": expected_name,
                        "error": None
                    }
                    break
            else:
                results["drug_rankings"] = {
                    "passed": False,
                    "actual": drug_name,
                    "expected": "MEK inhibitor or PARP inhibitor",
                    "error": f"Top drug '{drug_name}' doesn't match expected"
                }
        else:
            results["drug_rankings"] = {
                "passed": False,
                "actual": None,
                "expected": "At least one drug",
                "error": "No drugs returned"
            }
    
    # Validate confidence ranges
    if "confidence_ranges" in test_case["metrics_to_validate"]:
        drugs = response.get("drugs", [])
        if drugs:
            top_drug = drugs[0]
            confidence = top_drug.get("confidence", 0.0)
            
            expected_ranges = documented.get("confidence_ranges", {})
            if "RAS_pathway" in expected_ranges:
                expected_range = expected_ranges["RAS_pathway"]
                min_conf = expected_range["min"]
                max_conf = expected_range["max"]
                
                results["confidence_ranges"] = {
                    "passed": min_conf <= confidence <= max_conf,
                    "actual": confidence,
                    "expected": f"[{min_conf}, {max_conf}]",
                    "error": None if min_conf <= confidence <= max_conf else f"Confidence {confidence:.3f} outside expected range [{min_conf}, {max_conf}]"
                }
            else:
                results["confidence_ranges"] = {
                    "passed": True,  # No specific range to validate
                    "actual": confidence,
                    "expected": "Any valid range",
                    "error": None
                }
        else:
            results["confidence_ranges"] = {
                "passed": False,
                "actual": None,
                "expected": "Valid confidence score",
                "error": "No drugs to validate confidence"
            }
    
    # Validate evidence tiers
    if "evidence_tiers" in test_case["metrics_to_validate"]:
        drugs = response.get("drugs", [])
        if drugs:
            top_drug = drugs[0]
            evidence_tier = top_drug.get("evidence_tier", "").lower()
            
            # For MM with multiple MAPK mutations, should be "supported"
            if disease == "multiple_myeloma" and len(test_case["mutations"]) >= 3:
                expected_tier = "supported"
                results["evidence_tiers"] = {
                    "passed": evidence_tier == expected_tier,
                    "actual": evidence_tier,
                    "expected": expected_tier,
                    "error": None if evidence_tier == expected_tier else f"Evidence tier '{evidence_tier}' doesn't match expected '{expected_tier}'"
                }
            else:
                results["evidence_tiers"] = {
                    "passed": True,  # No specific tier to validate
                    "actual": evidence_tier,
                    "expected": "Any valid tier",
                    "error": None
                }
        else:
            results["evidence_tiers"] = {
                "passed": False,
                "actual": None,
                "expected": "Valid evidence tier",
                "error": "No drugs to validate evidence tier"
            }
    
    return results


async def run_metric_validation():
    """Run metric validation for all test cases."""
    print("="*60)
    print("THERAPY FIT METRIC VALIDATION")
    print("="*60)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Cases: {len(METRIC_TEST_CASES)}")
    
    results = []
    
    async with httpx.AsyncClient() as client:
        for test_case in METRIC_TEST_CASES:
            print(f"\n{'='*60}")
            print(f"Testing: {test_case['name']}")
            print(f"{'='*60}")
            
            # Call API
            print("📡 Calling /api/efficacy/predict...")
            response = await call_efficacy_predict(
                client,
                test_case["mutations"],
                test_case["disease"]
            )
            
            if response is None:
                results.append({
                    "test_case": test_case["name"],
                    "status": "FAILED",
                    "error": "API call failed"
                })
                continue
            
            print("✅ Response received")
            
            # Validate metrics
            print("🔍 Validating metrics...")
            validation = validate_metrics(response, test_case)
            
            # Print results
            for metric_name, metric_result in validation.items():
                if metric_name in test_case["metrics_to_validate"]:
                    status = "✅" if metric_result["passed"] else "❌"
                    print(f"   {status} {metric_name}:")
                    print(f"      Actual: {metric_result.get('actual', 'N/A')}")
                    print(f"      Expected: {metric_result.get('expected', 'N/A')}")
                    if metric_result.get("error"):
                        print(f"      Error: {metric_result['error']}")
            
            # Determine overall status
            validated_metrics = [m for m in test_case["metrics_to_validate"]]
            passed_count = sum(1 for m in validated_metrics if validation[m]["passed"])
            all_passed = passed_count == len(validated_metrics)
            
            results.append({
                "test_case": test_case["name"],
                "status": "PASSED" if all_passed else "FAILED",
                "validation": validation,
                "passed_metrics": passed_count,
                "total_metrics": len(validated_metrics)
            })
    
    # Summary
    print("\n" + "="*60)
    print("METRIC VALIDATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results if r["status"] == "PASSED")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    
    print(f"\nTotal Tests: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    print("\nDetailed Results:")
    for result in results:
        status_icon = "✅" if result["status"] == "PASSED" else "❌"
        print(f"   {status_icon} {result['test_case']}")
        print(f"      Metrics: {result.get('passed_metrics', 0)}/{result.get('total_metrics', 0)} passed")
        if result["status"] == "FAILED":
            for metric_name, metric_result in result["validation"].items():
                if not metric_result["passed"] and metric_result.get("error"):
                    print(f"      - {metric_name}: {metric_result['error']}")
    
    # Save results
    output_file = Path(__file__).parent / "therapy_fit_metric_validation_results.json"
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "api_base_url": API_BASE_URL,
            "test_cases": len(METRIC_TEST_CASES),
            "passed": passed,
            "failed": failed,
            "results": results
        }, f, indent=2)
    
    print(f"\n📄 Results saved to: {output_file}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_metric_validation())
    sys.exit(exit_code)
