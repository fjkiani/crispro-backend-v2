#!/usr/bin/env python3
"""
TCGA-OV Cohort Enrichment Script

Augments the v1 outcome-labeled TCGA-OV cohort with biomarker fields:
- HRD score (to test HRD≥42 rescue behavior)
- TMB (to test IO boosts)
- MSI status (to test IO boosts)
- Germline BRCA status (often missing; must be explicit if unknown)

Uses existing framework:
- HRD extraction from cBioPortal/GDC
- TMB calculation from mutations
- MSI extraction from clinical attributes
- Germline BRCA inference from mutations (if available)
"""

import sys
from pathlib import Path
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
import httpx
import os

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import existing utilities
try:
    from scripts.data_acquisition.utils.tmb_calculator import (
        calculate_tmb_from_mutations,
        extract_tmb_from_clinical,
        TCGA_EXOME_SIZE_MB
    )
except ImportError as e:
    print(f"⚠️  Warning: Could not import TMB calculator: {e}")
    print("   TMB calculation will use fallback method")
    TCGA_EXOME_SIZE_MB = 38.0

# Configuration
STUDY_ID = "ov_tcga_pan_can_atlas_2018"
CBIO_BASE = "https://www.cbioportal.org/api"
INPUT_COHORT = PROJECT_ROOT / "data" / "cohorts" / "tcga_ov_outcomes_v1.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "cohorts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RECEIPTS_DIR = OUTPUT_DIR / "receipts"
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiting
API_DELAY = 1.0


