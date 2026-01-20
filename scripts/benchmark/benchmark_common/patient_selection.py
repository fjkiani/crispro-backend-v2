"""
Patient Selection Module

Unified patient selection logic for validation mode and sequential processing.
"""

from typing import List, Dict, Any


def select_validation_patients(
    all_patients: List[Dict[str, Any]],
    n_patients: int = 5,
    min_mutations: int = 1
) -> List[Dict[str, Any]]:
    """
    Select patients with lowest mutation counts for validation testing.
    
    Args:
        all_patients: All available patients
        n_patients: Number of patients to select
        min_mutations: Minimum mutations required (default: 1, excludes 0-mutation patients)
    
    Returns:
        List of selected patients (sorted by mutation count, ascending)
    """
    # Sort by mutation count, take lowest N
    patients_with_counts = [
        (p, len(p.get('mutations', [])))
        for p in all_patients
        if len(p.get('mutations', [])) >= min_mutations
    ]
    patients_with_counts.sort(key=lambda x: x[1])
    
    return [p for p, _ in patients_with_counts[:n_patients]]


def select_sequential_patients(
    all_patients: List[Dict[str, Any]],
    start_index: int,
    end_index: int
) -> List[Dict[str, Any]]:
    """
    Select sequential patients from index range.
    
    Args:
        all_patients: All available patients
        start_index: Starting index (inclusive)
        end_index: Ending index (exclusive)
    
    Returns:
        List of selected patients
    """
    return all_patients[start_index:end_index]


def calculate_time_estimate(patients: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate time estimate for processing patients.
    
    Args:
        patients: List of patients to process
    
    Returns:
        Dict with total_mutations, avg_mutations, expected_time_per_patient, max_expected_time
    """
    if not patients:
        return {
            "total_mutations": 0,
            "avg_mutations": 0.0,
            "expected_time_per_patient": 0.0,
            "max_expected_time": 0.0
        }
    
    mutation_counts = [len(p.get('mutations', [])) for p in patients]
    total_mutations = sum(mutation_counts)
    avg_mutations = total_mutations / len(patients)
    
    # Estimate: 1 second per mutation + 25 seconds overhead
    expected_time_per_patient = avg_mutations + 25.0
    max_expected_time = max(mutation_counts) + 25.0 if mutation_counts else 0.0
    
    return {
        "total_mutations": total_mutations,
        "avg_mutations": avg_mutations,
        "expected_time_per_patient": expected_time_per_patient,
        "max_expected_time": max_expected_time
    }


