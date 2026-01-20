"""
Therapy Fit Configuration: Disease validation, normalization, and default settings.

Provides universal disease support for Therapy Fit functionality.
Based on patterns from panel_config.py and complete_care_universal/config.py
"""

from typing import Dict, Tuple

# Disease mappings (case-insensitive, supports abbreviations)
# Based on panel_config.py:get_panel_for_disease() pattern
DISEASE_MAPPINGS: Dict[str, str] = {
    # Fully supported (have disease-specific panels)
    "ovarian": "ovarian_cancer",
    "ovarian_cancer": "ovarian_cancer",
    "hgsoc": "ovarian_cancer_hgs",
    "ovarian_cancer_hgs": "ovarian_cancer_hgs",
    "melanoma": "melanoma",
    "multiple_myeloma": "multiple_myeloma",
    "myeloma": "multiple_myeloma",
    "mm": "multiple_myeloma",
    
    # Partially supported (work but use fallback panel)
    "breast": "breast_cancer",
    "breast_cancer": "breast_cancer",
    "colorectal": "colorectal_cancer",
    "colorectal_cancer": "colorectal_cancer",
    "crc": "colorectal_cancer",
    "pancreatic": "pancreatic_cancer",
    "pancreatic_cancer": "pancreatic_cancer",
    "lung": "lung_cancer",
    "lung_cancer": "lung_cancer",
    "prostate": "prostate_cancer",
    "prostate_cancer": "prostate_cancer",
}

# Disease-specific default model selection
# Default to evo2_1b for all diseases (fastest, sufficient accuracy)
DEFAULT_MODELS: Dict[str, str] = {
    "ovarian_cancer": "evo2_1b",
    "ovarian_cancer_hgs": "evo2_1b",
    "breast_cancer": "evo2_1b",
    "colorectal_cancer": "evo2_1b",
    "melanoma": "evo2_1b",
    "multiple_myeloma": "evo2_1b",
    "pancreatic_cancer": "evo2_1b",
    "lung_cancer": "evo2_1b",
    "prostate_cancer": "evo2_1b",
}


def validate_disease_type(disease: str) -> Tuple[bool, str]:
    """
    Validate and normalize disease type.
    
    Uses same normalization pattern as panel_config.py:
    disease_lower = disease.lower().replace(" ", "_")
    
    Args:
        disease: Disease string (can be various formats like "MM", "Ovarian Cancer", "ovarian_cancer")
    
    Returns:
        (is_valid, normalized_disease)
        - is_valid: True if disease is recognized, False if using fallback
        - normalized_disease: Normalized disease name
    """
    if not disease:
        return False, "multiple_myeloma"  # Default fallback
    
    # Normalize input (same pattern as panel_config.py)
    disease_lower = disease.lower().replace(" ", "_")
    
    # Check if exact match exists
    if disease_lower in DISEASE_MAPPINGS:
        normalized = DISEASE_MAPPINGS[disease_lower]
        return True, normalized
    
    # Check if normalized value is a valid disease
    if disease_lower in DISEASE_MAPPINGS.values():
        return True, disease_lower
    
    # Fallback: return normalized form (may not be recognized)
    return False, disease_lower


def get_default_model(disease_type: str) -> str:
    """
    Get default model for disease type.
    
    Args:
        disease_type: Disease type (will be normalized)
    
    Returns:
        Default model ID (e.g., "evo2_1b")
    """
    _, normalized = validate_disease_type(disease_type)
    return DEFAULT_MODELS.get(normalized, "evo2_1b")
