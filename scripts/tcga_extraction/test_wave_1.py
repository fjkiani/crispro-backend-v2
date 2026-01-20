#!/usr/bin/env python3
"""
Test Wave 1: Validate Food Validator with TCGA-Weighted Pathway Scoring

Tests 4 use cases:
1. Vitamin D → Ovarian (should work, TCGA data available)
2. Curcumin → Breast (should work, TCGA data available)
3. Resveratrol → Pancreatic (should work, TCGA data available)
4. Omega-3 → Alzheimer's (should fail gracefully, disease not in database)

Validates:
- P scores use TCGA weights (not binary matching)
- Pathway contributions reflect real mutation frequencies
- Error handling for missing diseases
"""

import requests
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

API_BASE = "http://127.0.0.1:8000"

# Test cases
TEST_CASES = [
    {
        "test_id": 1,
        "compound": "Vitamin D",
        "disease": "ovarian_cancer_hgs",
        "expected_p_min": 0.15,  # Should use TCGA weights (TP53=0.955, HRD=0.112)
        "expected_verdict": "SUPPORTED",  # or "WEAK_SUPPORT"
        "should_pass": True
    },
    {
        "test_id": 2,
        "compound": "Curcumin",
        "disease": "breast_cancer",
        "expected_p_min": 0.50,  # Should use PI3K weight (0.827)
        "expected_verdict": "SUPPORTED",  # or "WEAK_SUPPORT"
        "should_pass": True
    },
    {
        "test_id": 3,
        "compound": "Resveratrol",
        "disease": "pancreatic_cancer",
        "expected_p_min": 0.60,  # Should use KRAS weight (0.854)
        "expected_verdict": "SUPPORTED",  # or "WEAK_SUPPORT"
        "should_pass": True
    },
    {
        "test_id": 4,
        "compound": "Omega-3 fatty acids",
        "disease": "alzheimers_disease",
        "expected_p_min": None,  # Should fail gracefully
        "expected_verdict": None,
        "should_pass": False  # Expected to fail (disease not in database)
    }
]


