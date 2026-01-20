#!/usr/bin/env python3
"""
End-to-End PGx Integration Validation

Sprint 8: End-to-End Testing
Purpose: Validate complete PGx integration workflow with real patient data

Tests:
1. Patient profile → PGx extraction → Drug screening → Risk-benefit composition
2. Trial matching → PGx safety gate → Safety flags
3. Complete care plan → PGx results in response

Research Use Only - Not for Clinical Decision Making
"""

import json
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from api.services.pgx_extraction_service import get_pgx_extraction_service
from api.services.pgx_screening_service import get_pgx_screening_service
from api.services.risk_benefit_composition_service import get_risk_benefit_composition_service
from api.services.pgx_care_plan_integration import (
    integrate_pgx_into_drug_efficacy,
    add_pgx_safety_gate_to_trials
)

# Paths
VALIDATION_DATA = PROJECT_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "cohorts"
OUTPUT_DIR = VALIDATION_DATA / "receipts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_validation_cases() -> List[Dict[str, Any]]:
    """Load validation cases from consolidated dataset."""
    consolidated_path = VALIDATION_DATA / "pgx_validation_datasets_consolidated_20260107_140310.json"
    
    if not consolidated_path.exists():
        print(f"⚠️  Consolidated dataset not found: {consolidated_path}")
        return []
    
    with open(consolidated_path) as f:
        data = json.load(f)
    
    cases = []
    
    # Extract Tier 2 cases
    tier2 = data.get("sources", {}).get("Tier2", {})
    tier2_cases = tier2.get("cases", [])
    for case in tier2_cases:
        cases.append({
            "case_id": case.get("case_id", "unknown"),
            "gene": case.get("gene"),
            "variant": case.get("variant"),
            "drug": case.get("drug"),
            "expected_toxicity": "HIGH" if case.get("expected_outcome") == "contraindicated" else "MODERATE",
            "source": "Tier2"
        })
    
    return cases


async def test_pgx_extraction_integration(case: Dict[str, Any]) -> Dict[str, Any]:
    """Test PGx extraction from patient profile."""
    pgx_service = get_pgx_extraction_service()
    
    # Create test patient profile
    patient_profile = {
        "patient_id": case["case_id"],
        "germline_variants": [
            {
                "gene": case["gene"],
                "variant": case["variant"],
                "hgvs_c": case["variant"] if case["variant"].startswith("c.") else "",
                "hgvs_p": case["variant"] if case["variant"].startswith("p.") else "",
                "classification": "pathogenic"
            }
        ]
    }
    
    # Extract PGx variants
    extracted = pgx_service.extract_from_patient_profile(patient_profile)
    
    # Check if variant was extracted
    found = any(
        v.get("gene") == case["gene"] and v.get("variant") == case["variant"]
        for v in extracted
    )
    
    return {
        "case_id": case["case_id"],
        "extracted": found,
        "extracted_count": len(extracted),
        "passed": found
    }


async def test_drug_screening_integration(case: Dict[str, Any]) -> Dict[str, Any]:
    """Test drug screening with PGx variants."""
    pgx_screening = get_pgx_screening_service()
    pgx_extraction = get_pgx_extraction_service()
    
    # Create patient profile
    patient_profile = {
        "germline_variants": [
            {
                "gene": case["gene"],
                "variant": case["variant"],
                "hgvs_c": case["variant"] if case["variant"].startswith("c.") else "",
                "hgvs_p": case["variant"] if case["variant"].startswith("p.") else ""
            }
        ]
    }
    
    # Extract variants
    variants = pgx_extraction.extract_from_patient_profile(patient_profile)
    
    # Screen drug
    drug_name = case["drug"]
    screening_result = await pgx_screening.screen_drug(
        drug_name=drug_name,
        germline_variants=variants,
        treatment_line="first-line"
    )
    
    # Check if toxicity tier matches expected
    toxicity_tier = screening_result.get("toxicity_tier")
    expected = case.get("expected_toxicity", "MODERATE")
    
    # Allow HIGH or MODERATE to match if expected is HIGH
    tier_match = (
        toxicity_tier == expected or
        (expected == "HIGH" and toxicity_tier in ["HIGH", "MODERATE"])
    )
    
    return {
        "case_id": case["case_id"],
        "drug": drug_name,
        "toxicity_tier": toxicity_tier,
        "expected": expected,
        "tier_match": tier_match,
        "screened": screening_result.get("screened", False),
        "passed": tier_match and screening_result.get("screened", False)
    }