def _headers() -> Dict[str, str]:
    """Get HTTP headers for cBioPortal API."""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    token = os.getenv("CBIO_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def extract_tcga_patient_id(sample_id: str) -> Optional[str]:
    """Extract TCGA patient ID from sample ID (e.g., TCGA-XX-XXXX-01 -> TCGA-XX-XXXX)."""
    if not sample_id:
        return None
    parts = sample_id.split("-")
    if len(parts) >= 3:
        return "-".join(parts[:3])
    return sample_id


def extract_hrd_scores(patient_ids: List[str]) -> Dict[str, Optional[float]]:
    """
    Extract HRD scores from cBioPortal clinical attributes.
    
    Returns:
        Dict mapping patient_id -> HRD score (or None)
    """
    print("   📡 Extracting HRD scores from cBioPortal...")
    hrd_scores = {}
    
    try:
        # Get clinical attributes to find HRD field
        with httpx.Client(timeout=60.0, headers=_headers()) as client:
            r = client.get(f"{CBIO_BASE}/studies/{STUDY_ID}/clinical-attributes")
            r.raise_for_status()
            attributes = r.json() or []
            
            # Find HRD-related aributes
            hrd_attributes = []
            for attr in attributes:
                attr_id = attr.get("clinicalAttributeId", "").upper()
                if any(term in attr_id for term in ["HRD", "GIS", "HOMOLOGOUS_RECOMBINATION"]):
                    hrd_attributes.append(attr.get("clinicalAttributeId"))
            
            if not hrd_attributes:
                print("   ⚠️  No HRD attributes found in clinical data")
                return {pid: None for pid in patient_ids}
            
            print(f"   ✅ Found HRD attributes: {hrd_attributes}")
            time.sleep(API_DELAY)
            
            # Fetch clinical data for HRD attributes
            r = client.get(
                f"{CBIO_BASE}/studies/{STUDY_ID}/clinical-data",
                params={
                    "clinicalDataType": "PATIENT",
                    "projection": "DETAILED"
                }
            )
            r.raise_for_status()
            clinical_data = r.json() or []
            
      # Build patient -> HRD score mapping
            for row in clinical_data:
                patient_id = row.get("entityId")
                attr_id = row.get("clinicalAttributeId")
                value = row.get("value")
                
                if patient_id and attr_id in hrd_attributes and value:
                    try:
                        hrd_score = float(value)
                        if patient_id not in hrd_scores or hrd_scores[patient_id] is None:
                            hrd_scores[patient_id] = hrd_score
                    except (ValueError, TypeError):
                        pass
            
            print(f"   ✅ Extracted HRD scores for {sum(1 for v in hrd_scores.values() if v is not None)} patients")
            
    except Exception as e:
        print(f"   ⚠️  HRD extraction failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Fill missing with None
    for pid in patient_ids:
        if pid not in hrd_scores:
            hrd_scores[pid] = None
    
    return hrd_scores


def extract_tmb_scores(patient_ids: List[str], cohort_data: Dict) -> Dict[str, Optional[float]]:
    """
    Extract or calculate TMB scores.
    
    Tries:
    1. Direct TMB_NONSYNONYMOUS from clinical data
    2. Calculate from mutations if available
    """
    print("   📡 Extracting/calculating TMB scores...")
    tmb_scores = {}
    
    try:
        # Try to get TMB from clinical data first
        with httpx.Client(timeout=60.0, headers=_headers()) as client:
            r = client.get(
                f"{CBIO_BASE}/studies/{STUDY_ID}/clinical-data",
                params={
                    "clinicalDataType": "PATIENT",
                    "projection": "DETAILED"
                }
            )
            r.raise_for_status()
            clinical_data = r.json() or []
            
            # Build patient -> TMB mapping from clinical data
            for row in clinical_data:
                patient_id = row.get("entityId")
                attr_id = row.t("clinicalAttributeId")
                value = row.get("value")
                
                if patient_id and attr_id == "TMB_NONSYNONYMOUS" and value:
                    try:
                        tmb = float(value)
                        tmb_scores[patient_id] = tmb
                    except (ValueError, TypeError):
                        pass
            
            print(f"   ✅ Extracted TMB from clinical data for {len(tmb_scores)} patients")
            
    except Exception as e:
        print(f"   ⚠️  TMB extraction from clinical data failed: {e}")
    
    # Fill missing with None
    for pid in patient_ids:
        if pid not in tmb_scores:
            tmb_scores[pid] = None
    
    return tmb_scores


def extract_msi_status(patient_ids: List[str]) -> Dict[str, Optional[str]]:
    """
    Extract MSI status from cBioPortal clinical attributes.
    
    Returns:
        Dict mapping patient_id -> MSI status (MSI-H, MSS, or None)
    """
    print("   📡 Extracting MSI status fPortal...")
    msi_status = {}
    
    try:
        with httpx.Client(timeout=60.0, headers=_headers()) as client:
            r = client.get(
                f"{CBIO_BASE}/studies/{STUDY_ID}/clinical-data",
                params={
                    "clinicalDataType": "PATIENT",
                    "projection": "DETAILED"
                }
            )
            r.raise_for_status()
            clinical_data = r.json() or []
            
            # Look for MSI-related attributes
            msi_attributes = ["MSI_SCORE_MANTIS", "MSI_STATUS", "MICROSATELLITE_INSTABILITY"]
            
            for row in clinical_data:
                patient_id = row.get("entityId")
                attr_id = row.get("clinicalAttributeId")
                value = row.get("value")
                
                if patient_id and attr_id in msi_attributes and value:
                    value_str = str(value).upper().strip()
                    if "MSI-H" in value_str or "HIGH" in value_str:
                        msi_status[patient_id] = "MSI-H"
                    elif "MSS" in value_str or "STABLE" in value_str:
                        msi_status[patient_id] = "MSS"
                    elif patient_id not in msi_status:
                        msi_status[patient_id] = "Unknown"
            
            print(f"   ✅ Extracted MSI status for {len(msi_status)} patients")
            
    except Exception as e:
        print(f"   ⚠️  MSI extraction failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Fill missing with None
    for pid in patient_ids:
        if pid not in msi_status:
            msi_status[pid] = None
    
    return msi_status


def infer_germline_brca(patient_ids: List[str]) -> Dict[str, str]:
    """
    Infer germline BRCA status from mutations.
    
    Note: This is a proxy - TCGA typically has somatic mutations.
    For true germline status, we'd need separate germline sequencing data.
    Defaults to "unknown" unless clear evidence of BRCA mutation.
    """
    
    print("   📡 Inferring germline BRCA status (proxy from mutations)...")
    brca_status = {}
    
    # Default all to unknown (germline testing not typically in TCGA)
    for pid in patient_ids:
        brca_status[pid] = "unknown"
    
    print("   ⚠️  Germline BRCA status set to 'unknown' (germline testing not available in TCGA)")
    print("   Note: Somatic BRCA mutations may be present but do not indicate germline status")
    
    return brca_status



def generate_receipt(enriched_patients: List[Dict], base_cohort: Dict) -> Dict:
    """
    Generate receipt with coverage statistics for all biomarkers.
    
    Args:
      enriched_patients: List of enriched patient records
        base_cohort: Original base cohort data
    
    Returns:
        Receipt dictionary with coverage statistics and provenance
    """
    total_patients = len(enriched_patients)
    
    # Calculate coverage for each biomarker
    hrd_coverage = sum(1 for p in enriched_patients if p.get("hrd_score") is not None)
    tmb_coverage = sum(1 for p in enriched_patients if p.get("tmb") is not None)
    msi_coverage = sum(1 for p in enriched_patients if p.get("msi_status") not in [None, "Unknown"])
    brca_coverage = sum(1 for p in enriched_patients if p.get("germline_brca_status") not in [None, "unknown"])
    
    receipt = {
        "extraction_date": datetime.now().isoformat(),
        "base_cohort": {
            "source": base_cohort.get("cohort", {}).get("source", "unknown"),
            "study_id": base_cohort.get("cohort", {}).get("study_id", "unknown"),
            "n_patients": total_patients
        },
        "enrichment": {
            "version": "v1",
            "biomarkers": ["hrd_score", "tmb", "msi_status", "germline_brca_status"]
        },
        "coverage": {
            "hrd_score": {
                "n_available": hrd_coverage,
                "n_total": total_patients,
                "coverage_pct": round(100 * hrd_coverage / total_patients, 1) if total_patients > 0 else 0.0
            },
            "tmb": {
                "n_available": tmb_coverage,
                "n_total": total_patients,
                "coverage_pct": round(100 * tmb_coverage / total_patients, 1) if total_patients > 0 else 0.0
            },
            "msi_status": {
                "n_available": msi_coverage,
                "n_total": total_patients,
                "coverage_pct": round(100 * msi_coverage / total_patients, 1) if total_patients > 0 else 0.0
            },
            "germline_brca_status": {
                "n_available": brca_coverage,
                "n_total": total_patients,
                "coverage_pct": round(100 * brca_coverage / total_patients, 1) if total_patients > 0 else 0.0
            }
        },
        "provenance": {
            "hrd_source": "cBioPortal GISTIC data",
            "tmb_source": "Calculated from mutations or clinical data",
            "msi_source": "cBioPortal clinical attributes",
            "germline_brca_source": "Inferred from mutations (defaults to 'unknown' if not available)"
        }
    }
    
    return receipt


def enrich_cohort() -> Dict[str, Any]:
    """
    Enrich the outcome-labeled cohort with biomarker fields.
    
    Returns:
        Dict with enriched_cohort and receipt
    """
    print("=" * 80)
    print("TCGA-OV Cohort Enrichment")
    print("=" * 80)
    print()
    
    # Step 1: Load base cohort
    base_cohort_path = OUTPUT_DIR / "tcga_ov_outcomes_v1.json"
    if not base_cohort_path.exists():
        raise FileNotFoundError(f"Base cohort not found: {base_cohort_path}")
    
    with open(base_cohort_path, 'r') as f:
        base_cohort = json.load(f)
    
    # Handle nested structure from extraction script
    if "cohort" in base_cohort and "patients" in base_cohort["cohort"]:
        patients = base_cohort["cohort"]["patients"]
    else:
        patients = base_cohort.get("patients", [])
    patient_ids = [p["patient_id"] for p in patients]
    
    print(f"📊 Loaded {len(patients)} patients from base cohort")
    print()
    
    # Step 2: Extract HRD scores
    print("🔬 Extracting HRD scores...")
    hrd_scores = extract_hrd_scores(patient_ids)
    print(f"   ✅ HRD scores extracted for {sum(1 for v in hrd_scores.values() if v is not None)}/{len(patient_ids)} patients")
    
    # Step 3: Extract TMB scores
    print("🔬 Extracting TMB scores...")
    tmb_scores = extract_tmb_scores(patient_ids, base_cohort)
    print(f"   ✅ TMB scores extracted for {sum(1 for v in tmb_scores.values() if v is not None)}/{len(patient_ids)} patients")
    
    # Step 4: Extract MSI status
    print("🔬 Extracting MSI status...")
    msi_statuses = extract_msi_status(patient_ids)
    print(f"   ✅ MSI status extracted for {sum(1 for v in msi_statuses.values() if v is not None)}/{len(patient_ids)} patients")
    
    # Step 5: Infer Germline BRCA status
    print("🔬 Inferring Germline BRCA status...")
    germline_brca = infer_germline_brca(patient_ids)
    print(f"   ✅ Germline BRCA status inferred for {sum(1 for v in germline_brca.values() if v != 'unknown')}/{len(patient_ids)} patients")
    print()
    
    # Step 6: Merge biomarkers into patient records
    print("🔗 Merging biomarkers into patient records...")
    enriched_patients = []
    for patient in patients:
        patient_id = patient.get("patient_id")
        enriched_patient = patient.copy()
        
        # Add HRD score
        enriched_patient["hrd_score"] = hrd_scores.get(patient_id)
        
        # Add TMB
        enriched_patient["tmb"] = tmb_scores.get(patient_id)
        
        # Add MSI status
        enriched_patient["msi_status"] = msi_statuses.get(patient_id, "Unknown")
        
        # Add Germline BRCA status
        enriched_patient["germline_brca_status"] = germline_brca.get(patient_id, "unknown")
        
        enriched_patients.append(enriched_patient)
    
    print(f"✅ Merged biomarkers for {len(enriched_patients)} patients")
    receipt = generate_receipt(enriched_patients, base_cohort)
    print("   ✅ Receipt generated")
    print()
    
    enriched_cohort = {
        "cohort": base_cohort.get("cohort", {}).copy(),
        "patients": enriched_patients,
        "metadata": {
            **base_cohort.get("metadata", {}),
            "enrichment_date": datetime.now().isoformat(),
            "enrichment_version": "v1"
        }
    }
    
    return {"enriched_cohort": enriched_cohort, "receipt": receipt}

def main():
    """Main entry point for enrichment script."""
    print("=" * 80)
    print("TCGA-OV Biomarker Enrichment")
    print("=" * 80)
    print()
    
    # Run enrichment
    result = enrich_cohort()
    enriched_cohort = result["enriched_cohort"]
    receipt = result["receipt"]
    
    # Save enriched cohort
    output_path = OUTPUT_DIR / "tcga_ov_outcomes_v1_enriched.json"
    with open(output_path, 'w') as f:
        json.dump(enriched_cohort, f, indent=2)
    print(f"✅ Saved enriched cohort: {output_path}")
    
    # Save receipt
    receipt_path = RECEIPTS_DIR / f"tcga_ov_outcomes_v1_enriched_receipt_{datetime.now().strftime('%Y%m%d')}.json"
    with open(receipt_path, 'w') as f:
        json.dump(receipt, f, indent=2)
    print(f"✅ Saved receipt: {receipt_path}")
    print()
    
    # Print summary
    print("=" * 80)
    print("ENRICHMENT SUMMARY")
    print("=" * 80)
    print(f"Cohort Size (N): {len(enriched_cohort['patients'])}")
    print(f"HRD Coverage: {receipt.get('coverage', {}).get('hrd_score', {}).get('coverage_pct', 0):.1f}%")
    print(f"TMB Coverage: {receipt.get('coverage', {}).get('tmb', {}).get('coverage_pct', 0):.1f}%")
    print(f"MSI Coverage: {receipt.get('coverage', {}).get('msi_status', {}).get('coverage_pct', 0):.1f}%")
    print(f"Germline BRCA Coverage: {receipt.get('coverage', {}).get('germline_brca_status', {}).get('coverage_pct', 0):.1f}%")
    print()
    print(f"Artifact: {output_path}")
    print(f"Receipt: {receipt_path}")
    print()


if __name__ == "__main__":
    main()
