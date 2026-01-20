#!/usr/bin/env python3
"""
cBioPortal Clinical Trial Dataset Extraction Script

Extracts patient-level data from cBioPortal for clinical trial outcome benchmarking:
- Mutations (gene, protein change, chromosome, position)
- Clinical Outcomes (PFS, OS, response rates)
- Treatments (drugs, treatment lines, response)

Target Studies:
- ov_tcga_pan_can_atlas_2018 (TCGA Ovarian Cancer PanCan Atlas)
- ov_tcga (TCGA Ovarian Cancer - Original)

Output: Unified dataset with mutations + outcomes + treatments per patient
"""

import sys
from pathlib import Path
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd

# Add pyBioPortal to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
PYBIOPORTAL_PATH = PROJECT_ROOT / "oncology-coPilot" / "oncology-backend" / "tests" / "pyBioPortal-master"
if PYBIOPORTAL_PATH.exists() and str(PYBIOPORTAL_PATH) not in sys.path:
    sys.path.insert(0, str(PYBIOPORTAL_PATH))

try:
    from pybioportal import studies as st
    from pybioportal import molecular_profiles as mp
    from pybioportal import sample_lists as sl
    from pybioportal import mutations as mut
    from pybioportal import clinical_data as cd
    from pybioportal import treatments as trt
except ImportError as e:
    print(f"❌ Error importing pyBioPortal: {e}")
    print(f"   Make sure pyBioPortal is available at: {PYBIOPORTAL_PATH}")
    sys.exit(1)

# Configuration
TARGET_STUDIES = [
    "ov_tcga_pan_can_atlas_2018",
    "ov_tcga"
]

OUTPUT_DIR = PROJECT_ROOT / "data" / "benchmarks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiting (seconds between API calls)
API_DELAY = 1.0

# Data completeness thresholds
MIN_MUTATIONS_PER_PATIENT = 0  # Allow patients with no mutations (will be filtered later)
REQUIRE_OUTCOMES = False  # Don't require outcomes (will report completeness)
REQUIRE_TREATMENTS = False  # Don't require treatments (will report completeness)


def extract_tcga_patient_id(sample_id: str) -> Optional[str]:
    """Extract TCGA patient ID from sample ID (e.g., TCGA-XX-XXXX-01 -> TCGA-XX-XXXX)."""
    if not sample_id:
        return None
    parts = sample_id.split("-")
    if len(parts) >= 3:
        return "-".join(parts[:3])
    return sample_id


def find_mutation_profile(study_id: str) -> Optional[str]:
    """Find the mutations molecular profile ID for a study."""
    print(f"   📡 Finding mutation profile for {study_id}...")
    time.sleep(API_DELAY)
    
    try:
        profiles = mp.get_all_molecular_profiles_in_study(study_id)
        if profiles.empty:
            print(f"   ⚠️  No molecular profiles found for {study_id}")
            return None
        
        # Look for mutations profile (ends with _mutations)
        for _, row in profiles.iterrows():
            profile_id = str(row.get("molecularProfileId", ""))
            if profile_id.endswith("_mutations"):
                print(f"   ✅ Found mutation profile: {profile_id}")
                return profile_id
        
        print(f"   ⚠️  No mutations profile found for {study_id}")
        return None
    except Exception as e:
        print(f"   ❌ Error finding mutation profile: {e}")
        return None


def find_sample_list(study_id: str, prefer_all: bool = True) -> Optional[str]:
    """Find a sample list ID for a study (prefer '_all' if available)."""
    print(f"   📡 Finding sample list for {study_id}...")
    time.sleep(API_DELAY)
    
    try:
        sample_lists = sl.get_all_sample_lists_in_study(study_id)
        if sample_lists.empty:
            print(f"   ⚠️  No sample lists found for {study_id}")
            return None
        
        # Prefer '_all' sample list
        if prefer_all:
            for _, row in sample_lists.iterrows():
                list_id = str(row.get("sampleListId", ""))
                if list_id.endswith("_all"):
                    print(f"   ✅ Found '_all' sample list: {list_id}")
                    return list_id
        
        # Fallback to first available
        first_list_id = str(sample_lists.iloc[0].get("sampleListId", ""))
        print(f"   ✅ Using sample list: {first_list_id}")
        return first_list_id
    except Exception as e:
        print(f"   ❌ Error finding sample list: {e}")
        return None


