#!/usr/bin/env python3
"""
Audit TCGA Biomarkers: Check what biomarker fields are actually available.

Run this BEFORE running benchmarks to understand data availability.
"""

import sys
import json
from pathlib import Path
from collections import Counter
from typing import Dict, Any, List

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "benchmarks"


def load_dataset() -> List[Dict[str, Any]]:
    """Load TCGA dataset."""
    dataset_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    
    if not dataset_file.exists():
        print(f"❌ Dataset not found: {dataset_file}")
        sys.exit(1)
    
    with open(dataset_file, 'r') as f:
        data = json.load(f)
    
    # Extract patients
    patients = []
    if isinstance(data, list):
        for study in data:
            for patient in study.get("patients", []):
                patients.append(patient)
    elif isinstance(data, dict):
        for study_data in data.values():
            for patient in study_data.get("patients", []):
                patients.append(patient)
    
    return patients


def audit_biomarker_fields(patients: List[Dict]) -> Dict[str, Any]:
    """Audit what biomarker fields are available in the dataset."""
    
    # Fields to check
    tmb_fields = ["TMB_NONSYNONYMOUS", "TMB_SCORE", "TMB", "MUTATION_COUNT"]
    hrd_fields = ["HRD_SCORE", "HRD", "HRD_STATUS", "HOMOLOGOUS_RECOMBINATION_DEFICIENCY"]
    msi_fields = ["MSI_STATUS", "MSI", "MSI_SCORE", "MICROSATELLITE_INSTABILITY"]
    other_fields = ["BRCA1_STATUS", "BRCA2_STATUS", "BRCA_STATUS", "PD_L1_STATUS", "PD_L1_SCORE"]
    
    all_fields = tmb_fields + hrd_fields + msi_fields + other_fields
    
    # Count availability
    field_counts = {field: 0 for field in all_fields}
    field_values = {field: Counter() for field in all_fields}
    
    # Track all clinical outcome fields seen
    all_clinical_fields = Counter()
    
    # Gene mutation counts
    brca1_count = 0
    brca2_count = 0
    mmr_count = 0
    
    for patient in patients:
        outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
        
        # Check each field
        for field in all_fields:
            if outcomes.get(field) is not None:
                field_counts[field] += 1
                value = str(outcomes.get(field))[:50]  # Truncate long values
                field_values[field][value] += 1
        
        # Track all fields
        if isinstance(outcomes, dict):
            for key in outcomes.keys():
                all_clinical_fields[key] += 1
        
        # Check mutations for BRCA and MMR genes
        mutations = patient.get("mutations", [])
        genes = [m.get("gene", "").upper() for m in mutations]
        
        if "BRCA1" in genes:
            brca1_count += 1
        if "BRCA2" in genes:
            brca2_count += 1
        if any(g in genes for g in ["MLH1", "MSH2", "MSH6", "PMS2"]):
            mmr_count += 1
    
    return {
        "total_patients": len(patients),
        "field_counts": field_counts,
        "field_values": {k: dict(v.most_common(5)) for k, v in field_values.items()},
        "all_clinical_fields": dict(all_clinical_fields.most_common(30)),
        "mutation_based": {
            "brca1_mutations": brca1_count,
            "brca2_mutations": brca2_count,
            "mmr_mutations": mmr_count,
        }
    }


