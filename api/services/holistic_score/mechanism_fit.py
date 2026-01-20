"""
Mechanism Fit Calculator

Computes mechanism fit score from 7D vectors using cosine similarity.
"""

from typing import Dict, List, Any, Optional, Tuple
import logging

from .utils import dict_to_vector, l2_normalize

logger = logging.getLogger(__name__)


def compute_mechanism_fit(
    patient_profile: Dict[str, Any],
    trial: Dict[str, Any]
) -> Tuple[Optional[float], Dict[str, float]]:
    """
    Compute mechanism fit score from 7D vectors.
    
    Handles both array format [0.95, 0.0, ...] and dict format {"ddr": 0.95, ...}
    Uses cosine similarity for alignment.
    
    Args:
        patient_profile: Patient data with mechanism_vector
        trial: Trial data with moa_vector
    
    Returns:
        Tuple of (mechanism_fit_score, mechanism_alignment_dict)
    """
    patient_vector = patient_profile.get("mechanism_vector")
    trial_moa = trial.get("moa_vector")
    
    if not patient_vector or not trial_moa:
        return None, {}
    
    # Convert dict to array if needed
    if isinstance(trial_moa, dict):
        trial_moa = dict_to_vector(trial_moa)
    if isinstance(patient_vector, dict):
        patient_vector = dict_to_vector(patient_vector)
    
    # Ensure vectors are same length (7D expected)
    if len(patient_vector) != len(trial_moa):
        logger.warning(
            f"Vector length mismatch: patient={len(patient_vector)}, "
            f"trial={len(trial_moa)}"
        )
        return None, {}
    
    # L2 normalize
    patient_norm = l2_normalize(patient_vector)
    trial_norm = l2_normalize(trial_moa)
    
    # Cosine similarity
    score = sum(p * t for p, t in zip(patient_norm, trial_norm))
    score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
    
    # Pathway alignment breakdown
    pathway_names = ["DDR", "MAPK", "PI3K", "VEGF", "HER2", "IO", "Efflux"]
    alignment = {}
    for i, name in enumerate(pathway_names[:len(patient_vector)]):
        # Product of normalized values shows alignment strength
        alignment[name] = round(patient_norm[i] * trial_norm[i], 3)
    
    return round(score, 3), alignment
