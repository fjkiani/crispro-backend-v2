#!/usr/bin/env python3
"""
Add BRCA TCGA Study to Existing Dataset

Extracts brca_tcga_pan_can_atlas_2018 and combines with existing dataset
to improve HRD biomarker coverage.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Add pyBioPortal to path
PYBIOPORTAL_PATH = PROJECT_ROOT / "oncology-coPilot" / "oncology-backend" / "tests" / "pyBioPortal-master"
if PYBIOPORTAL_PATH.exists() and str(PYBIOPORTAL_PATH) not in sys.path:
    sys.path.insert(0, str(PYBIOPORTAL_PATH))

try:
    from pybioportal import studies as st
    from pybioportal import molecular_profiles as mp
    from pybioportal import sample_lists as sl
    from pybioportal import mutations as mut
    from pybioportal import clinical_data as cd
    PYBIOPORTAL_AVAILABLE = True
except ImportError as e:
    print(f"❌ Error importing pyBioPortal: {e}")
    PYBIOPORTAL_AVAILABLE = False
    sys.exit(1)

# Import extraction functions from existing script
sys.path.insert(0, str(Path(__file__).parent))
from extract_cbioportal_trial_datasets import (
    find_mutation_profile,
    find_sample_list,
    extract_mutations,
    extract_clinical_outcomes,
    extract_treatments,
    combine_patient_data,
    validate_dataset,
    extract_study_dataset
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "benchmarks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_existing_dataset() -> List[Dict[str, Any]]:
    """Load existing dataset."""
    latest_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    if not latest_file.exists():
        return []
    
    with open(latest_file, 'r') as f:
        data = json.load(f)
    
    return data if isinstance(data, list) else []


def main():
    """Extract BRCA study and combine with existing dataset."""
    print("=" * 80)
    print("ADDING BRCA STUDY TO DATASET FOR ENHANCED HRD COVERAGE")
    print("=" * 80)
    
    # Load existing
    print("\n📂 Loading existing dataset...")
    existing = load_existing_dataset()
    existing_study_ids = {s.get("study_id") for s in existing if isinstance(s, dict)}
    existing_patients = sum(len(s.get("patients", [])) for s in existing if isinstance(s, dict))
    print(f"   Found {len(existing)} studies: {', '.join(existing_study_ids)}")
    print(f"   Total patients: {existing_patients}")
    
    # Check if BRCA already exists
    if "brca_tcga_pan_can_atlas_2018" in existing_study_ids:
        print("\n✅ BRCA study already in dataset. Exiting.")
        return
    
    # Extract BRCA study
    print("\n📡 Extracting BRCA study...")
    brca_study = extract_study_dataset("brca_tcga_pan_can_atlas_2018")
    
    if not brca_study:
        print("❌ Failed to extract BRCA study")
        return
    
    print(f"   ✅ Extracted {len(brca_study.get('patients', []))} patients from BRCA study")
    
    # Combine datasets
    print("\n🔗 Combining datasets...")
    combined = existing + [brca_study]
    
    # Save combined dataset
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_file = OUTPUT_DIR / f"cbioportal_trial_datasets_{timestamp}.json"
    latest_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    
    print(f"\n💾 Saving combined dataset...")
    with open(timestamped_file, 'w') as f:
        json.dump(combined, f, indent=2, default=str)
    
    with open(latest_file, 'w') as f:
        json.dump(combined, f, indent=2, default=str)
    
    total_patients = sum(len(s.get("patients", [])) for s in combined if isinstance(s, dict))
    print(f"   ✅ Saved:")
    print(f"      Timestamped: {timestamped_file}")
    print(f"      Latest: {latest_file}")
    print(f"      Total studies: {len(combined)}")
    print(f"      Total patients: {total_patients}")
    
    print("\n✅ Complete! Run validation to check HRD coverage improvement:")
    print(f"   python scripts/benchmark/validate_enhanced_biomarkers.py")


if __name__ == "__main__":
    main()

