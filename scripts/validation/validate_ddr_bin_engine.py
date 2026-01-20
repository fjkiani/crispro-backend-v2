"""
Validation Script for DDR_bin Scoring Engine.

Validates DDR_bin engine on synthetic data across different disease sites.
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.services.resistance.biomarkers.diagnostic.ddr_bin_scoring import (
    assign_ddr_status,
    get_ddr_config,
)
from api.services.resistance.config.ddr_config import DDR_CONFIG


def generate_synthetic_ddr_test_cases() -> List[Dict[str, Any]]:
    """
    Generate synthetic test cases for DDR_bin engine validation.
    
    Returns:
        List of test case dictionaries with mutations, CNA, HRD assay, and expected DDR_bin_status
    """
    test_cases = []
    
    # Test Case 1: BRCA pathogenic (ovary) - Should be DDR_defective
    test_cases.append({
        "test_id": "TC001_BRCA_pathogenic_ovary",
        "patient_id": "SYNTH_OV001",
        "disease_site": "ovary",
        "mutations": [
            {
                "patient_id": "SYNTH_OV001",
                "gene_symbol": "BRCA1",
                "variant_classification": "Pathogenic",
                "variant_type": "SNV",
            }
        ],
        "cna": None,
        "hrd_assay": None,
        "clinical_data": {"disease_site": "ovary", "tumor_subtype": "HGSOC"},
        "expected_ddr_bin_status": "DDR_defective",
        "expected_brca_pathogenic": True,
    })
    
    # Test Case 2: HRD positive by score (ovary) - Should be DDR_defective
    test_cases.append({
        "test_id": "TC002_HRD_positive_ovary",
        "patient_id": "SYNTH_OV002",
        "disease_site": "ovary",
        "mutations": [],
        "cna": None,
        "hrd_assay": {
            "patient_id": "SYNTH_OV002",
            "hrd_score": 68.0,
            "hrd_status": None,
            "assay_name": "Myriad",
        },
        "clinical_data": {"disease_site": "ovary", "tumor_subtype": "HGSOC"},
        "expected_ddr_bin_status": "DDR_defective",
        "expected_hrd_status_inferred": "HRD_positive",
    })
    
    # Test Case 3: Core HRR pathogenic (breast) - Should be DDR_defective
    test_cases.append({
        "test_id": "TC003_core_HRR_breast",
        "patient_id": "SYNTH_BR001",
        "disease_site": "breast",
        "mutations": [
            {
                "patient_id": "SYNTH_BR001",
                "gene_symbol": "PALB2",
                "variant_classification": "Pathogenic",
                "variant_type": "SNV",
            }
        ],
        "cna": None,
        "hrd_assay": None,
        "clinical_data": {"disease_site": "breast", "tumor_subtype": "TNBC"},
        "expected_ddr_bin_status": "DDR_defective",
        "expected_core_HRR_pathogenic": True,
    })
    
    # Test Case 4: Extended DDR pathogenic (prostate) - Should be DDR_defective
    test_cases.append({
        "test_id": "TC004_extended_DDR_prostate",
        "patient_id": "SYNTH_PR001",
        "disease_site": "prostate",
        "mutations": [
            {
                "patient_id": "SYNTH_PR001",
                "gene_symbol": "ATM",
                "variant_classification": "Pathogenic",
                "variant_type": "SNV",
            }
        ],
        "cna": None,
        "hrd_assay": None,
        "clinical_data": {"disease_site": "prostate"},
        "expected_ddr_bin_status": "DDR_defective",
        "expected_extended_DDR_pathogenic": True,
    })
    
    # Test Case 5: DDR proficient (ovary) - Should be DDR_proficient
    test_cases.append({
        "test_id": "TC005_DDR_proficient_ovary",
        "patient_id": "SYNTH_OV003",
        "disease_site": "ovary",
        "mutations": [
            {
                "patient_id": "SYNTH_OV003",
                "gene_symbol": "TP53",
                "variant_classification": "Pathogenic",
                "variant_type": "SNV",
            }
        ],
        "cna": None,
        "hrd_assay": {
            "patient_id": "SYNTH_OV003",
            "hrd_score": 25.0,  # Below threshold
            "hrd_status": "HRD_negative",
            "assay_name": "Myriad",
        },
        "clinical_data": {"disease_site": "ovary", "tumor_subtype": "HGSOC"},
        "expected_ddr_bin_status": "DDR_proficient",
        "expected_brca_pathogenic": False,
    })
    
    # Test Case 6: No DDR info (ovary) - Should be unknown
    test_cases.append({
        "test_id": "TC006_no_DDR_info_ovary",
        "patient_id": "SYNTH_OV004",
        "disease_site": "ovary",
        "mutations": [
            {
                "patient_id": "SYNTH_OV004",
                "gene_symbol": "TP53",
                "variant_classification": "VUS",
                "variant_type": "SNV",
            }
        ],
        "cna": None,
        "hrd_assay": None,
        "clinical_data": {"disease_site": "ovary", "tumor_subtype": "HGSOC"},
        "expected_ddr_bin_status": "unknown",
    })
    
    # Test Case 7: BRCA with biallelic loss (ovary) - Should be DDR_defective
    test_cases.append({
        "test_id": "TC007_brca_biallelic_ovary",
        "patient_id": "SYNTH_OV005",
        "disease_site": "ovary",
        "mutations": [
            {
                "patient_id": "SYNTH_OV005",
                "gene_symbol": "BRCA2",
                "variant_classification": "Pathogenic",
                "variant_type": "SNV",
            }
        ],
        "cna": [
            {
                "patient_id": "SYNTH_OV005",
                "gene_symbol": "BRCA2",
                "copy_number_state": "deletion",
            }
        ],
        "hrd_assay": None,
        "clinical_data": {"disease_site": "ovary", "tumor_subtype": "HGSOC"},
        "expected_ddr_bin_status": "DDR_defective",
        "expected_brca_pathogenic": True,
    })
    
    # Test Case 8: Priority ordering - BRCA over HRD (ovary)
    test_cases.append({
        "test_id": "TC008_priority_BRCA_over_HRD",
        "patient_id": "SYNTH_OV006",
        "disease_site": "ovary",
        "mutations": [
            {
                "patient_id": "SYNTH_OV006",
                "gene_symbol": "BRCA1",
                "variant_classification": "Pathogenic",
                "variant_type": "SNV",
            }
        ],
        "cna": None,
        "hrd_assay": {
            "patient_id": "SYNTH_OV006",
            "hrd_score": 75.0,  # High HRD score
            "hrd_status": "HRD_positive",
            "assay_name": "Myriad",
        },
        "clinical_data": {"disease_site": "ovary", "tumor_subtype": "HGSOC"},
        "expected_ddr_bin_status": "DDR_defective",
        "expected_brca_pathogenic": True,
        "expected_hrd_status_inferred": "HRD_positive",  # Should still infer HRD
    })
    
    return test_cases


def validate_ddr_bin_engine(test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate DDR_bin engine on synthetic test cases.
    
    Args:
        test_cases: List of test case dictionaries
    
    Returns:
        Dictionary with validation results
    """
    validation_results = {
        "total_test_cases": len(test_cases),
        "correct": 0,
        "incorrect": 0,
        "errors": [],
        "per_disease_site": {},
    }
    
    for test_case in test_cases:
        test_id = test_case["test_id"]
        patient_id = test_case["patient_id"]
        disease_site = test_case["disease_site"]
        
        # Run DDR_bin engine
        # Note: assign_ddr_status expects tables (lists) not single records
        # Prepare tables for this single patient
        mutations_table = test_case["mutations"] if test_case.get("mutations") else []
        cna_table = test_case["cna"] if test_case.get("cna") else None
        hrd_assay_table = [test_case["hrd_assay"]] if test_case.get("hrd_assay") else None
        
        # Ensure clinical_data has patient_id
        clinical_data = test_case.get("clinical_data", {})
        clinical_data["patient_id"] = patient_id
        clinical_table = [clinical_data]
        
        # Run engine
        results = assign_ddr_status(
            mutations_table=mutations_table,
            clinical_table=clinical_table,
            cna_table=cna_table,
            hrd_assay_table=hrd_assay_table,
            config=None
        )
        
        # Get result for this patient
        if results and len(results) > 0:
            result = results[0]  # Should only be one patient
        else:
            result = {}  # No result returned
        
        # Validate DDR_bin_status
        computed_status = result.get("DDR_bin_status")
        expected_status = test_case["expected_ddr_bin_status"]
        
        is_correct = computed_status == expected_status
        
        # Validate additional flags if specified
        additional_checks = []
        if "expected_brca_pathogenic" in test_case:
            if result.get("BRCA_pathogenic") != test_case["expected_brca_pathogenic"]:
                additional_checks.append(f"BRCA_pathogenic mismatch")
        
        if "expected_core_HRR_pathogenic" in test_case:
            if result.get("core_HRR_pathogenic") != test_case["expected_core_HRR_pathogenic"]:
                additional_checks.append(f"core_HRR_pathogenic mismatch")
        
        if "expected_extended_DDR_pathogenic" in test_case:
            if result.get("extended_DDR_pathogenic") != test_case["expected_extended_DDR_pathogenic"]:
                additional_checks.append(f"extended_DDR_pathogenic mismatch")
        
        if "expected_hrd_status_inferred" in test_case:
            if result.get("HRD_status_inferred") != test_case["expected_hrd_status_inferred"]:
                additional_checks.append(f"HRD_status_inferred mismatch")
        
        if is_correct and not additional_checks:
            validation_results["correct"] += 1
        else:
            validation_results["incorrect"] += 1
            validation_results["errors"].append({
                "test_id": test_id,
                "patient_id": patient_id,
                "computed_status": computed_status,
                "expected_status": expected_status,
                "is_correct": is_correct,
                "additional_checks": additional_checks,
                "full_result": result,
            })
        
        # Track per disease site
        if disease_site not in validation_results["per_disease_site"]:
            validation_results["per_disease_site"][disease_site] = {
                "correct": 0,
                "incorrect": 0,
                "total": 0,
            }
        
        validation_results["per_disease_site"][disease_site]["total"] += 1
        if is_correct and not additional_checks:
            validation_results["per_disease_site"][disease_site]["correct"] += 1
        else:
            validation_results["per_disease_site"][disease_site]["incorrect"] += 1
    
    # Calculate accuracy
    if validation_results["total_test_cases"] > 0:
        validation_results["accuracy"] = validation_results["correct"] / validation_results["total_test_cases"]
    
    # Calculate per-disease accuracy
    for disease_site, stats in validation_results["per_disease_site"].items():
        if stats["total"] > 0:
            stats["accuracy"] = stats["correct"] / stats["total"]
    
    return validation_results


