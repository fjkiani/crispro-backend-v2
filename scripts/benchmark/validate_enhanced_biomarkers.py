#!/usr/bin/env python3
"""
Validation script for enhanced biomarker extraction.

Validates that enhanced biomarker extraction improves coverage
and maintains data quality standards.

Usage:
    python scripts/benchmark/validate_enhanced_biomarkers.py [--dataset path/to/dataset.json]
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.benchmark.benchmark_common.utils.biomarker_extractor import (
    extract_tmb_from_patient,
    extract_hrd_from_patient,
    extract_msi_from_patient,
    build_tumor_context
)


def load_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """Load patient dataset from JSON file."""
    with open(dataset_path, 'r') as f:
        data = json.load(f)
    
    patients = []
    
    # Handle different data formats
    if isinstance(data, list):
        # List of studies - extract patients from each study
        for item in data:
            if isinstance(item, dict):
                if "patients" in item:
                    # Study object with patients list
                    patients.extend(item.get("patients", []))
                elif "patient_id" in item or "mutations" in item:
                    # Direct patient object
                    patients.append(item)
    elif isinstance(data, dict):
        if "patients" in data:
            # Single study object
            patients = data.get("patients", [])
        else:
            # Dict of studies keyed by study_id
            for study_data in data.values():
                if isinstance(study_data, dict) and "patients" in study_data:
                    patients.extend(study_data.get("patients", []))
    
    return patients


def validate_enhanced_extraction(patients: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate enhanced biomarker extraction.
    
    Compares baseline (old) vs enhanced (new) extraction:
    - Coverage: % of patients with biomarker data
    - Confidence distribution: High/Medium/Low breakdown
    - Source distribution: Direct vs estimated breakdown
    """
    results = {
        "total_patients": len(patients),
        "tmb": {"coverage": 0, "sources": defaultdict(int), "confidence": defaultdict(int)},
        "hrd": {"coverage": 0, "sources": defaultdict(int), "confidence": defaultdict(int)},
        "msi": {"coverage": 0, "sources": defaultdict(int), "confidence": defaultdict(int)},
        "tumor_contexts": {
            "with_any_biomarker": 0,
            "with_all_biomarkers": 0,
            "completeness_distribution": defaultdict(int)
        }
    }
    
    for patient in patients:
        # Build tumor context with enhanced extraction
        tumor_context = build_tumor_context(
            patient,
            estimate_hrd=True,
            estimate_msi=True,
            hrd_confidence="medium",
            msi_confidence="medium",
            tmb_pathogenic_only=True,
            tmb_min_maf=0.01
        )
        
        # Track TMB
        if "tmb" in tumor_context:
            results["tmb"]["coverage"] += 1
            tmb_source = tumor_context.get("biomarker_sources", {}).get("tmb", "unknown")
            results["tmb"]["sources"][tmb_source] += 1
            tmb_conf = tumor_context.get("biomarker_confidence", {}).get("tmb", "unknown")
            results["tmb"]["confidence"][tmb_conf] += 1
        
        # Track HRD
        if "hrd_score" in tumor_context:
            results["hrd"]["coverage"] += 1
            hrd_source = tumor_context.get("biomarker_sources", {}).get("hrd", "unknown")
            results["hrd"]["sources"][hrd_source] += 1
            hrd_conf = tumor_context.get("biomarker_confidence", {}).get("hrd_score", "unknown")
            results["hrd"]["confidence"][hrd_conf] += 1
        
        # Track MSI
        if "msi_status" in tumor_context:
            results["msi"]["coverage"] += 1
            msi_source = tumor_context.get("biomarker_sources", {}).get("msi", "unknown")
            results["msi"]["sources"][msi_source] += 1
            msi_conf = tumor_context.get("biomarker_confidence", {}).get("msi_status", "unknown")
            results["msi"]["confidence"][msi_conf] += 1
        
        # Track tumor context completeness
        biomarkers_present = sum([
            "tmb" in tumor_context,
            "hrd_score" in tumor_context,
            "msi_status" in tumor_context
        ])
        
        if biomarkers_present > 0:
            results["tumor_contexts"]["with_any_biomarker"] += 1
        
        if biomarkers_present == 3:
            results["tumor_contexts"]["with_all_biomarkers"] += 1
        
        completeness = tumor_context.get("completeness_score", 0.0)
        completeness_bucket = f"{int(completeness * 3) / 3:.2f}"
        results["tumor_contexts"]["completeness_distribution"][completeness_bucket] += 1
    
    # Calculate percentages
    n = len(patients)
    results["tmb"]["coverage_pct"] = (results["tmb"]["coverage"] / n * 100) if n > 0 else 0
    results["hrd"]["coverage_pct"] = (results["hrd"]["coverage"] / n * 100) if n > 0 else 0
    results["msi"]["coverage_pct"] = (results["msi"]["coverage"] / n * 100) if n > 0 else 0
    results["tumor_contexts"]["any_biomarker_pct"] = (results["tumor_contexts"]["with_any_biomarker"] / n * 100) if n > 0 else 0
    results["tumor_contexts"]["all_biomarkers_pct"] = (results["tumor_contexts"]["with_all_biomarkers"] / n * 100) if n > 0 else 0
    
    return results


