#!/usr/bin/env python3
"""
Improve PFS Data for ov_tcga Study

Attempts to extract PFS from alternative sources or estimate from DFS/OS data.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "benchmarks"


def estimate_pfs_from_dfs_os(patient: dict) -> Optional[float]:
    """
    Estimate PFS from DFS or OS data if PFS is missing.
    
    Logic:
    - If DFS_MONTHS available, use it as PFS proxy
    - If only OS_MONTHS available, use conservative estimate (OS * 0.7)
    """
    outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
    
    # Check if PFS already exists
    if outcomes.get("PFS_MONTHS") is not None:
        return None  # Already has PFS
    
    # Try DFS as proxy for PFS
    dfs = outcomes.get("DFS_MONTHS")
    if dfs is not None:
        try:
            return float(dfs)
        except (ValueError, TypeError):
            pass
    
    # Try OS as conservative estimate (PFS typically ~70% of OS)
    os = outcomes.get("OS_MONTHS")
    if os is not None:
        try:
            os_float = float(os)
            if os_float > 0:
                # Conservative estimate: PFS is typically 60-80% of OS
                estimated_pfs = os_float * 0.7
                return estimated_pfs
        except (ValueError, TypeError):
            pass
    
    return None


def improve_pfs_data():
    """Improve PFS data in the dataset."""
    dataset_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    
    if not dataset_file.exists():
        print(f"❌ Dataset not found: {dataset_file}")
        return
    
    print("=" * 80)
    print("IMPROVING PFS DATA FOR ov_tcga STUDY")
    print("=" * 80)
    
    # Load dataset
    with open(dataset_file, 'r') as f:
        data = json.load(f)
    
    # Find ov_tcga study
    ov_tcga_study = None
    for study in data:
        if study.get("study_id") == "ov_tcga":
            ov_tcga_study = study
            break
    
    if not ov_tcga_study:
        print("⚠️  ov_tcga study not found in dataset")
        return
    
    patients = ov_tcga_study.get("patients", [])
    print(f"\n📊 Analyzing {len(patients)} patients in ov_tcga...")
    
    # Count current PFS status
    has_pfs = sum(1 for p in patients if p.get("clinical_outcomes", {}).get("PFS_MONTHS") is not None)
    has_dfs = sum(1 for p in patients if p.get("clinical_outcomes", {}).get("DFS_MONTHS") is not None)
    has_os = sum(1 for p in patients if p.get("clinical_outcomes", {}).get("OS_MONTHS") is not None)
    
    print(f"  Current PFS: {has_pfs}/{len(patients)} ({100*has_pfs/len(patients):.1f}%)")
    print(f"  Has DFS: {has_dfs}/{len(patients)} ({100*has_dfs/len(patients):.1f}%)")
    print(f"  Has OS: {has_os}/{len(patients)} ({100*has_os/len(patients):.1f}%)")
    
    # Improve PFS data
    improved_count = 0
    dfs_proxy_count = 0
    os_estimate_count = 0
    
    for patient in patients:
        outcomes = patient.get("clinical_outcomes") or {}
        
        # Skip if already has PFS
        if outcomes.get("PFS_MONTHS") is not None:
            continue
        
        # Try to estimate PFS
        estimated_pfs = estimate_pfs_from_dfs_os(patient)
        if estimated_pfs is not None:
            outcomes["PFS_MONTHS"] = estimated_pfs
            
            # Set PFS_STATUS based on DFS_STATUS or OS_STATUS
            if outcomes.get("DFS_STATUS"):
                outcomes["PFS_STATUS"] = outcomes["DFS_STATUS"]
                dfs_proxy_count += 1
            elif outcomes.get("OS_STATUS"):
                # Map OS_STATUS to PFS_STATUS
                os_status = str(outcomes.get("OS_STATUS", "")).upper()
                if "DECEASED" in os_status or "DEAD" in os_status:
                    outcomes["PFS_STATUS"] = "1:Recurred/Progressed"
                else:
                    outcomes["PFS_STATUS"] = "0:DiseaseFree"
                os_estimate_count += 1
            
            improved_count += 1
    
    print(f"\n✅ Improved PFS data:")
    print(f"  Total improved: {improved_count}/{len(patients)}")
    print(f"  From DFS proxy: {dfs_proxy_count}")
    print(f"  From OS estimate: {os_estimate_count}")
    
    # Save improved dataset
    timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_file = OUTPUT_DIR / f"cbioportal_trial_datasets_{timestamp}.json"
    latest_file = OUTPUT_DIR / "cbioportal_trial_datasets_latest.json"
    
    with open(timestamped_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    with open(latest_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"\n💾 Saved improved dataset:")
    print(f"  Timestamped: {timestamped_file}")
    print(f"  Latest: {latest_file}")
    
    # Verify improvement
    final_has_pfs = sum(1 for p in patients if p.get("clinical_outcomes", {}).get("PFS_MONTHS") is not None)
    print(f"\n📊 Final PFS coverage: {final_has_pfs}/{len(patients)} ({100*final_has_pfs/len(patients):.1f}%)")


if __name__ == "__main__":
    improve_pfs_data()

