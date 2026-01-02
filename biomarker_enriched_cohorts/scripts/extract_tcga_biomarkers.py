#!/usr/bin/env python3
"""
TCGA Biomarker Extraction Script

This script extracts biomarker data (TMB, MSI, Aneuploidy, BRCA) from cBioPortal
for TCGA-OV PanCancer Atlas study.

CRITICAL: Use ov_tcga_pan_can_atlas_2018 study (NOT ov_tcga legacy)

Usage:
    cd oncology-coPilot/oncology-backend-minimal
    python3 scripts/cohorts/extract_tcga_biomarkers.py

Output:
    data/cohorts/tcga_ov_biomarkers_raw.json
    data/cohorts/tcga_ov_brca_mutations.json
"""
import requests
import json
from pathlib import Path
from datetime import datetime

# Configuration
STUDY_ID = "ov_tcga_pan_can_atlas_2018"  # CRITICAL: Use PanCancer Atlas!
MUTATION_PROFILE = f"{STUDY_ID}_mutations"
BRCA1_ENTREZ = 672
BRCA2_ENTREZ = 675

BIOMARKER_ATTRS = [
    "TMB_NONSYNONYMOUS",
    "MSI_SCORE_MANTIS", 
    "MSI_SENSOR_SCORE",
    "ANEUPLOIDY_SCORE",
    "FRACTION_GENOME_ALTERED",
    "MUTATION_COUNT"
]

# Output directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "cohorts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_clinical_biomarkers():
    """Extract clinical biomarker data from cBioPortal."""
    print("=" * 60)
    print("EXTRACTING BIOMARKER DATA FROM TCGA-OV PANCANCER ATLAS")
    print("=" * 60)
    print()

    # Step 1: Get all samples
    print("📊 Step 1: Fetching samples...")
    samples_url = f"https://www.cbioportal.org/api/studies/{STUDY_ID}/samples"
    resp = requests.get(samples_url, timeout=60)
    samples = resp.json()
    print(f"   ✅ Found {len(samples)} samples")

    sample_to_patient = {s["sampleId"]: s["patientId"] for s in samples}

    # Step 2: Fetch clinical data
    print()
    print("📊 Step 2: Fetching clinical data (sample-level attributes)...")
    clinical_url = f"https://www.cbioportal.orgtudies/{STUDY_ID}/clinical-data"
    params = {"clinicalDataType": "SAMPLE", "projection": "DETAILED"}
    resp = requests.get(clinical_url, params=params, timeout=120)
    clinical_data = resp.json()
    print(f"   ✅ Retrieved {len(clinical_data)} clinical data points")

    # Step 3: Parse and aggregate by patient
    print()
    print("📊 Step 3: Aggregating biomarker data by patient...")

    sample_data = {}
    for cd in clinical_data:
        sample_id = cd.get("sampleId")
        attr_id = cd.get("clinicalAttributeId")
        value = cd.get("value")
        
        if sample_id not in sample_data:
            sample_data[sample_id] = {}
        
        if attr_id in BIOMARKER_ATTRS and value:
            try:
                sample_data[sample_id][attr_id] = float(value)
            except:
                sample_data[sample_id][attr_id] = value

    # Aggregate to patient level
    patient_biomarkers = {}
    for sample_id, attrs in sample_data.items():
        patient_id = sample_to_patient.get(sample_id, sample_id)
        if patient_id not in patient_biomarkers:
            patient_biomarkers[patient_id] = {}
        for attr, val in attrs.items():
            if attr not in patient_biomarkers[patient_id]:
                patient_biomarkers[patient_id][attr] = val

    # Calculate coverage
    total_patients = len(set(sample_to_patient.values()))
    coverage = {}
    for attr in BIOMARKER_ATTRS:
        count = sum(1 for p in patient_biomarkers.values() if attr in p)
        pct = 100 * count / total_patients if total_patients > 0 else 0
        coverage[attr] = {"n": count, "pct": round(pct, 1)}

    # Save output
    output = {
        "study_id": STUDY_ID,
        "extraction_date": datetime.now().isoformat(),
        "n_patients": total_patients,
        "coverage": coverage,
        "patients": patient_biomarkers
    }

    output_path = OUTPUT_DIR / "tcga_ov_biomarkers_raw.json"
    output_path.write_text(json.dumps(output, indent=2))
    print(f"\n✅ Saved biomarker data to: {output_path}")
    
    return output


