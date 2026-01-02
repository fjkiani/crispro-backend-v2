#!/usr/bin/env python3
"""
Merge Biomarker Data into Enriched Cohort

This script merges all extracted biomarker data into a final enriched cohort
with derived status fields (MSI status, HRD proxy).

Prerequisites:
    - Run extract_tcga_outcomes.py first (creates base cohort)
    - Run extract_tcga_biomarkers.py (creates biomarker + BRCA data)

Usage:
    cd oncology-coPilot/oncology-backend-minimal
    python3 scripts/cohorts/merge_enriched_cohort.py

Output:
    data/cohorts/tcga_ov_enriched_v2.json
    data/cohorts/receipts/tcga_ov_enriched_v2_receipt_*.json
"""
import json
from pathlib import Path
from datetime import datetime

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "cohorts"


def derive_msi_status(msi_mantis, msi_sensor):
    """
    Derive MSI status from MANTIS and MSIsensor scores.
    
    Thresholds:
    - MANTIS: > 0.4 = MSI-H
    - MSIsensor: > 3.5 = MSI-H
    """
    if msi_mantis is not None and msi_mantis > 0.4:
        return "MSI-H"
    elif msi_sensor is not None and msi_sensor > 3.5:
        return "MSI-H"
    elif msi_mantis is not None or msi_sensor is not None:
        return "MSS"
    return "Unknown"


def derive_hrd_proxy(aneuploidy, fga):
    """
    Derive HRD proxy from Aneuploidy score and Fraction Genome Altered.
    
    Thresholds:
    - HRD-High: Aneuploidy >= 15 AND FGA >= 0.4
    - HRD-Intermediate: Aneuploidy >= 10 OR FGA >= 0.3
    - HRD-Low: Otherwise
    """
    if aneuploidy is None or fga is None:
        return "Unknown"
    if aneuploidy >= 15 and fga >= 0.4:
        return "HRD-High"
    elif aneuploidy >= 10 or fga >= 0.3:
        return "HRD-Intermediate"
    return "HRD-Low"


