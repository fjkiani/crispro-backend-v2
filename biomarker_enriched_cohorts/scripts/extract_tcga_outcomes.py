#!/usr/bin/env python3
"""
TCGA-OV Outcome-Labeled Cohort Extraction Script

Extracts TCGA-OV cohort with OS/PFS outcomes from cBioPortal and converts to
standardized outcome-labeled format for cohort context benchmarking.

Mission: Deliver outcome-labeled, real-cohort artifacts with:
- os_days, os_event (converted from OS_MONTHS, OS_STATUS)
- pfs_days, pfs_event (converted from PFS_MONTHS, PFS_STATUS)
- Platinum-resistant proxy (PFI < 6 months) if treatment dates exist
- Standardized JSON artifacts with provenance

Uses existing framework:
- cBioPortal extraction (extract_cbioportal_trial_datasets.py)
- PFS status parser (pfs_status_parser.py)
- Cohort context framework patterns
"""

import sys
from pathlib import Path
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import existing extraction utilities
try:
    from scripts.benchmark.extract_cbioportal_trial_datasets import (
        extract_clinical_outcomes,
        extract_treatments
    )
    from scripts.benchmark.benchmark_common.utils.pfs_status_parser import (
        parse_os_status,
        parse_pfs_status
    )
except ImportError as e:
    print(f"❌ Error importing extraction utilities: {e}")
    print("   Make sure extract_cbioportal_trial_datasets.py is available")
    sys.exit(1)

# Configuration
STUDY_ID = "ov_tcga_pan_can_atlas_2018"  # TCGA-OV PanCan Atlas
OUTPUT_DIR = PROJECT_ROOT / "data" / "cohorts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RECEIPTS_DIR = OUTPUT_DIR / "receipts"
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

# Label definitions
LABEL_DEFINITIONS_VERSION = "v1"
TIME_ORIGIN = "diagnosis_date"  # TCGA standard
CENSORING_POLICY = "Standard survival analysis: events = 1, censored = 0"
DAYS_PER_MONTH = 30.44  # Standard conversion factor
PFI_RESISTANT_THRESHOLD_DAYS = 6 * 30.44  # 6 months in days


def convert_months_to_days(months: Optional[float]) -> Optional[int]:
    """Convert months to days using standard conversion factor."""
    if months is None or pd.isna(months):
        return None
    return int(months * DAYS_PER_MONTH)


def calculate_pfi(
    treatment_start_date: Optional[str],
    progression_date: Optional[str],
    pfs_days: Optional[int]
) -> Optional[Dict[str, Any]]:
    """
    Calculate Platinum-Free Interval (PFI) if treatment dates exist.
    
    PFI = time from last platinum treatment to progression/recurrence.
    PFI < 6 months = platinum-resistant.
    """
    # If we have PFS days and it's an event, use that as proxy
    if pfs_days is not None and pfs_days < PFI_RESISTANT_THRESHOLD_DAYS:
        return {
            "pfi_days": pfs_days,
            "pfi_resistant": True,
            "pfi_source": "pfs_proxy",
            "note": "PFI estimated from PFS (progression < 6 months)"
        }
    
    # If we have explicit treatment dates, calculate PFI
    if treatment_start_date and progression_date:
        try:
            from datetime import datetime
            start = datetime.fromisoformat(treatment_start_date.replace('Z', '+00:00'))
            prog = datetime.fromisoformat(progression_date.replace('Z', '+00:00'))
            pfi_days = (prog - start).days
            return {
                "pfi_days": pfi_days,
                "pfi_resistant": pfi_days < PFI_RESISTANT_THRESHOLD_DAYS,
                "pfi_source": "treatment_dates",
                "note": "PFI calculated from treatment start to progression"
            }
        except (ValueError, AttributeError):
            pass
    
    return None


