"""
Data Loader Module

Unified cBioPortal dataset loading with consistent filtering logic.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional


def load_cbioportal_dataset(
    dataset_file: Optional[str] = None,
    output_dir: Optional[Path] = None,
    require_mutations: bool = True,
    require_pfs: bool = True,
    require_os: bool = True,
) -> List[Dict[str, Any]]:
    """
    Load cBioPortal dataset with consistent filtering.
    
    Args:
        dataset_file: Path to dataset file (default: cbioportal_trial_datasets_latest.json)
        output_dir: Directory containing dataset (default: data/benchmarks)
        require_mutations: Filter out patients with no mutations
        require_pfs: Filter out patients without PFS_MONTHS
        require_os: Filter out patients without OS_MONTHS
    
    Returns:
        List of eligible patients with mutations, PFS, and OS data
    """
    if output_dir is None:
        # Find project root
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent.parent.parent
        output_dir = project_root / "data" / "benchmarks"
    
    if dataset_file is None:
        dataset_file = output_dir / "cbioportal_trial_datasets_latest.json"
    else:
        dataset_file = Path(dataset_file)
    
    if not dataset_file.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_file}")
    
    with open(dataset_file, 'r') as f:
        data = json.load(f)
    
    # Handle both list and dict formats
    patients = []
    if isinstance(data, list):
        # List of studies
        for study in data:
            for patient in study.get("patients", []):
                patients.append(patient)
    elif isinstance(data, dict):
        # Dict of studies
        for study_data in data.values():
            for patient in study_data.get("patients", []):
                patients.append(patient)
    else:
        raise ValueError(f"Unexpected data format: {type(data)}")
    
    # Apply filters
    eligible_patients = []
    for patient in patients:
        mutations = patient.get("mutations", [])
        outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
        
        # Check requirements
        if require_mutations and (not mutations or len(mutations) == 0):
            continue
        
        if require_pfs and outcomes.get("PFS_MONTHS") is None:
            continue
        
        if require_os and outcomes.get("OS_MONTHS") is None:
            continue
        
        eligible_patients.append(patient)
    
    return eligible_patients


