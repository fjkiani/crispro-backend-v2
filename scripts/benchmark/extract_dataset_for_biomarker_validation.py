#!/usr/bin/env python3
"""
Extract cBioPortal Dataset for Enhanced Biomarker Validation

This script extracts patient data from cBioPortal using pybioportal
and saves it in the format expected by validate_enhanced_biomarkers.py

Usage:
    python scripts/benchmark/extract_dataset_for_biomarker_validation.py [--study STUDY_ID] [--output OUTPUT_FILE]
"""

import sys
import argparse
from pathlib import Path
import json

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
    print(f"⚠️  Warning: pyBioPortal not available: {e}")
    print(f"   Make sure pyBioPortal is available at: {PYBIOPORTAL_PATH}")
    PYBIOPORTAL_AVAILABLE = False

# Use the existing extraction script if available
EXTRACT_SCRIPT = PROJECT_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "scripts" / "benchmark" / "extract_cbioportal_trial_datasets.py"


def extract_dataset_simple(study_id: str = "ov_tcga_pan_can_atlas_2018", output_file: Path = None):
    """
    Simple dataset extraction using existing extract_cbioportal_trial_datasets.py
    
    This is a wrapper that calls the existing extraction script.
    """
    if not EXTRACT_SCRIPT.exists():
        print(f"❌ Extraction script not found: {EXTRACT_SCRIPT}")
        print(f"   Please run the full extraction script manually:")
        print(f"   python {EXTRACT_SCRIPT} --study {study_id}")
        return False
    
    print(f"📡 Using existing extraction script: {EXTRACT_SCRIPT}")
    print(f"   Study: {study_id}")
    
    # Import and run the extraction
    import subprocess
    import sys
    
    cmd = [
        sys.executable,
        str(EXTRACT_SCRIPT),
        "--study", study_id
    ]
    
    print(f"   Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Extraction failed:")
        print(result.stderr)
        return False
    
    print(result.stdout)
    
    # Check if output file was created
    OUTPUT_DIR = PROJECT_ROOT / "data" / "benchmarks"
    latest_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    
    if latest_file.exists():
        print(f"✅ Dataset extracted successfully: {latest_file}")
        if output_file and output_file != latest_file:
            # Copy to requested location
            import shutil
            shutil.copy(latest_file, output_file)
            print(f"✅ Copied to: {output_file}")
        return True
    else:
        print(f"⚠️  Expected output file not found: {latest_file}")
        return False


def check_existing_dataset():
    """Check if dataset already exists."""
    OUTPUT_DIR = PROJECT_ROOT / "data" / "benchmarks"
    latest_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    
    if latest_file.exists():
        print(f"✅ Found existing dataset: {latest_file}")
        
        # Check dataset size
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        # Count patients
        if isinstance(data, list):
            total_patients = sum(len(study.get("patients", [])) for study in data)
        elif isinstance(data, dict):
            total_patients = sum(len(study.get("patients", [])) for study in data.values())
        else:
            total_patients = len(data) if isinstance(data, list) else 0
        
        print(f"   Total patients: {total_patients}")
        return latest_file
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Extract cBioPortal dataset for biomarker validation"
    )
    parser.add_argument(
        "--study",
        type=str,
        default="ov_tcga_pan_can_atlas_2018",
        help="cBioPortal study ID (default: ov_tcga_pan_can_atlas_2018)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: data/benchmarks/cbioportal_trial_datasets_latest.json)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-extraction even if dataset exists"
    )
    
    args = parser.parse_args()
    
    # Check for existing dataset
    if not args.force:
        existing = check_existing_dataset()
        if existing:
            print(f"\n✅ Using existing dataset: {existing}")
            print(f"   To re-extract, use --force flag")
            return
    
    # Check if pyBioPortal is available
    if not PYBIOPORTAL_AVAILABLE:
        print("\n❌ pyBioPortal not available. Cannot extract dataset.")
        print("\nTo fix this:")
        print(f"1. Ensure pyBioPortal is available at: {PYBIOPORTAL_PATH}")
        print(f"2. Or run the extraction script manually:")
        print(f"   python {EXTRACT_SCRIPT} --study {args.study}")
        return
    
    # Set output file
    if args.output:
        output_file = Path(args.output)
    else:
        OUTPUT_DIR = PROJECT_ROOT / "data" / "benchmarks"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    
    print(f"\n📡 Extracting dataset from cBioPortal...")
    print(f"   Study: {args.study}")
    print(f"   Output: {output_file}")
    
    # Extract using existing script
    success = extract_dataset_simple(args.study, output_file)
    
    if success:
        print(f"\n✅ Dataset ready for validation!")
        print(f"   Run validation with:")
        print(f"   python scripts/benchmark/validate_enhanced_biomarkers.py --dataset {output_file}")
    else:
        print(f"\n❌ Dataset extraction failed. Please check errors above.")


if __name__ == "__main__":
    main()