def print_audit_report(audit: Dict[str, Any]):
    """Print audit report."""
    n = audit["total_patients"]
    
    print("\n" + "=" * 70)
    print("📊 TCGA BIOMARKER AUDIT REPORT")
    print("=" * 70)
    print(f"\nTotal patients: {n}")
    
    print("\n" + "-" * 70)
    print("TMB FIELDS")
    print("-" * 70)
    for field in ["TMB_NONSYNONYMOUS", "TMB_SCORE", "TMB", "MUTATION_COUNT"]:
        count = audit["field_counts"].get(field, 0)
        pct = count / n * 100 if n > 0 else 0
        values = audit["field_values"].get(field, {})
        print(f"  {field}: {count}/{n} ({pct:.1f}%)")
        if values:
            print(f"    Sample values: {dict(list(values.items())[:3])}")
    
    print("\n" + "-" * 70)
    print("HRD FIELDS")
    print("-" * 70)
    for field in ["HRD_SCORE", "HRD", "HRD_STATUS"]:
        count = audit["field_counts"].get(field, 0)
        pct = count / n * 100 if n > 0 else 0
        values = audit["field_values"].get(field, {})
        print(f"  {field}: {count}/{n} ({pct:.1f}%)")
        if values:
            print(f"    Sample values: {dict(list(values.items())[:3])}")
    
    print("\n" + "-" * 70)
    print("MSI FIELDS")
    print("-" * 70)
    for field in ["MSI_STATUS", "MSI", "MSI_SCORE"]:
        count = audit["field_counts"].get(field, 0)
        pct = count / n * 100 if n > 0 else 0
        values = audit["field_values"].get(field, {})
        print(f"  {field}: {count}/{n} ({pct:.1f}%)")
        if values:
            print(f"    Sample values: {dict(list(values.items())[:3])}")
    
    print("\n" + "-" * 70)
    print("MUTATION-BASED ESTIMATES")
    print("-" * 70)
    mb = audit["mutation_based"]
    print(f"  BRCA1 mutations: {mb['brca1_mutations']}/{n} ({mb['brca1_mutations']/n*100:.1f}%)")
    print(f"  BRCA2 mutations: {mb['brca2_mutations']}/{n} ({mb['brca2_mutations']/n*100:.1f}%)")
    print(f"  MMR mutations: {mb['mmr_mutations']}/{n} ({mb['mmr_mutations']/n*100:.1f}%)")
    
    print("\n" + "-" * 70)
    print("ALL CLINICAL FIELDS (Top 20)")
    print("-" * 70)
    for field, count in list(audit["all_clinical_fields"].items())[:20]:
        pct = count / n * 100 if n > 0 else 0
        print(f"  {field}: {count} ({pct:.1f}%)")
    
    print("\n" + "=" * 70)
    print("IMPLICATIONS FOR BENCHMARK")
    print("=" * 70)
    
    # TMB assessment
    tmb_direct = audit["field_counts"].get("TMB_NONSYNONYMOUS", 0)
    mutation_count = audit["field_counts"].get("MUTATION_COUNT", 0)
    
    if tmb_direct > n * 0.5:
        print(f"✅ TMB: Direct field available ({tmb_direct}/{n})")
    elif mutation_count > n * 0.5:
        print(f"⚠️ TMB: Using MUTATION_COUNT estimate ({mutation_count}/{n})")
    else:
        print(f"❌ TMB: Limited coverage, will estimate from mutations")
    
    # HRD assessment
    hrd_direct = audit["field_counts"].get("HRD_SCORE", 0)
    brca_count = mb['brca1_mutations'] + mb['brca2_mutations']
    
    if hrd_direct > n * 0.1:
        print(f"✅ HRD: Direct field available ({hrd_direct}/{n})")
    else:
        print(f"⚠️ HRD: NO direct HRD field - BRCA estimation only ({brca_count}/{n} BRCA+)")
        print(f"   → This means {n - brca_count} patients will get HRD=20 (low)")
    
    # MSI assessment
    msi_direct = audit["field_counts"].get("MSI_STATUS", 0)
    
    if msi_direct > n * 0.1:
        print(f"✅ MSI: Direct field available ({msi_direct}/{n})")
    else:
        print(f"⚠️ MSI: NO direct MSI field - MMR estimation only ({mb['mmr_mutations']}/{n} MMR+)")
        print(f"   → This means {n - mb['mmr_mutations']} patients will get MSS")


def main():
    print("Loading TCGA dataset...")
    patients = load_dataset()
    
    print(f"Auditing {len(patients)} patients...")
    audit = audit_biomarker_fields(patients)
    
    print_audit_report(audit)
    
    # Save audit results
    audit_file = OUTPUT_DIR / "tcga_biomarker_audit.json"
    with open(audit_file, 'w') as f:
        json.dump(audit, f, indent=2)
    print(f"\n💾 Audit results saved to: {audit_file}")


if __name__ == "__main__":
    main()

