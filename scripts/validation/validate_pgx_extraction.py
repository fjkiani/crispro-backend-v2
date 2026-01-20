#!/usr/bin/env python3
"""
Validate PGx Extraction Service

Tests the PGx extraction service with real validation data to ensure
it correctly identifies pharmacogene variants.

Ground Truth: Validation cases from existing PGx validation cohort
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # oncology-backend-minimal
sys.path.insert(0, str(PROJECT_ROOT))

from api.services.pgx_extraction_service import get_pgx_extraction_service

# Paths
PGX_REPORTS = PROJECT_ROOT.parent.parent / "publications" / "05-pgx-dosing-guidance" / "reports"
OUTPUT_DIR = PROJECT_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "cohorts" / "receipts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_tier2_cases() -> List[Dict[str, Any]]:
    """Load Tier 2 validation cases as ground truth."""
    tier2_path = PGX_REPORTS / "tier2_validation_cases.json"
    if not tier2_path.exists():
        return []
    
    with open(tier2_path) as f:
        data = json.load(f)
    
    return data.get("cases", [])


def create_test_patient_profile(case: Dict[str, Any]) -> Dict[str, Any]:
    """Create a test patient profile from a validation case."""
    return {
        "patient_id": case.get("case_id", "unknown"),
        "disease": "test",
        "germline_variants": [
            {
                "gene": case.get("gene"),
                "variant": case.get("variant"),
                "hgvs_c": case.get("variant") if case.get("variant", "").startswith("c.") else "",
                "hgvs_p": case.get("variant") if case.get("variant", "").startswith("p.") else "",
                "classification": "pathogenic"
            }
        ]
    }


def test_extraction_from_profile(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Test extraction from patient profile."""
    pgx_service = get_pgx_extraction_service()
    
    results = {
        "total_cases": len(cases),
        "extracted": 0,
        "missed": 0,
        "false_positives": 0,
        "cases": []
    }
    
    for case in cases:
        gene = case.get("gene")
        variant = case.get("variant")
        
        # Create test profile
        test_profile = create_test_patient_profile(case)
        
        # Extract PGx variants
        extracted = pgx_service.extract_from_patient_profile(test_profile)
        
        # Check if our variant was extracted
        found = False
        for ext_variant in extracted:
            if ext_variant.get("gene") == gene and ext_variant.get("variant") == variant:
                found = True
                break
        
        case_result = {
            "case_id": case.get("case_id"),
            "gene": gene,
            "variant": variant,
            "extracted": found,
            "extracted_variants": extracted
        }
        
        if found:
            results["extracted"] += 1
        else:
            results["missed"] += 1
            case_result["error"] = "Variant not extracted"
        
        results["cases"].append(case_result)
    
    # Calculate metrics
    if results["total_cases"] > 0:
        results["precision"] = results["extracted"] / results["total_cases"]
        results["recall"] = results["extracted"] / results["total_cases"]
    else:
        results["precision"] = 0.0
        results["recall"] = 0.0
    
    return results


def test_extraction_from_vcf_format() -> Dict[str, Any]:
    """Test extraction from VCF-like mutation format."""
    pgx_service = get_pgx_extraction_service()
    
    # Create test VCF mutations (simulating VCF parser output)
    test_mutations = [
        {
            "gene": "DPYD",
            "variant": "c.2846A>T",
            "hgvs_c": "c.2846A>T",
            "chrom": "1",
            "pos": 97915614,
            "ref": "A",
            "alt": "T",
            "zygosity": "heterozygous"
        },
        {
            "gene": "TPMT",
            "variant": "*3A",
            "hgvs_c": "c.460G>A",
            "chrom": "6",
            "pos": 18139228,
            "ref": "G",
            "alt": "A",
            "zygosity": "heterozygous"
        },
        {
            "gene": "BRCA1",  # Not a pharmacogene
            "variant": "c.5266dupC",
            "hgvs_c": "c.5266dupC",
            "chrom": "17",
            "pos": 43044295,
            "ref": "C",
            "alt": "C",
            "zygosity": "heterozygous"
        }
    ]
    
    extracted = pgx_service.extract_from_vcf(test_mutations, sample_type="germline")
    
    # Should extract 2 PGx variants (DPYD, TPMT), not BRCA1
    expected_genes = {"DPYD", "TPMT"}
    extracted_genes = {v["gene"] for v in extracted}
    
    return {
        "test_mutations": len(test_mutations),
        "extracted_variants": len(extracted),
        "expected_genes": list(expected_genes),
        "extracted_genes": list(extracted_genes),
        "correct": expected_genes == extracted_genes,
        "extracted_variants_detail": extracted
    }


def main():
    """Main validation execution."""
    print("=" * 60)
    print("PGx Extraction Service Validation")
    print("=" * 60)
    print()
    
    # Load ground truth
    print("📊 Loading ground truth cases...")
    cases = load_tier2_cases()
    print(f"  Loaded {len(cases)} Tier 2 validation cases")
    
    # Test 1: Extraction from patient profile
    print("\n🧪 Test 1: Extraction from Patient Profile")
    profile_results = test_extraction_from_profile(cases)
    print(f"  Total cases: {profile_results['total_cases']}")
    print(f"  Extracted: {profile_results['extracted']}")
    print(f"  Missed: {profile_results['missed']}")
    print(f"  Precision: {profile_results['precision']:.2%}")
    print(f"  Recall: {profile_results['recall']:.2%}")
    
    # Test 2: Extraction from VCF format
    print("\n🧪 Test 2: Extraction from VCF Format")
    vcf_results = test_extraction_from_vcf_format()
    print(f"  Test mutations: {vcf_results['test_mutations']}")
    print(f"  Extracted variants: {vcf_results['extracted_variants']}")
    print(f"  Expected genes: {vcf_results['expected_genes']}")
    print(f"  Extracted genes: {vcf_results['extracted_genes']}")
    print(f"  Correct: {'✅' if vcf_results['correct'] else '❌'}")
    
    # Generate receipt
    receipt = {
        "timestamp": datetime.now().isoformat(),
        "validation_type": "pgx_extraction",
        "ground_truth_source": "tier2_validation_cases.json",
        "results": {
            "profile_extraction": profile_results,
            "vcf_extraction": vcf_results
        },
        "metrics": {
            "precision": profile_results["precision"],
            "recall": profile_results["recall"],
            "target_precision": 0.95,
            "target_recall": 0.90,
            "meets_targets": profile_results["precision"] >= 0.95 and profile_results["recall"] >= 0.90
        }
    }
    
    # Save receipt
    receipt_path = OUTPUT_DIR / f"pgx_extraction_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(receipt_path, 'w') as f:
        json.dump(receipt, f, indent=2)
    
    print(f"\n💾 Validation receipt saved: {receipt_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Precision: {profile_results['precision']:.2%} (target: ≥95%)")
    print(f"Recall: {profile_results['recall']:.2%} (target: ≥90%)")
    print(f"VCF Extraction: {'✅ PASS' if vcf_results['correct'] else '❌ FAIL'}")
    print(f"Meets Targets: {'✅ YES' if receipt['metrics']['meets_targets'] else '❌ NO'}")
    print("=" * 60)
    
    return 0 if receipt['metrics']['meets_targets'] and vcf_results['correct'] else 1


if __name__ == "__main__":
    sys.exit(main())