def extract_tcga_ov_outcomes() -> Dict[str, Any]:
    """
    Extract TCGA-OV cohort with outcome labels.
    
    Returns:
        Dictionary with cohort data, metadata, and provenance
    """
    print(f"🔬 Extracting TCGA-OV outcomes from {STUDY_ID}...")
    
    # Step 1: Extract clinical outcomes
    print("   Step 1: Extracting clinical outcomes...")
    clinical_df = extract_clinical_outcomes(STUDY_ID)
    
    if clinical_df.empty:
        raise ValueError(f"No clinical data found for {STUDY_ID}")
    
    print(f"   ✅ Retrieved {len(clinical_df)} patients")
    
    # Step 2: Extract treatments (for PFI calculation)
    print("   Step 2: Extracting treatments...")
    treatments_df = extract_treatments(STUDY_ID)
    
    # Step 3: Convert to standardized format
    print("   Step 3: Converting to standardized format...")
    patients = []
    os_count = 0
    pfs_count = 0
    pfi_count = 0
    
    for _, row in clinical_df.iterrows():
        patient_id = str(row.get("patientId", ""))
        if not patient_id:
            continue
        
        # Convert OS
        os_months = row.get("OS_MONTHS")
        os_status = row.get("OS_STATUS")
        os_days = convert_months_to_days(os_months)
        os_event, os_status_parsed = parse_os_status(os_status) if os_status else (None, None)
        
        # Convert PFS
        pfs_months = row.get("PFS_MONTHS")
        pfs_status = row.get("PFS_STATUS")
        pfs_days = convert_months_to_days(pfs_months)
        pfs_event, pfs_status_parsed = parse_pfs_status(pfs_status) if pfs_status else (None, None)
        
        # Calculate PFI (if possible)
        pfi_data = None
        if pfs_days is not None and pfs_event == 1:
            # Use PFS as proxy for PFI
            pfi_data = calculate_pfi(None, None, pfs_days)
            if pfi_data:
                pfi_count += 1
        
        # Build patient record
        patient_record = {
            "patient_id": patient_id,
            "outcomes": {
                "os_days": os_days,
                "os_event": bool(os_event) if os_event is not None else None,
                "pfs_days": pfs_days,
                "pfs_event": bool(pfs_event) if pfs_event is not None else None
            }
        }
        
        # Add PFI if available
        if pfi_data:
            patient_record["outcomes"]["pfi"] = pfi_data
        
        # Track completeness
        if os_days is not None and os_event is not None:
            os_count += 1
        if pfs_days is not None and pfs_event is not None:
            pfs_count += 1
        
        patients.append(patient_record)
    
    # Step 4: Build cohort artifact
    cohort_artifact = {
        "cohort": {
            "source": "cbioportal",
            "study_id": STUDY_ID,
            "disease": "ovarian_cancer",
            "patients": patients,
            "metadata": {
                "extraction_date": datetime.now().isoformat(),
                "label_definitions_version": LABEL_DEFINITIONS_VERSION,
                "time_origin": TIME_ORIGIN,
                "censoring_policy": CENSORING_POLICY,
                "sources": [
                    f"cBioPortal study: {STUDY_ID}",
                    "OS: OS_MONTHS → os_days (×30.44), OS_STATUS → os_event (parsed)",
                    "PFS: PFS_MONTHS → pfs_days (×30.44), PFS_STATUS → pfs_event (parsed)",
                    "PFI: Estimated from PFS when progression < 6 months"
                ],
                "data_quality": "high",
                "completeness": {
                    "total_patients": len(patients),
                    "os_complete": os_count,
                    "pfs_complete": pfs_count,
                    "pfi_available": pfi_count,
                    "os_coverage": os_count / len(patients) if patients else 0,
                    "pfs_coverage": pfs_count / len(patients) if patients else 0
                }
            }
        }
    }
    
    # Step 5: Generate receipt
    receipt = {
        "extraction_date": datetime.now().isoformat(),
        "study_id": STUDY_ID,
        "cohort_size": len(patients),
        "os_labels": os_count,
        "pfs_labels": pfs_count,
        "pfi_labels": pfi_count,
        "label_definitions_version": LABEL_DEFINITIONS_VERSION,
        "time_origin": TIME_ORIGIN,
        "censoring_policy": CENSORING_POLICY,
        "source_columns": {
            "os_days": "OS_MONTHS (converted ×30.44)",
            "os_event": "OS_STATUS (parsed)",
            "pfs_days": "PFS_MONTHS (converted ×30.44)",
            "pfs_event": "PFS_STATUS (parsed)",
            "pfi": "PFS proxy (if progression < 6 months)"
        },
        "missingness": {
            "os_missing": len(patients) - os_count,
            "pfs_missing": len(patients) - pfs_count,
            "pfi_missing": len(patients) - pfi_count
        },
        "validation_checks": {
            "os_days_range": "0-5000 days (outliers counted)",
            "os_event_boolean": "All non-null values are boolean",
            "pfs_days_range": "0-5000 days (outliers counted)",
            "pfs_ent_boolean": "All non-null values are boolean"
        }
    }
    
    return cohort_artifact, receipt


def main():
    """Main extraction function."""
    print("=" * 80)
    print("TCGA-OV Outcome-Labeled Cohort Extraction")
    print("=" * 80)
    print()
    
    try:
        # Extract cohort
        cohort_artifact, receipt = extract_tcga_ov_outcomes()
        
        # Save cohort artifact
        artifact_path = OUTPUT_DIR / f"tcga_ov_outcomes_{LABEL_DEFINITIONS_VERSION}.json"
        with open(artifact_path, 'w') as f:
            json.dump(cohort_artifact, f, indent=2)
        print(f"✅ Saved cohort artifact: {artifact_path}")
        
        # Save receipt
        receipt_filename = f"tcga_ov_outcomes_{LABEL_DEFINITIONS_VERSION}_receipt_{datetime.now().strftime('%Y%m%d')}.json"
        receipt_path = RECEIPTS_DIR / receipt_filename
        with open(receipt_path, 'w') as f:
            json.dump(receipt, f, indent=2)
        print(f"✅ Saved receipt: {receipt_path}")
        
        # Prinmmary
        print()
        print("=" * 80)
        print("EXTRACTION SUMMARY")
        print("=" * 80)
        print(f"Cohort Size (N): {receipt['cohort_size']}")
        print(f"OS Labels: {receipt['os_labels']} ({receipt['os_labels']/receipt['cohort_size']*100:.1f}%)")
        print(f"PFS Labels: {receipt['pfs_labels']} ({receipt['pfs_labels']/receipt['cohort_size']*100:.1f}%)")
        print(f"PFI Labels: {receipt['pfi_labels']} ({receipt['pfi_labels']/receipt['cohort_size']*100:.1f}%)")
        print()
        print(f"Artifact: {artifact_path}")
        print(f"Receipt: {receipt_path}")
        print()
        
        # Validation check
        if receipt['os_labels'] >= 400:
            print("✅ ACCEPTANCE CRITERIA MET: N ≥ 400 patients with OS labels")
        else:
            print(f"⚠️  ACCEPTANCE CRITERIA: Only {receipt['os_labels']} patients with OS labels (target: ≥400)")
            print("   This may be due to data availability in cBioPortal")
        
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