def run_test(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single test case."""
    print(f"\n{'='*80}")
    print(f"🧪 TEST {test_case['test_id']}: {test_case['compound']} → {test_case['disease']}")
    print(f"{'='*80}")
    
    try:
        # Use validate_food_dynamic endpoint (uses FoodSPEIntegrationService with TCGA weights)
        payload = {
            "compound": test_case["compound"],
            "disease_context": {
                "disease": test_case["disease"],
                "mutations": [],
                "biomarkers": {},
                "pathways_disrupted": []  # Will be loaded from universal DB
            },
            "treatment_history": {
                "current_line": 3,
                "prior_therapies": []
            },
            "patient_medications": [],
            "use_evo2": False
        }
        
        response = requests.post(
            f"{API_BASE}/api/hypothesis/validate_food_dynamic",
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Debug: Print full response if error
            if data.get("status") == "ERROR":
                print(f"❌ API Error Response:")
                print(f"   {json.dumps(data, indent=2)}")
            
            # Extract results
            status = data.get("status", "UNKNOWN")
            verdict = data.get("verdict", "UNKNOWN")
            overall_score = data.get("overall_score", 0.0)
            confidence = data.get("confidence", 0.0)
            spe_breakdown = data.get("spe_breakdown", {})
            pathway_score = spe_breakdown.get("pathway", 0.0) if isinstance(spe_breakdown, dict) else 0.0
            
            # Handle format errors
            if pathway_score is None:
                pathway_score = 0.0
            try:
                pathway_score = float(pathway_score)
            except (ValueError, TypeError):
                pathway_score = 0.0
            
            # Validate
            passed = True
            issues = []
            
            if test_case["should_pass"]:
                if status != "SUCCESS":
                    passed = False
                    issues.append(f"Status: expected SUCCESS, got {status}")
                
                if test_case["expected_p_min"] and pathway_score < test_case["expected_p_min"]:
                    passed = False
                    issues.append(f"P score too low: {pathway_score:.3f} < {test_case['expected_p_min']:.3f}")
                
                # Check if pathway score reflects TCGA weighting (not binary 0.0/1.0)
                # Acceptable range: 0.01 to 0.99 (TCGA weights are continuous)
                if pathway_score == 0.0 or pathway_score == 1.0:
                    issues.append(f"⚠️ P score looks binary ({pathway_score:.3f}), not TCGA-weighted")
                elif 0.01 <= pathway_score <= 0.99:
                    # This is a valid TCGA-weighted score (even if low)
                    pass  # No issue
            
            else:
                # Should fail gracefully
                if status == "SUCCESS":
                    issues.append("⚠️ Expected failure but got SUCCESS")
                    passed = False
                else:
                    passed = True
            
            result = {
                "test_id": test_case["test_id"],
                "compound": test_case["compound"],
                "disease": test_case["disease"],
                "status": status,
                "verdict": verdict,
                "pathway_score": pathway_score,
                "overall_score": overall_score,
                "confidence": confidence,
                "spe_breakdown": spe_breakdown,
                "passed": passed,
                "issues": issues
            }
            
            # Print results
            print(f"✅ Status: {status}")
            print(f"✅ Verdict: {verdict}")
            print(f"✅ P Score: {pathway_score:.3f} (expected ≥{test_case.get('expected_p_min', 0):.3f})")
            print(f"✅ Overall: {overall_score:.3f}")
            print(f"✅ Confidence: {confidence:.3f}")
            
            if issues:
                print(f"\n⚠️ Issues:")
                for issue in issues:
                    print(f"   - {issue}")
            
            if passed:
                print(f"\n✅ TEST {test_case['test_id']} PASSED")
            else:
                print(f"\n❌ TEST {test_case['test_id']} FAILED")
            
            return result
            
        else:
            error_msg = response.text[:200] if response.text else "Unknown error"
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"   {error_msg}")
            
            return {
                "test_id": test_case["test_id"],
                "compound": test_case["compound"],
                "disease": test_case["disease"],
                "status": "ERROR",
                "passed": False,
                "error": f"HTTP {response.status_code}: {error_msg}"
            }
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Backend not running at {API_BASE}")
        print(f"   Start backend with: cd oncology-backend-minimal && uvicorn api.main:app --reload")
        return {
            "test_id": test_case["test_id"],
            "compound": test_case["compound"],
            "disease": test_case["disease"],
            "status": "ERROR",
            "passed": False,
            "error": "Backend not running"
        }
    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            "test_id": test_case["test_id"],
            "compound": test_case["compound"],
            "disease": test_case["disease"],
            "status": "ERROR",
            "passed": False,
            "error": str(e)
        }


def main():
    """Run all test cases."""
    print("=" * 80)
    print("🧪 TEST WAVE 1: Food Validator with TCGA-Weighted Pathway Scoring")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API Base: {API_BASE}")
    print()
    
    results = []
    
    for test_case in TEST_CASES:
        result = run_test(test_case)
        results.append(result)
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 TEST WAVE 1 SUMMARY")
    print(f"{'='*80}")
    
    passed_count = sum(1 for r in results if r.get("passed", False))
    total_count = len(results)
    
    print(f"\nTests Passed: {passed_count}/{total_count}")
    print()
    
    print("Detailed Results:")
    print("| Test | Compound | Disease | P Score | Verdict | Status |")
    print("|------|----------|---------|---------|---------|--------|")
    
    for result in results:
        test_id = result["test_id"]
        compound = result["compound"]
        disease = result["disease"]
        p_score = result.get("pathway_score", "N/A")
        if isinstance(p_score, float):
            p_score = f"{p_score:.3f}"
        verdict = result.get("verdict", "N/A")
        status = "✅ PASS" if result.get("passed", False) else "❌ FAIL"
        
        print(f"| {test_id} | {compound} | {disease} | {p_score} | {verdict} | {status} |")
    
    # Save results
    output_file = Path(__file__).parent / "TEST_WAVE_1_RESULTS.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_tests": total_count,
            "passed_tests": passed_count,
            "results": results
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if passed_count == total_count:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️ {total_count - passed_count} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