def extract_mutations(study_id: str, mutation_profile_id: str, sample_list_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """Extract mutations for all patients in a study."""
    print(f"   📡 Extracting mutations from {mutation_profile_id}...")
    time.sleep(API_DELAY)
    
    mutations_by_patient: Dict[str, List[Dict[str, Any]]] = {}
    
    try:
        # Fetch mutations using sample list
        df_muts = mut.get_muts_in_mol_prof_by_sample_list_id(
            molecular_profile_id=mutation_profile_id,
            sample_list_id=sample_list_id,
            projection="DETAILED",
            pageSize=100000  # Large page size to get all mutations
        )
        
        if df_muts.empty:
            print(f"   ⚠️  No mutations found for {study_id}")
            return mutations_by_patient
        
        print(f"   ✅ Retrieved {len(df_muts)} mutation rows")
        
        # Find gene column (could be hugoSymbol, gene, etc.)
        gene_cols = [c for c in df_muts.columns if "hugo" in c.lower() or c.lower() == "gene"]
        if not gene_cols:
            print(f"   ⚠️  Could not find gene column in mutations DataFrame")
            print(f"      Available columns: {list(df_muts.columns)}")
            return mutations_by_patient
        gene_col = gene_cols[0]
        
        # Process mutations
        for _, row in df_muts.iterrows():
            # Extract patient ID from sample ID
            sample_id = str(row.get("sampleId") or row.get("sample_id") or "")
            if not sample_id:
                continue
            
            patient_id = extract_tcga_patient_id(sample_id) or sample_id
            
            # Extract mutation data
            chrom = row.get("chromosome") or row.get("chr") or row.get("chrom")
            pos = row.get("startPosition") or row.get("start_position") or row.get("position")
            ref = row.get("referenceAllele") or row.get("ref") or row.get("referenceAllele")
            alt = row.get("variantAllele") or row.get("alt") or row.get("tumorSeqAllele2")
            protein_change = row.get("proteinChange") or row.get("hgvsp") or row.get("aminoAcidChange")
            gene = row.get(gene_col)
            
            if not gene:
                continue
            
            mutation = {
                "gene": str(gene),
                "chromosome": str(chrom) if chrom else None,
                "position": int(pos) if pos else None,
                "ref": str(ref).upper() if ref else None,
                "alt": str(alt).upper() if alt else None,
                "protein_change": str(protein_change) if protein_change else None,
                "mutation_type": str(row.get("mutationType", "")),
                "variant_type": str(row.get("variantType", "")),
            }
            
            if patient_id not in mutations_by_patient:
                mutations_by_patient[patient_id] = []
            mutations_by_patient[patient_id].append(mutation)
        
        print(f"   ✅ Extracted mutations for {len(mutations_by_patient)} patients")
        return mutations_by_patient
        
    except Exception as e:
        print(f"   ❌ Error extracting mutations: {e}")
        import traceback
        traceback.print_exc()
        return mutations_by_patient


def extract_clinical_outcomes(study_id: str) -> pd.DataFrame:
    """Extract clinical outcomes (PFS, OS, response rates) for all patients."""
    print(f"   📡 Extracting clinical outcomes for {study_id}...")
    time.sleep(API_DELAY)
    
    try:
        # Get all patient-level clinical data
        clinical_df = cd.get_all_clinical_data_in_study(
            study_id=study_id,
            clinical_data_type="PATIENT",
            pageSize=100000
        )
        
        if clinical_df.empty:
            print(f"   ⚠️  No clinical data found for {study_id}")
            return pd.DataFrame()
        
        print(f"   ✅ Retrieved {len(clinical_df)} clinical data rows")
        
        # Pivot to wide format (one row per patient)
        if "patientId" in clinical_df.columns and "clinicalAttributeId" in clinical_df.columns:
            clinical_wide = clinical_df.pivot(
                index="patientId",
                columns="clinicalAttributeId",
                values="value"
            )
            clinical_wide.reset_index(inplace=True)
            
            # Convert numeric fields
            numeric_fields = ['OS_MONTHS', 'PFS_MONTHS', 'DFS_MONTHS', 'DSS_MONTHS', 'AGE', 
                            'TMB_NONSYNONYMOUS', 'MUTATION_COUNT', 'FRACTION_GENOME_ALTERED']
            for field in numeric_fields:
                if field in clinical_wide.columns:
                    clinical_wide[field] = pd.to_numeric(clinical_wide[field], errors='coerce')
            
            print(f"   ✅ Pivoted to wide format: {len(clinical_wide)} patients")
            
            # Report key outcome fields
            key_fields = ['OS_MONTHS', 'OS_STATUS', 'PFS_MONTHS', 'PFS_STATUS', 'DFS_MONTHS', 'DFS_STATUS']
            available_fields = [f for f in key_fields if f in clinical_wide.columns]
            print(f"   ✅ Key outcome fields available: {available_fields}")
            
            return clinical_wide
        else:
            print(f"   ⚠️  Clinical data format unexpected. Columns: {list(clinical_df.columns)}")
            return clinical_df
            
    except Exception as e:
        print(f"   ❌ Error extracting clinical outcomes: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def extract_treatments(study_id: str) -> pd.DataFrame:
    """Extract patient-level treatment data."""
    print(f"   📡 Extracting treatments for {study_id}...")
    time.sleep(API_DELAY)
    
    try:
        # Check if patient-level treatments are available
        has_treatments = trt.fetch_status_display_patient_trts([study_id], tier="Agent")
        if not has_treatments:
            print(f"   ⚠️  Patient-level treatments not available for {study_id}")
            return pd.DataFrame()
        
        # Fetch patient-level treatments
        treatments_df = trt.fetch_all_patient_level_treatments(
            study_view_filter={"studyIds": [study_id]},
            tier="Agent"
        )
        
        if treatments_df.empty:
            print(f"   ⚠️  No treatment data found for {study_id}")
            return pd.DataFrame()
        
        print(f"   ✅ Retrieved {len(treatments_df)} treatment records")
        return treatments_df
        
    except Exception as e:
        print(f"   ❌ Error extracting treatments: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def combine_patient_data(
    study_id: str,
    mutations: Dict[str, List[Dict[str, Any]]],
    clinical_outcomes: pd.DataFrame,
    treatments: pd.DataFrame
) -> List[Dict[str, Any]]:
    """Combine mutations, clinical outcomes, and treatments into unified patient records."""
    print(f"   📊 Combining data for {study_id}...")
    
    # Get all unique patient IDs
    patient_ids = set()
    patient_ids.update(mutations.keys())
    if not clinical_outcomes.empty and "patientId" in clinical_outcomes.columns:
        patient_ids.update(clinical_outcomes["patientId"].astype(str).tolist())
    if not treatments.empty and "patientId" in treatments.columns:
        patient_ids.update(treatments["patientId"].astype(str).tolist())
    
    print(f"   📊 Found {len(patient_ids)} unique patients")
    
    combined_data = []
    
    for patient_id in patient_ids:
        patient_record = {
            "patient_id": patient_id,
            "study_id": study_id,
            "mutations": mutations.get(patient_id, []),
            "clinical_outcomes": {},
            "treatments": []
        }
        
        # Add clinical outcomes
        if not clinical_outcomes.empty and "patientId" in clinical_outcomes.columns:
            patient_clinical = clinical_outcomes[clinical_outcomes["patientId"] == patient_id]
            if not patient_clinical.empty:
                # Convert to dict (exclude patientId)
                patient_record["clinical_outcomes"] = patient_clinical.iloc[0].drop("patientId").to_dict()
        
        # Add treatments
        if not treatments.empty and "patientId" in treatments.columns:
            patient_treatments = treatments[treatments["patientId"] == patient_id]
            if not patient_treatments.empty:
                patient_record["treatments"] = patient_treatments.to_dict("records")
        
        combined_data.append(patient_record)
    
    print(f"   ✅ Combined data for {len(combined_data)} patients")
    return combined_data


def validate_dataset(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate dataset completeness and quality."""
    print(f"\n📊 Validating dataset...")
    
    total_patients = len(dataset)
    patients_with_mutations = sum(1 for p in dataset if p.get("mutations"))
    patients_with_outcomes = sum(1 for p in dataset if p.get("clinical_outcomes"))
    patients_with_treatments = sum(1 for p in dataset if p.get("treatments"))
    patients_complete = sum(
        1 for p in dataset
        if p.get("mutations") and p.get("clinical_outcomes") and p.get("treatments")
    )
    
    # Check for key outcome fields
    patients_with_pfs = 0
    patients_with_os = 0
    patients_with_pfs_and_os = 0
    
    for p in dataset:
        outcomes = p.get("clinical_outcomes", {})
        if isinstance(outcomes, dict):
            has_pfs = "PFS_MONTHS" in outcomes and outcomes.get("PFS_MONTHS") is not None
            has_os = "OS_MONTHS" in outcomes and outcomes.get("OS_MONTHS") is not None
            if has_pfs:
                patients_with_pfs += 1
            if has_os:
                patients_with_os += 1
            if has_pfs and has_os:
                patients_with_pfs_and_os += 1
    
    # Check data quality
    quality_issues = []
    
    # Check for duplicate patient IDs
    patient_ids = [p.get("patient_id") for p in dataset]
    if len(patient_ids) != len(set(patient_ids)):
        quality_issues.append("Duplicate patient IDs found")
    
    # Check for valid PFS/OS values
    invalid_pfs = 0
    invalid_os = 0
    for p in dataset:
        outcomes = p.get("clinical_outcomes", {})
        if isinstance(outcomes, dict):
            pfs_months = outcomes.get("PFS_MONTHS")
            os_months = outcomes.get("OS_MONTHS")
            if pfs_months is not None and (not isinstance(pfs_months, (int, float)) or pfs_months < 0):
                invalid_pfs += 1
            if os_months is not None and (not isinstance(os_months, (int, float)) or os_months < 0):
                invalid_os += 1
    
    if invalid_pfs > 0:
        quality_issues.append(f"{invalid_pfs} patients with invalid PFS_MONTHS")
    if invalid_os > 0:
        quality_issues.append(f"{invalid_os} patients with invalid OS_MONTHS")
    
    validation_report = {
        "total_patients": total_patients,
        "patients_with_mutations": patients_with_mutations,
        "patients_with_outcomes": patients_with_outcomes,
        "patients_with_treatments": patients_with_treatments,
        "patients_complete": patients_complete,
        "patients_with_pfs": patients_with_pfs,
        "patients_with_os": patients_with_os,
        "patients_with_pfs_and_os": patients_with_pfs_and_os,
        "mutation_coverage": patients_with_mutations / total_patients if total_patients > 0 else 0,
        "outcome_coverage": patients_with_outcomes / total_patients if total_patients > 0 else 0,
        "treatment_coverage": patients_with_treatments / total_patients if total_patients > 0 else 0,
        "complete_coverage": patients_complete / total_patients if total_patients > 0 else 0,
        "pfs_coverage": patients_with_pfs / total_patients if total_patients > 0 else 0,
        "os_coverage": patients_with_os / total_patients if total_patients > 0 else 0,
        "pfs_and_os_coverage": patients_with_pfs_and_os / total_patients if total_patients > 0 else 0,
        "quality_issues": quality_issues,
        "benchmarking_ready": (
            patients_with_pfs_and_os >= 200 and
            len(quality_issues) == 0
        ),
        "benchmarking_ready_pfs_os": (
            patients_with_pfs_and_os >= 200 and
            len(quality_issues) == 0
        ),
        "patients_with_mutations_and_pfs_os": sum(
            1 for p in dataset
            if len(p.get("mutations", [])) > 0 and
            isinstance(p.get("clinical_outcomes"), dict) and
            p.get("clinical_outcomes", {}).get("PFS_MONTHS") is not None and
            p.get("clinical_outcomes", {}).get("OS_MONTHS") is not None
        )
    }
    
    print(f"   Total patients: {total_patients}")
    print(f"   With mutations: {patients_with_mutations} ({validation_report['mutation_coverage']*100:.1f}%)")
    print(f"   With outcomes: {patients_with_outcomes} ({validation_report['outcome_coverage']*100:.1f}%)")
    print(f"   With treatments: {patients_with_treatments} ({validation_report['treatment_coverage']*100:.1f}%)")
    print(f"   With PFS: {patients_with_pfs} ({validation_report['pfs_coverage']*100:.1f}%)")
    print(f"   With OS: {patients_with_os} ({validation_report['os_coverage']*100:.1f}%)")
    print(f"   With PFS + OS: {patients_with_pfs_and_os} ({validation_report['pfs_and_os_coverage']*100:.1f}%)")
    print(f"   Complete (all three): {patients_complete} ({validation_report['complete_coverage']*100:.1f}%)")
    
    if quality_issues:
        print(f"\n   ⚠️  Quality Issues:")
        for issue in quality_issues:
            print(f"      - {issue}")
    else:
        print(f"\n   ✅ No quality issues detected")
    
    # Check PFS/OS benchmarking readiness (mutations + PFS + OS)
    patients_mutations_pfs_os = validation_report.get("patients_with_mutations_and_pfs_os", 0)
    
    if validation_report["benchmarking_ready_pfs_os"]:
        print(f"\n   ✅ Dataset is READY for PFS/OS benchmarking")
        print(f"      Patients with mutations + PFS + OS: {patients_mutations_pfs_os}")
    elif patients_mutations_pfs_os >= 200:
        print(f"\n   ✅ Dataset is READY for PFS/OS benchmarking")
        print(f"      Patients with mutations + PFS + OS: {patients_mutations_pfs_os}")
    else:
        print(f"\n   ⚠️  Dataset may not be ready for benchmarking")
        print(f"      Patients with mutations + PFS + OS: {patients_mutations_pfs_os} (need ≥200)")
    
    return validation_report


def extract_study_dataset(study_id: str) -> Optional[Dict[str, Any]]:
    """Extract complete dataset for a single study."""
    print(f"\n{'='*80}")
    print(f"EXTRACTING DATASET: {study_id}")
    print(f"{'='*80}")
    
    # Step 1: Find mutation profile
    mutation_profile_id = find_mutation_profile(study_id)
    if not mutation_profile_id:
        print(f"   ⚠️  Skipping {study_id} - no mutation profile found")
        return None
    
    # Step 2: Find sample list
    sample_list_id = find_sample_list(study_id)
    if not sample_list_id:
        print(f"   ⚠️  Skipping {study_id} - no sample list found")
        return None
    
    # Step 3: Extract mutations
    mutations = extract_mutations(study_id, mutation_profile_id, sample_list_id)
    
    # Step 4: Extract clinical outcomes
    clinical_outcomes = extract_clinical_outcomes(study_id)
    
    # Step 5: Extract treatments
    treatments = extract_treatments(study_id)
    
    # Step 6: Combine data
    combined_data = combine_patient_data(study_id, mutations, clinical_outcomes, treatments)
    
    # Step 7: Validate
    validation_report = validate_dataset(combined_data)
    
    # Step 8: Create output structure
    dataset = {
        "study_id": study_id,
        "extraction_date": datetime.now().isoformat(),
        "mutation_profile_id": mutation_profile_id,
        "sample_list_id": sample_list_id,
        "patients": combined_data,
        "validation": validation_report,
        "summary": {
            "total_patients": len(combined_data),
            "patients_with_mutations": validation_report["patients_with_mutations"],
            "patients_with_outcomes": validation_report["patients_with_outcomes"],
            "patients_with_treatments": validation_report["patients_with_treatments"],
            "patients_complete": validation_report["patients_complete"],
        }
    }
    
    return dataset


def main():
    """Main extraction function."""
    print("="*80)
    print("cBioPortal Clinical Trial Dataset Extraction")
    print("="*80)
    print(f"Target Studies: {', '.join(TARGET_STUDIES)}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"API Delay: {API_DELAY}s between calls")
    print("="*80)
    
    all_datasets = []
    
    for study_id in TARGET_STUDIES:
        dataset = extract_study_dataset(study_id)
        if dataset:
            all_datasets.append(dataset)
    
    if not all_datasets:
        print("\n❌ No datasets extracted successfully")
        return
    
    # Save combined dataset
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"cbioportal_trial_datasets_{timestamp}.json"
    
    print(f"\n💾 Saving dataset to {output_file}...")
    with open(output_file, "w") as f:
        json.dump(all_datasets, f, indent=2, default=str)
    
    print(f"✅ Dataset saved successfully!")
    print(f"\n📊 Summary:")
    total_patients = sum(d["summary"]["total_patients"] for d in all_datasets)
    print(f"   Total studies: {len(all_datasets)}")
    print(f"   Total patients: {total_patients}")
    
    # Also save latest version
    latest_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    with open(latest_file, "w") as f:
        json.dump(all_datasets, f, indent=2, default=str)
    print(f"   Also saved as: {latest_file}")


if __name__ == "__main__":
    main()