def main():
    """Main validation script."""
    print("=" * 70)
    print("DDR_BIN ENGINE VALIDATION")
    print("=" * 70)
    
    # Step 1: Generate synthetic test cases
    print("\n1. Generating synthetic test cases...")
    test_cases = generate_synthetic_ddr_test_cases()
    print(f"   Generated {len(test_cases)} test cases")
    print(f"   Disease sites: {set(tc['disease_site'] for tc in test_cases)}")
    
    # Step 2: Validate DDR_bin engine
    print("\n2. Validating DDR_bin engine...")
    validation_results = validate_ddr_bin_engine(test_cases)
    
    print(f"\n   Total Test Cases: {validation_results['total_test_cases']}")
    print(f"   Correct: {validation_results['correct']}")
    print(f"   Incorrect: {validation_results['incorrect']}")
    if validation_results.get('accuracy') is not None:
        print(f"   Accuracy: {validation_results['accuracy']:.2%}")
    
    print("\n   Per Disease Site:")
    for disease_site, stats in validation_results["per_disease_site"].items():
        print(f"      {disease_site}: {stats['correct']}/{stats['total']} correct ({stats.get('accuracy', 0):.2%})")
    
    # Display errors
    if validation_results["errors"]:
        print("\n   Errors:")
        for error in validation_results["errors"][:5]:  # Show first 5 errors
            print(f"      {error['test_id']}: Computed {error['computed_status']}, Expected {error['expected_status']}")
            if error["additional_checks"]:
                print(f"         Additional issues: {', '.join(error['additional_checks'])}")
        if len(validation_results["errors"]) > 5:
            print(f"      ... and {len(validation_results['errors']) - 5} more errors")
    
    # Save results
    output_dir = project_root / "data" / "validation" / "ddr_bin"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {
        "validation_timestamp": datetime.now().isoformat(),
        "test_cases": len(test_cases),
        "validation_results": validation_results,
    }
    
    output_file = output_dir / "ddr_bin_validation_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n3. Saved validation results to: {output_file}")
    
    print("\n" + "=" * 70)
    if validation_results["incorrect"] == 0:
        print("✅ VALIDATION PASSED - All test cases correct!")
    else:
        print(f"⚠️  VALIDATION PARTIAL - {validation_results['incorrect']} test case(s) failed")
    print("=" * 70)


if __name__ == "__main__":
    main()