def extract_brca_mutations():
    """Extract BRCA1/BRCA2 mutation status from cBioPortal."""
    print()
    print("=" * 60)
    print("EXTRACTING BRCA1/BRCA2 MUTATIONS")
    print("=" * 60)
    print()

    mutations_url = f"https://www.cbioportal.org/api/molecular-profiles/{MUTATION_PROFILE}/mutations/fetch"
    body = {
        "sampleListId": f"{STUDY_ID}_all",
        "entrezGeneIds": [BRCA1_ENTREZ, BRCA2_ENTREZ]
    }

    print("Fetching BRCA mutations...")
    resp = requests.post(mutations_url, json=body, timeout=120)
    print(f"Status: {resp.status_code}")

    if resp.status_code == 200:
        mutations = resp.json()
        print(f"Found {len(mutations)} BRCA mutations")
        
        # Group by gene and patient
        brca_patients = {BRCA1_ENTREZ: set(), BRCA2_ENTREZ: set()}
        for m in mutations:
            entrez_id = m.get("entrezGeneId")
            patient_id = m.get("patientId")
            if entrez_id in brca_patients and patient_id:
                brca_patients[entrez_id].add(patient_id)
        
        all_brca = brca_patients[BRCA1_ENTREZ] | brca_patients[BRCA2_ENTREZ]
        
        print()
        print("BRCA MUTATION SUMMARY:")
        print(f"  BRCA1 mutated: {len(brca_patients[BRCA1_ENTREZ])} patients")
        print(f"  BRCA2 mutated: {len(brca_patients[BRCA2_ENTREZ])} patients")
        print(f"  Any BRCA mutated: {len(all_brca)} patients")
        
        # Save output
        output = {
            "study_id": STUDY_ID,
            "extraction_date": datetime.now().isoformat(),
            "brca1_patients": list(brca_patients[BRCA1_ENTREZ]),
            "brca2_patients": list(brca_patients[BRCA2_ENTREZ]),
            "any_brca_patients": list(all_brca),
            "n_brca1": len(brca_patients[BRCA1_ENTREZ]),
            "n_brca2": len(brca_patients[BRCA2_ENTREZ]),
            "n_any_brca": len(all_brca)
        }
        
        output_path = OUTPUT_DIR / "tcga_ov_brca_mutations.json"
        output_path.write_text(json.dumps(output, indent=2))
        print(f"\n✅ Saved BRCA data to: {output_path}")
        
        return output
    else:
        print(f"Error: {resp.text[:500]}")
        return None


def main():
    print("=" * 70)
    print("TCGA-OV BIOMARKER EXTRACTION")
    print("=" * 70)
    print(f"Study: {STUDY_ID}")
    print(f"Output: {OUTPUT_DIR}")
    print()
    
    # Extract biomarkers
    biomarkers = extract_clinical_biomarkers()
    
    # Extract BRCA mutations
    brca = extract_brca_mutations()
    
    print()
    print("=" * 70)
    print("EXTRACTION COMPLETE")
    print("=" * 70)
    print()
    print("COVERAGE REPORT:")
    for attr, info in biomarkers["coverage"].items():
        print(f"  {attr}: {info['n']}/{biomarkers['n_patients']} ({info['pct']}%)")
    if brca:
        print(f"  BRCA_SOMATIC: {brca['n_any_brca']}/{biomarkers['n_patients']} ({round(100*brca['n_any_brca']/biomarkers['n_patients'], 1)}%)")


if __name__ == "__main__":
    main()