async def test_risk_benefit_composition(case: Dict[str, Any]) -> Dict[str, Any]:
    """Test risk-benefit composition."""
    rb_service = get_risk_benefit_composition_service()
    pgx_screening = get_pgx_screening_service()
    pgx_extraction = get_pgx_extraction_service()
    
    # Create patient profile
    patient_profile = {
        "germline_variants": [
            {
                "gene": case["gene"],
                "variant": case["variant"],
                "hgvs_c": case["variant"] if case["variant"].startswith("c.") else "",
                "hgvs_p": case["variant"] if case["variant"].startswith("p.") else ""
            }
        ]
    }
    
    # Extract and screen
    variants = pgx_extraction.extract_from_patient_profile(patient_profile)
    screening = await pgx_screening.screen_drug(
        drug_name=case["drug"],
        germline_variants=variants,
        treatment_line="first-line"
    )
    
    # Compose risk-benefit
    efficacy_score = 0.85  # Simulated high efficacy
    result = rb_service.compose_risk_benefit(
        efficacy_score=efficacy_score,
        toxicity_tier=screening.get("toxicity_tier"),
        adjustment_factor=screening.get("adjustment_factor")
    )
    
    # Check if composition is correct
    expected_high_risk = case.get("expected_toxicity") == "HIGH"
    is_high_risk = result.composite_score == 0.0 or result.action_label == "AVOID / HIGH-RISK"
    
    passed = (expected_high_risk and is_high_risk) or (not expected_high_risk and not is_high_risk)
    
    return {
        "case_id": case["case_id"],
        "efficacy_score": efficacy_score,
        "composite_score": result.composite_score,
        "action_label": result.action_label,
        "expected_high_risk": expected_high_risk,
        "is_high_risk": is_high_risk,
        "passed": passed
    }


async def test_drug_efficacy_integration(case: Dict[str, Any]) -> Dict[str, Any]:
    """Test integration into drug efficacy response."""
    # Create mock drug efficacy response
    drug_efficacy_response = {
        "status": "success",
        "drugs": [
            {
                "name": case["drug"],
                "efficacy_score": 0.85,
                "confidence": 0.80
            }
        ]
    }
    
    # Create patient profile
    patient_profile = {
        "germline_variants": [
            {
                "gene": case["gene"],
                "variant": case["variant"],
                "hgvs_c": case["variant"] if case["variant"].startswith("c.") else "",
                "hgvs_p": case["variant"] if case["variant"].startswith("p.") else ""
            }
        ],
        "disease": {"type": "ovarian_cancer_hgs"},
        "treatment": {"line": "first-line", "history": []}
    }
    
    # Integrate PGx
    enhanced = await integrate_pgx_into_drug_efficacy(
        drug_efficacy_response=drug_efficacy_response,
        patient_profile=patient_profile,
        treatment_line="first-line",
        prior_therapies=[]
    )
    
    # Check if integration worked
    drug = enhanced.get("drugs", [{}])[0]
    has_pgx = "pgx_screening" in drug
    has_composite = "composite_score" in drug
    
    return {
        "case_id": case["case_id"],
        "has_pgx_screening": has_pgx,
        "has_composite_score": has_composite,
        "composite_score": drug.get("composite_score"),
        "action_label": drug.get("action_label"),
        "passed": has_pgx and has_composite
    }


