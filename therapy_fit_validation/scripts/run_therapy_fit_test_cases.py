#!/usr/bin/env python3
"""
Run Therapy Fit Test Cases

Loads test cases from THERAPY_FIT_TEST_CASES.md and runs them against the API.
Generates actual results that can be compared to expected results.

Usage:
    python scripts/run_therapy_fit_test_cases.py
    python scripts/run_therapy_fit_test_cases.py --test-case AYESHA-001
    python scripts/run_therapy_fit_test_cases.py --all
"""

import asyncio
import httpx
import json
import sys
import re
import argparse
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 300.0  # 5 minutes for Evo2 scoring

# Path to test cases document - try multiple possible locations
def find_test_cases_file() -> Path:
    """Find the test cases file in various possible locations."""
    possible_paths = [
        Path(__file__).parent.parent.parent / ".cursor" / "MOAT" / "THERAPY_FIT_TEST_CASES.md",
        Path(__file__).parent.parent / ".cursor" / "MOAT" / "THERAPY_FIT_TEST_CASES.md",
        Path(__file__).parent.parent.parent.parent / ".cursor" / "MOAT" / "THERAPY_FIT_TEST_CASES.md",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    # If not found, return the most likely path
    return possible_paths[0]


def parse_test_cases_from_markdown(file_path: Path) -> List[Dict[str, Any]]:
    """Parse test cases from markdown file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    test_cases = []
    
    # Find all test case sections - improved regex
    # Pattern: ### Test Case N: Name\n\n**Patient ID:** ID\n**Disease:** Disease\n**Treatment Line:** Line\n\n**Mutations:**\n```json\n[...]\n```
    pattern = r'### Test Case \d+: (.+?)\n\n\*\*Patient ID:\*\* (.+?)\n\*\*Disease:\*\* (.+?)\n\*\*Treatment Line:\*\* (.+?)\n\n\*\*Mutations:\*\n```json\n(.*?)\n```'
    
    matches = list(re.finditer(pattern, content, re.DOTALL))
    
    if not matches:
        # Try alternative pattern
        pattern = r'### Test Case \d+: (.+?)\*\*Patient ID:\*\* (.+?)\*\*Disease:\*\* (.+?)\*\*Treatment Line:\*\* (.+?)\*\*Mutations:\*\*```json\n(.*?)\n```'
        matches = list(re.finditer(pattern, content, re.DOTALL))
    
    for match in matches:
        name = match.group(1).strip()
        patient_id = match.group(2).strip()
        disease = match.group(3).strip()
        treatment_line = match.group(4).strip()
        mutations_json = match.group(5).strip()
        
        try:
            mutations = json.loads(mutations_json)
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing mutations for {patient_id}: {e}")
            print(f"   JSON snippet: {mutations_json[:200]}...")
            continue
        
        # Extract expected results - find section after mutations
        expected = {}
        section_start = match.end()
        section_end = min(section_start + 5000, len(content))
        section_content = content[section_start:section_end]
        
        # Find expected top drug
        top_drug_match = re.search(r'\*\*Top Drug Rankings:\*\*\s+1\. \*\*(.+?)\*\*', section_content, re.DOTALL)
        if top_drug_match:
            expected["top_drug"] = top_drug_match.group(1).strip()
        
        # Find expected confidence range
        confidence_match = re.search(r'Expected Confidence: ([\d.]+)-([\d.]+)', section_content)
        if confidence_match:
            expected["confidence_min"] = float(confidence_match.group(1))
            expected["confidence_max"] = float(confidence_match.group(2))
        
        # Find expected evidence tier
        tier_match = re.search(r'Expected Evidence Tier: "(.+?)"', section_content)
        if tier_match:
            expected["evidence_tier"] = tier_match.group(1)
        
        # Find pathway alignment expectations
        pathway_matches = re.findall(r'- (.+?) pathway: Expected ([\d.]+)-?([\d.]+)?', section_content)
        expected["pathway_alignment"] = {}
        for pathway_match in pathway_matches:
            pathway_name = pathway_match[0].strip()
            min_val = float(pathway_match[1])
            max_val = float(pathway_match[2]) if pathway_match[2] else min_val
            expected["pathway_alignment"][pathway_name] = {"min": min_val, "max": max_val}
        
        test_cases.append({
            "name": name,
            "patient_id": patient_id,
            "disease": disease,
            "treatment_line": treatment_line,
            "mutations": mutations,
            "expected": expected
        })
    
    return test_cases


async def call_efficacy_predict(
    client: httpx.AsyncClient,
    mutations: List[Dict[str, Any]],
    disease: str,
    model_id: str = "evo2_1b"
) -> Optional[Dict[str, Any]]:
    """Call /api/efficacy/predict endpoint."""
    url = f"{API_BASE_URL}/api/efficacy/predict"
    
    # Normalize disease name
    disease_map = {
        "Ovarian Cancer (High-Grade Serous Ovarian Carcinoma - HGSOC)": "ovarian_cancer",
        "Ovarian Cancer (High-Grade Serous)": "ovarian_cancer",
        "Multiple Myeloma": "multiple_myeloma",
        "Melanoma": "melanoma"
    }
    disease_normalized = disease_map.get(disease, disease.lower().replace(" ", "_"))
    
    payload = {
        "model_id": model_id,
        "mutations": mutations,
        "disease": disease_normalized,
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


def compare_results(actual: Dict[str, Any], expected: Dict[str, Any], test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Compare actual results to expected results."""
    comparison = {
        "test_case": test_case["name"],
        "patient_id": test_case["patient_id"],
        "passed": True,
        "checks": {},
        "errors": []
    }
    
    drugs = actual.get("drugs", [])
    if not drugs:
        comparison["passed"] = False
        comparison["errors"].append("No drugs returned")
        return comparison
    
    top_drug = drugs[0]
    
    # Check top drug matches expected
    if "top_drug" in expected:
        drug_name = top_drug.get("name", "").upper()
        expected_name = expected["top_drug"].upper()
        
        # Check if expected drug name appears in actual drug name
        match = any(keyword in drug_name for keyword in expected_name.split())
        comparison["checks"]["top_drug_match"] = {
            "passed": match,
            "actual": drug_name,
            "expected": expected_name
        }
        if not match:
            comparison["passed"] = False
            comparison["errors"].append(f"Top drug '{drug_name}' doesn't match expected '{expected_name}'")
    
    # Check confidence range
    if "confidence_min" in expected and "confidence_max" in expected:
        confidence = top_drug.get("confidence", 0.0)
        in_range = expected["confidence_min"] <= confidence <= expected["confidence_max"]
        comparison["checks"]["confidence_range"] = {
            "passed": in_range,
            "actual": confidence,
            "expected": f"[{expected['confidence_min']}, {expected['confidence_max']}]"
        }
        if not in_range:
            comparison["passed"] = False
            comparison["errors"].append(f"Confidence {confidence:.3f} outside expected range [{expected['confidence_min']}, {expected['confidence_max']}]")
    
    # Check evidence tier
    if "evidence_tier" in expected:
        actual_tier = top_drug.get("evidence_tier", "").lower()
        expected_tier = expected["evidence_tier"].lower()
        tier_match = actual_tier == expected_tier
        comparison["checks"]["evidence_tier"] = {
            "passed": tier_match,
            "actual": actual_tier,
            "expected": expected_tier
        }
        if not tier_match:
            comparison["passed"] = False
            comparison["errors"].append(f"Evidence tier '{actual_tier}' doesn't match expected '{expected_tier}'")
    
    # Check pathway alignment
    if "pathway_alignment" in expected:
        actual_pathways = extract_pathway_scores(actual)
        comparison["checks"]["pathway_alignment"] = {}
        
        for pathway_name, expected_range in expected["pathway_alignment"].items():
            # Try to find matching pathway in actual results
            actual_score = None
            for key, value in actual_pathways.items():
                if pathway_name.lower() in key.lower() or key.lower() in pathway_name.lower():
                    actual_score = value
                    break
            
            if actual_score is not None:
                in_range = expected_range["min"] <= actual_score <= expected_range["max"]
                comparison["checks"]["pathway_alignment"][pathway_name] = {
                    "passed": in_range,
                    "actual": actual_score,
                    "expected": f"[{expected_range['min']}, {expected_range['max']}]"
                }
                if not in_range:
                    comparison["passed"] = False
                    comparison["errors"].append(f"Pathway '{pathway_name}' score {actual_score:.3f} outside expected range [{expected_range['min']}, {expected_range['max']}]")
            else:
                comparison["checks"]["pathway_alignment"][pathway_name] = {
                    "passed": False,
                    "actual": None,
                    "expected": f"[{expected_range['min']}, {expected_range['max']}]"
                }
                comparison["errors"].append(f"Pathway '{pathway_name}' not found in response")
    
    return comparison


async def run_test_case(test_case: Dict[str, Any], client: httpx.AsyncClient) -> Dict[str, Any]:
    """Run a single test case."""
    print(f"\n{'='*60}")
    print(f"Test Case: {test_case['name']}")
    print(f"Patient ID: {test_case['patient_id']}")
    print(f"Disease: {test_case['disease']}")
    print(f"Mutations: {len(test_case['mutations'])}")
    print(f"{'='*60}")
    
    # Print mutations
    for i, mut in enumerate(test_case['mutations'], 1):
        print(f"  {i}. {mut.get('gene', 'N/A')} {mut.get('hgvs_p', 'N/A')}")
    
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
    
    # Extract top drug info
    drugs = response.get("drugs", [])
    if drugs:
        top_drug = drugs[0]
        print(f"\n📊 Top Drug:")
        print(f"   Name: {top_drug.get('name', 'N/A')}")
        print(f"   Efficacy Score: {top_drug.get('efficacy_score', 'N/A')}")
        print(f"   Confidence: {top_drug.get('confidence', 'N/A')}")
        print(f"   Evidence Tier: {top_drug.get('evidence_tier', 'N/A')}")
        print(f"   Badges: {top_drug.get('badges', [])}")
        
        # Show pathway scores
        pathway_scores = extract_pathway_scores(response)
        if pathway_scores:
            print(f"\n🛤️  Pathway Scores:")
            for pathway, score in pathway_scores.items():
                print(f"   {pathway}: {score:.3f}")
    
    # Compare to expected
    print(f"\n🔍 Comparing to expected results...")
    comparison = compare_results(response, test_case["expected"], test_case)
    
    # Print comparison results
    for check_name, check_result in comparison["checks"].items():
        if isinstance(check_result, dict) and "passed" in check_result:
            status = "✅" if check_result["passed"] else "❌"
            print(f"   {status} {check_name}:")
            print(f"      Actual: {check_result.get('actual', 'N/A')}")
            print(f"      Expected: {check_result.get('expected', 'N/A')}")
        elif isinstance(check_result, dict):
            # Nested dict (like pathway_alignment)
            for sub_check, sub_result in check_result.items():
                if isinstance(sub_result, dict) and "passed" in sub_result:
                    status = "✅" if sub_result["passed"] else "❌"
                    print(f"   {status} {check_name} - {sub_check}:")
                    print(f"      Actual: {sub_result.get('actual', 'N/A')}")
                    print(f"      Expected: {sub_result.get('expected', 'N/A')}")
    
    if comparison["errors"]:
        print(f"\n⚠️  Errors:")
        for error in comparison["errors"]:
            print(f"   - {error}")
    
    status_icon = "✅" if comparison["passed"] else "❌"
    print(f"\n{status_icon} Overall: {'PASSED' if comparison['passed'] else 'FAILED'}")
    
    return {
        "test_case": test_case["name"],
        "patient_id": test_case["patient_id"],
        "status": "PASSED" if comparison["passed"] else "FAILED",
        "comparison": comparison,
        "response": response,
        "elapsed_seconds": elapsed
    }


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run Therapy Fit test cases")
    parser.add_argument("--test-case", type=str, help="Run specific test case by patient ID (e.g., AYESHA-001)")
    parser.add_argument("--all", action="store_true", help="Run all test cases")
    parser.add_argument("--output", type=str, help="Output JSON file for results")
    args = parser.parse_args()
    
    print("="*60)
    print("THERAPY FIT TEST CASES RUNNER")
    print("="*60)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Cases File: {TEST_CASES_FILE}")
    
    # Find and load test cases
    test_cases_file = find_test_cases_file()
    if not test_cases_file.exists():
        print(f"❌ Test cases file not found: {test_cases_file}")
        print(f"   Tried: {test_cases_file}")
        sys.exit(1)
    
    print(f"\n📄 Loading test cases from: {test_cases_file}")
    test_cases = parse_test_cases_from_markdown(test_cases_file)
    
    if not test_cases:
        print("❌ No test cases found in file")
        sys.exit(1)
    
    print(f"✅ Loaded {len(test_cases)} test cases")
    
    # Filter test cases if specific one requested
    if args.test_case:
        test_cases = [tc for tc in test_cases if tc["patient_id"] == args.test_case]
        if not test_cases:
            print(f"❌ Test case '{args.test_case}' not found")
            sys.exit(1)
    
    # Run test cases
    results = []
    
    async with httpx.AsyncClient() as client:
        for test_case in test_cases:
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
        elapsed = result.get("elapsed_seconds", 0)
        print(f"   {status_icon} {result['test_case']} ({result['patient_id']}) - {elapsed:.2f}s")
        if result["status"] == "FAILED" and "comparison" in result:
            for error in result["comparison"].get("errors", []):
                print(f"      - {error}")
    
    # Save results
    output_file = args.output or (Path(__file__).parent / "therapy_fit_test_cases_results.json")
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "api_base_url": API_BASE_URL,
            "test_cases_file": str(test_cases_file),
            "test_cases_run": len(results),
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

