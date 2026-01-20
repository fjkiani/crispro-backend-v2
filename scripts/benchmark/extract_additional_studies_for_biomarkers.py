#!/usr/bin/env python3
"""
Extract Additional Studies for Enhanced Biomarker Coverage

Adds more TCGA studies to improve HRD coverage from 8.9% → 15-20%
Focuses on studies with HRR pathway mutations (BRCA, ovarian, breast, etc.)
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Add pyBioPortal to path
PYBIOPORTAL_PATH = PROJECT_ROOT / "oncology-coPilot" / "oncology-backend" / "tests" / "pyBioPortal-master"
if PYBIOPORTAL_PATH.exists() and str(PYBIOPORTAL_PATH) not in sys.path:
    sys.path.insert(0, str(PYBIOPORTAL_PATH))

# Import existing extraction script functions
EXTRACT_SCRIPT = PROJECT_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "scripts" / "benchmark" / "extract_cbioportal_trial_datasets.py"

# Additional studies with HRR pathway mutations
ADDITIONAL_STUDIES = [
    "brca_tcga_pan_can_atlas_2018",  # Breast cancer - high BRCA mutation rate
    # Add more if needed
]

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


def extract_study(study_id: str) -> Dict[str, Any]:
    """Extract a single study using the existing extraction script."""
    print(f"\n📡 Extracting study: {study_id}")
    
    # Import the extraction functions
    import subprocess
    import tempfile
    
    # Run the extraction script for this study
    cmd = [
        sys.executable,
        str(EXTRACT_SCRIPT),
        "--study", study_id,
        "--output", str(OUTPUT_DIR / f"temp_{study_id}.json")
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    
    if result.returncode != 0:
        print(f"   ⚠️  Extraction failed: {result.stderr[:200]}")
        return None
    
    # Load the extracted data
    temp_file = OUTPUT_DIR / f"temp_{study_id}.json"
    if temp_file.exists():
        with open(temp_file, 'r') as f:
            data = json.load(f)
        
        # Clean up temp file
        temp_file.unlink()
        
        # Return first study if it's a list
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        elif isinstance(data, dict):
            return data
        
    return None


def combine_datasets(existing: List[Dict], new_studies: List[Dict]) -> List[Dict]:
    """Combine existing and new study datasets."""
    combined = existing.copy()
    
    # Add new studies (avoid duplicates)
    existing_study_ids = {s.get("study_id") for s in existing if isinstance(s, dict)}
    
    for new_study in new_studies:
        if new_study and new_study.get("study_id") not in existing_study_ids:
            combined.append(new_study)
            print(f"   ✅ Added study: {new_study.get('study_id')} ({len(new_study.get('patients', []))} patients)")
        elif new_study:
            print(f"   ⚠️  Study {new_study.get('study_id')} already exists, skipping")
    
    return combined


def save_combined_dataset(dataset: List[Dict]):
    """Save combined dataset with timestamp."""
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save timestamped version
    timestamped_file = OUTPUT_DIR / f"cbioportal_trial_datasets_{timestamp}.json"
    with open(timestamped_file, 'w') as f:
        json.dump(dataset, f, indent=2, default=str)
    
    # Update latest
    latest_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    with open(latest_file, 'w') as f:
        json.dump(dataset, f, indent=2, default=str)
    
    print(f"\n✅ Saved combined dataset:")
    print(f"   Timestamped: {timestamped_file}")
    print(f"   Latest: {latest_file}")
    
    # Calculate totals
    total_patients = sum(len(s.get("patients", [])) for s in dataset if isinstance(s, dict))
    print(f"   Total studies: {len(dataset)}")
    print(f"   Total patients: {total_patients}")


def main():
    """Main extraction function."""
    print("=" * 80)
    print("EXTRACTING ADDITIONAL STUDIES FOR ENHANCED BIOMARKER COVERAGE")
    print("=" * 80)
    
    # Load existing dataset
    print("\n📂 Loading existing dataset...")
    existing = load_existing_dataset()
    existing_patients = sum(len(s.get("patients", [])) for s in existing if isinstance(s, dict))
    print(f"   Found {len(existing)} studies with {existing_patients} patients")
    
    # Extract additional studies
    print(f"\n📡 Extracting {len(ADDITIONAL_STUDIES)} additional studies...")
    new_studies = []
    
    for study_id in ADDITIONAL_STUDIES:
        study_data = extract_study(study_id)
        if study_data:
            new_studies.append(study_data)
        else:
            print(f"   ⚠️  Failed to extract {study_id}")
    
    if not new_studies:
        print("\n⚠️  No new studies extracted. Exiting.")
        return
    
    # Combine datasets
    print("\n🔗 Combining datasets...")
    combined = combine_datasets(existing, new_studies)
    
    # Save combined dataset
    save_combined_dataset(combined)
    
    print("\n✅ Extraction complete!")
    print(f"\nNext steps:")
    print(f"1. Run validation: python scripts/benchmark/validate_enhanced_biomarkers.py")
    print(f"2. Check HRD coverage improvement (target: 15-20%)")


if __name__ == "__main__":
    main()

