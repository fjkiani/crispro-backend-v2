"""Disease normalization utilities.

Goal: one shared, safe normalizer for MOAT services.

Key rule: **no risky defaults** (never map unknown → ovarian/MM). Unknown stays unknown.
"""

from __future__ import annotations

from typing import Dict, Tuple


# Canonical disease ids used across the backend.
# Keep this list intentionally small; expand via explicit PRs + tests.
SUPPORTED_DISEASES = {
    "ovarian_cancer_hgs",
    "multiple_myeloma",
    "melanoma",
    "breast_cancer",
    "colorectal_cancer",
    "pancreatic_cancer",
    "lung_cancer",
    "prostate_cancer",
}


# Input aliases → canonical ids
_DISEASE_ALIASES: Dict[str, str] = {
    # Ovarian
    "ov": "ovarian_cancer_hgs",
    "ovarian": "ovarian_cancer_hgs",
    "ovarian_cancer": "ovarian_cancer_hgs",
    "ovarian_cancer_hgs": "ovarian_cancer_hgs",
    "hgsoc": "ovarian_cancer_hgs",
    "high_grade_serous_ovarian": "ovarian_cancer_hgs",

    # Multiple Myeloma
    "mm": "multiple_myeloma",
    "myeloma": "multiple_myeloma",
    "multiple_myeloma": "multiple_myeloma",

    # Melanoma
    "melanoma": "melanoma",

    # Breast
    "breast": "breast_cancer",
    "breast_cancer": "breast_cancer",

    # Colorectal
    "crc": "colorectal_cancer",
    "colorectal": "colorectal_cancer",
    "colorectal_cancer": "colorectal_cancer",

    # Pancreatic
    "pancreatic": "pancreatic_cancer",
    "pancreatic_cancer": "pancreatic_cancer",

    # Lung
    "lung": "lung_cancer",
    "lung_cancer": "lung_cancer",

    # Prostate
    "prostate": "prostate_cancer",
    "prostate_cancer": "prostate_cancer",
}


def normalize_disease_string(disease: str) -> str:
    """Normalize raw disease string into a comparable key."""
    return (
        (disease or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def validate_disease_type(disease: str) -> Tuple[bool, str]:
    """Return (is_valid, normalized_disease).

    - If recognized: (True, canonical_disease)
    - If unknown/empty: (False, 'unknown')

    NOTE: This function intentionally does *not* do risky defaults.
    """
    key = normalize_disease_string(disease)
    if not key:
        return False, "unknown"

    # Exact alias
    if key in _DISEASE_ALIASES:
        return True, _DISEASE_ALIASES[key]

    # Already canonical
    if key in SUPPORTED_DISEASES:
        return True, key

    # Partial match (best-effort, still safe)
    for alias, canonical in _DISEASE_ALIASES.items():
        if alias in key or key in alias:
            return True, canonical

    return False, "unknown"