def main():
    print("=" * 60)
    print("MERGING BIOMARKER DATA INTO ENRICHED COHORT")
    print("=" * 60)
    print()

    # Load base cohort
    base_cohort_file = OUTPUT_DIR / "tcga_ov_outcomes_v1.json"
    base_cohort = json.loads(base_cohort_file.read_text())
    print(f"Loaded base cohort from: {base_cohort_file}")

    # Get patients (handle nested structure)
    if "cohort" in base_cohort and "patients" in base_cohort["cohort"]:
        patients = base_cohort["cohort"]["patients"]
    else:
        patients = base_cohort.get("patients", [])
    print(f"  {len(patients)} patients in base cohort")

    # Load biomarker data
    biomarkers_file = OUTPUT_DIR / "tcga_ov_biomarkers_raw.json"
    biomarkers = json.loads(biomarkers_file.read_text())
    print(f"Loaded biomarkers from: {biomarkers_file}")

    # Load BRCA data
    brca_file = OUTPUT_DIR / "tcga_ov_brca_mutations.json"
    brca_data = json.loads(brca_file.read_text())
    print(f"Loaded BRCA mutations from: {brca_file}")

    brca1_patients = set(brca_data["brca1_patients"])
    brca2_patients = set(brca_data["brca2_patients"])
    any_brca_patients = set(brca_data["any_brca_patients"])

    # Get biomarker lookup
    biomarker_lookup = biomarkers.get("patients", {})

    # Enrich patients
    print()
    print("Enriching patients with biomarkers...")

    enriched_patients = []
    coverage = {
        "tmb": 0,
        "msi_score_mantis": 0,
        "msi_sensor_score": 0,
        "aneuploidy_score": 0,
        "fraction_genome_altered": 0,
        "brca_somatic": 0
    }

    for patient in patients:
        patient_id = patient.get("patient_id")
        enriched = patient.copy()
        
        # Get biomarker data for this patient
        bio = biomarker_lookup.get(patient_id, {})
        
        # Add TMB
        tmb = bio.get("TMB_NONSYNONYMOUS")
        enriched["tmb"] = tmb
        if tmb is not None:
            coverage["tmb"] += 1
        
        # Add MSI scores
        msi_mantis = bio.get("MSI_SCORE_MANTIS")
        msi_sensor = bio.get("MSI_SENSOR_SCORE")
        enriched["msi_score_mantis"] = msi_mantis
        enriched["msi_sensor_score"] = msi_sensor
        if msi_mantis is not None:
            coverage["msi_score_mantis"] += 1
        if msi_sensor is not None:
            coverage["msi_sensor_score"] += 1
        
        # Derive MSI status
        enriched["msi_status"] = derive_msi_status(msi_mantis, msi_sensor)
        
        # Add aneuploidy score (HRD proxy)
        aneuploidy = bio.get("ANEUPLOIDY_SCORE")
        enriched["aneuploidy_score"] = aneuploidy
        if aneuploidy is not None:
            coverage["aneuploidy_score"] += 1
        
        # Add fraction genome altered
        fga = bio.get("FRACTION_GENOME_ALTERED")
        enriched["fraction_genome_altered"] = fga
        if fga is not None:
            coverage["fraction_genome_altered"] += 1
        
        # Derive HRD proxy
        enriched["hrd_proxy"] = derive_hrd_proxy(aneuploidy, fga)
        
        # Add BRCA status (somatic)
        if patient_id in brca1_patients:
            enriched["brca_somatic"] = "BRCA1"
            coverage["brca_somatic"] += 1
        elif patient_id in brca2_patients:
            enriched["brca_somatic"] = "BRCA2"
            coverage["brca_somatic"] += 1
        else:
            enriched["brca_somatic"] = None
        
        # Germline BRCA unknown (TCGA is tumor-only)
        enriched["germline_brca_status"] = "unknown"
        
        enriched_patients.append(enriched)

    # Calculate statistics
    n = len(enriched_patients)
    msi_h_count = sum(1 for p in enriched_patients if p.get("msi_status") == "MSI-H")
    hrd_high_count = sum(1 for p in enriched_patients if p.get("hrd_proxy") == "HRD-High")

    print()
    print("=" * 60)
    print("COVERAGE REPORT")
    print("=" * 60)
    for field, count in coverage.items():
        pct = 100 * count / n if n > 0 else 0
        print(f"  {field}: {count}/{n} ({pct:.1f}%)")
    print()
    print(f"  MSI-H patients: {msi_h_count}")
    print(f"  HRD-High patients: {hrd_high_count}")

    # Create enriched cohort output
    output = {
        "cohort": {
            "source": "TCGA-OV PanCancer Atlas (ov_tcga_pan_can_atlas_2018)",
            "study_id": "ov_tcga_pan_can_atlas_2018",
            "disease": "Ovarian Cancer",
            "n_patients": len(enriched_patients),
            "enrichment_date": datetime.now().isoformat(),
            "biomarkers": ["tmb", "msi_score_mantis", "msi_sensor_score", "msi_status", 
                           "aneuploidy_score", "fraction_genome_altered", "hrd_proxy", 
                           "brca_somatic", "germline_brca_status"],
            "patients": enriched_patients
        },
        "coverage": {
            field: {"n": count, "pct": round(100 * count / n, 1)} 
            for field, count in coverage.items()
        },
        "derived_status": {
            "msi_h_count": msi_h_count,
            "hrd_high_count": hrd_high_count
        },
        "provenance": {
            "base_cohort": str(base_cohort_file),
            "biomarkers_source": "cBioPortal API (ov_tcga_pan_can_atlas_2018)",
            "brca_source": "cBioPortal mutations API",
            "tmb_field": "TMB_NONSYNONYMOUS (mutations/Mb)",
            "msi_fields": ["MSI_SCORE_MANTIS", "MSI_SENSOR_SCORE"],
            "msi_status_derivation": "MANTIS > 0.4 or MSIsensor > 3.5 = MSI-H",
            "hrd_proxy_derivation": "Aneuploidy >= 15 AND FGA >= 0.4 = HRD-High"
        }
    }

    # Save enriched cohort
    output_file = OUTPUT_DIR / "tcga_ov_enriched_v2.json"
    output_file.write_text(json.dumps(output, indent=2))
    print()
    print(f"✅ Saved enriched cohort: {output_file}")

    # Generate receipt
    receipt = {
        "extraction_date": datetime.now().isoformat(),
        "base_cohort": str(base_cohort_file),
        "n_patients": len(enriched_patients),
        "coverage": output["coverage"],
        "derived_status": output["derived_status"],
        "biomarkers": output["cohort"]["biomarkers"],
        "provenance": output["provenance"]
    }

    receipt_dir = OUTPUT_DIR / "receipts"
    receipt_dir.mkdir(exist_ok=True)
    receipt_file = receipt_dir / f"tcga_ov_enriched_v2_reipt_{datetime.now().strftime('%Y%m%d')}.json"
    receipt_file.write_text(json.dumps(receipt, indent=2))
    print(f"✅ Saved receipt: {receipt_file}")


if __name__ == "__main__":
    main()