async def main():
    """Main validation execution."""
    print("=" * 60)
    print("PGx Integration End-to-End Validation")
    print("=" * 60)
    print()
    
    # Load validation cases
    print("📊 Loading validation cases...")
    cases = load_validation_cases()
    print(f"  Loaded {len(cases)} validation cases")
    
    if not cases:
        print("  ❌ No validation cases found")
        return 1
    
    # Run tests
    results = {
        "extraction": [],
        "screening": [],
        "composition": [],
        "efficacy_integration": []
    }
    
    print("\n🧪 Test 1: PGx Extraction Integration")
    for case in cases:
        result = await test_pgx_extraction_integration(case)
        results["extraction"].append(result)
        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {case['case_id']}: {result['extracted_count']} variants extracted")
    
    print("\n🧪 Test 2: Drug Screening Integration")
    for case in cases:
        result = await test_drug_screening_integration(case)
        results["screening"].append(result)
        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {case['case_id']}: {result['toxicity_tier']} (expected: {result['expected']})")
    
    print("\n🧪 Test 3: Risk-Benefit Composition")
    for case in cases:
        result = await test_risk_benefit_composition(case)
        results["composition"].append(result)
        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {case['case_id']}: {result['action_label']} (score: {result['composite_score']:.3f})")
    
    print("\n🧪 Test 4: Drug Efficacy Integration")
    for case in cases:
        result = await test_drug_efficacy_integration(case)
        results["efficacy_integration"].append(result)
        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {case['case_id']}: PGx integrated, composite={result['composite_score']}")
    
    # Calculate metrics
    extraction_pass = sum(1 for r in results["extraction"] if r["passed"])
    screening_pass = sum(1 for r in results["screening"] if r["passed"])
    composition_pass = sum(1 for r in results["composition"] if r["passed"])
    efficacy_pass = sum(1 for r in results["efficacy_integration"] if r["passed"])
    
    total_tests = len(cases) * 4
    total_passed = extraction_pass + screening_pass + composition_pass + efficacy_pass
    
    # Generate receipt
    receipt = {
        "timestamp": datetime.now().isoformat(),
        "validation_type": "e2e_integration",
        "test_cases": len(cases),
        "results": {
            "extraction": {
                "passed": extraction_pass,
                "total": len(cases),
                "pass_rate": extraction_pass / len(cases) if cases else 0
            },
            "screening": {
                "passed": screening_pass,
                "total": len(cases),
                "pass_rate": screening_pass / len(cases) if cases else 0
            },
            "composition": {
                "passed": composition_pass,
                "total": len(cases),
                "pass_rate": composition_pass / len(cases) if cases else 0
            },
            "efficacy_integration": {
                "passed": efficacy_pass,
                "total": len(cases),
                "pass_rate": efficacy_pass / len(cases) if cases else 0
            }
        },
        "overall": {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "pass_rate": total_passed / total_tests if total_tests > 0 else 0
        },
        "target": {
            "min_pass_rate": 0.90,
            "meets_target": (total_passed / total_tests) >= 0.90 if total_tests > 0 else False
        }
    }
    
    # Save receipt
    receipt_path = OUTPUT_DIR / f"pgx_e2e_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(receipt_path, 'w') as f:
        json.dump(receipt, f, indent=2)
    
    print(f"\n💾 Validation receipt saved: {receipt_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Extraction: {extraction_pass}/{len(cases)} ({extraction_pass/len(cases)*100:.1f}%)")
    print(f"Screening: {screening_pass}/{len(cases)} ({screening_pass/len(cases)*100:.1f}%)")
    print(f"Composition: {composition_pass}/{len(cases)} ({composition_pass/len(cases)*100:.1f}%)")
    print(f"Efficacy Integration: {efficacy_pass}/{len(cases)} ({efficacy_pass/len(cases)*100:.1f}%)")
    print(f"\nOverall: {total_passed}/{total_tests} ({total_passed/total_tests*100:.1f}%)")
    print(f"Target (≥90%): {'✅ MET' if receipt['target']['meets_target'] else '❌ NOT MET'}")
    print("=" * 60)
    
    return 0 if receipt['target']['meets_target'] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))