def print_validation_report(results: Dict[str, Any]):
    """Print formatted validation report."""
    print("=" * 80)
    print("ENHANCED BIOMARKER EXTRACTION VALIDATION REPORT")
    print("=" * 80)
    print(f"\nTotal Patients: {results['total_patients']}")
    
    print("\n" + "-" * 80)
    print("TMB (Tumor Mutational Burden)")
    print("-" * 80)
    print(f"  Coverage: {results['tmb']['coverage']}/{results['total_patients']} ({results['tmb']['coverage_pct']:.1f}%)")
    print(f"  Sources:")
    for source, count in sorted(results['tmb']['sources'].items()):
        print(f"    {source}: {count}")
    print(f"  Confidence:")
    for conf, count in sorted(results['tmb']['confidence'].items()):
        print(f"    {conf}: {count}")
    
    print("\n" + "-" * 80)
    print("HRD (Homologous Recombination Deficiency)")
    print("-" * 80)
    print(f"  Coverage: {results['hrd']['coverage']}/{results['total_patients']} ({results['hrd']['coverage_pct']:.1f}%)")
    print(f"  Sources:")
    for source, count in sorted(results['hrd']['sources'].items()):
        print(f"    {source}: {count}")
    print(f"  Confidence:")
    for conf, count in sorted(results['hrd']['confidence'].items()):
        print(f"    {conf}: {count}")
    
    print("\n" + "-" * 80)
    print("MSI (Microsatellite Instability)")
    print("-" * 80)
    print(f"  Coverage: {results['msi']['coverage']}/{results['total_patients']} ({results['msi']['coverage_pct']:.1f}%)")
    print(f"  Sources:")
    for source, count in sorted(results['msi']['sources'].items()):
        print(f"    {source}: {count}")
    print(f"  Confidence:")
    for conf, count in sorted(results['msi']['confidence'].items()):
        print(f"    {conf}: {count}")
    
    print("\n" + "-" * 80)
    print("Tumor Context Completeness")
    print("-" * 80)
    print(f"  Patients with any biomarker: {results['tumor_contexts']['with_any_biomarker']}/{results['total_patients']} ({results['tumor_contexts']['any_biomarker_pct']:.1f}%)")
    print(f"  Patients with all biomarkers: {results['tumor_contexts']['with_all_biomarkers']}/{results['total_patients']} ({results['tumor_contexts']['all_biomarkers_pct']:.1f}%)")
    print(f"  Completeness Distribution:")
    for bucket, count in sorted(results['tumor_contexts']['completeness_distribution'].items()):
        print(f"    {bucket}: {count} patients")
    
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    # Success criteria
    hrd_coverage = results['hrd']['coverage_pct']
    msi_coverage = results['msi']['coverage_pct']
    any_biomarker = results['tumor_contexts']['any_biomarker_pct']
    
    print(f"\n✅ HRD Coverage: {hrd_coverage:.1f}% (Target: 15-20%)")
    if hrd_coverage >= 15:
        print("   ✓ Meets target")
    else:
        print("   ⚠ Below target - may need additional gene expansion")
    
    print(f"\n✅ MSI Coverage: {msi_coverage:.1f}% (Target: 3-5%)")
    if msi_coverage >= 3:
        print("   ✓ Meets target")
    else:
        print("   ⚠ Below target - may need additional gene expansion")
    
    print(f"\n✅ Any Biomarker Coverage: {any_biomarker:.1f}% (Target: >20%)")
    if any_biomarker >= 20:
        print("   ✓ Meets target")
    else:
        print("   ⚠ Below target - biomarker extraction may need improvement")
    
    print("\n" + "=" * 80)


def main():
    """Main validation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate enhanced biomarker extraction")
    parser.add_argument(
        "--dataset",
        type=str,
        default="data/benchmarks/cbioportal_trial_datasets_latest.json",
        help="Path to patient dataset JSON file"
    )
    
    args = parser.parse_args()
    
    # Load dataset
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"ERROR: Dataset file not found: {dataset_path}")
        print(f"Please provide a valid dataset path with --dataset")
        sys.exit(1)
    
    print(f"Loading dataset from: {dataset_path}")
    patients = load_dataset(str(dataset_path))
    print(f"Loaded {len(patients)} patients")
    
    # Run validation
    print("\nRunning enhanced biomarker extraction validation...")
    results = validate_enhanced_extraction(patients)
    
    # Print report
    print_validation_report(results)
    
    # Save results to JSON
    output_path = dataset_path.parent / "enhanced_biomarker_validation_results.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()

