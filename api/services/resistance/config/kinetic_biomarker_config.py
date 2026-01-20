"""
Kinetic Biomarker Configuration System.

Defines configurations for KELIM-like kinetic biomarkers (CA-125, PSA, future markers)
across different diseases with hierarchical architecture.
"""

from typing import Dict, Any, Optional


KINETIC_BIOMARKER_CONFIG = {
    "ovarian": {
        "ca125": {
            "class": "ELIM_RATE_CONSTANT_K",
            "marker_name": "CA-125",
            "use_cases": ["prognostic", "predictive", "therapeutic"],
            "evidence_level": "SOC",  # Standard of care / approaching standard
            "validation_status": {
                "prognostic": "validated",  # Multiple RCTs
                "predictive": "validated",  # ICON7, CHIVA, GOG-0218
                "therapeutic": "validated"  # IDS decision support
            },
            "modeling_approach": "mixed_effects",  # Population PK mixed-effects
            "data_requirements": {
                "min_measurements": 3,
                "time_window_days": 100,
                "requires_baseline": True,
                "baseline_window_days": 30  # Baseline within 30 days of treatment start
            },
            "cutoffs": {
                "favorable": 1.0,  # KELIM ≥1.0 = favorable (standardized)
                "intermediate": 0.5,  # 0.5-1.0 = intermediate
                "unfavorable": 0.0  # <0.5 = unfavorable
            },
            "categories": {
                "favorable": {"min": 1.0, "label": "Favorable"},
                "intermediate": {"min": 0.5, "max": 1.0, "label": "Intermediate"},
                "unfavorable": {"max": 0.5, "label": "Unfavorable"}
            }
        }
    },
    "prostate": {
        "psa": {
            "class": "ELIM_RATE_CONSTANT_K",
            "marker_name": "PSA",
            "use_cases": ["prognostic", "predictive", "therapeutic"],
            "evidence_level": "RUO",  # Research use only
            "validation_status": {
                "prognostic": "validated",  # Multiple studies
                "predictive": "exploratory",  # Early evidence
                "therapeutic": "exploratory"  # Early evidence
            },
            "modeling_approach": "mixed_effects",  # Same as CA-125
            "data_requirements": {
                "min_measurements": 3,
                "time_window_days": 100,
                "requires_baseline": True,
                "baseline_window_days": 30
            },
            "cutoffs": {
                "favorable": 1.0,  # PRO-KELIM ≥1.0 (may differ, TBD)
                "intermediate": 0.5,
                "unfavorable": 0.0
            },
            "categories": {
                "favorable": {"min": 1.0, "label": "Favorable"},
                "intermediate": {"min": 0.5, "max": 1.0, "label": "Intermediate"},
                "unfavorable": {"max": 0.5, "label": "Unfavorable"}
            }
        }
    },
    "default": {
        # Template for future markers (CEA, CA15-3, etc.)
        "marker_template": {
            "class": "ELIM_RATE_CONSTANT_K",
            "use_cases": ["prognostic"],  # Start with prognostic, expand
            "evidence_level": "EXPLORATORY",
            "validation_status": {
                "prognostic": "exploratory",
                "predictive": "exploratory",
                "therapeutic": "exploratory"
            },
            "modeling_approach": "mixed_effects",
            "data_requirements": {
                "min_measurements": 3,
                "time_window_days": 100,
                "requires_baseline": True,
                "baseline_window_days": 30
            },
            "cutoffs": {
                "favorable": 1.0,
                "intermediate": 0.5,
                "unfavorable": 0.0
            },
            "categories": {
                "favorable": {"min": 1.0, "label": "Favorable"},
                "intermediate": {"min": 0.5, "max": 1.0, "label": "Intermediate"},
                "unfavorable": {"max": 0.5, "label": "Unfavorable"}
            }
        }
    }
}


def get_kinetic_biomarker_config(disease_site: str, marker: str) -> Dict[str, Any]:
    """
    Get kinetic biomarker configuration for a given disease and marker.
    
    Args:
        disease_site: Disease site (ovarian, prostate, etc.)
        marker: Marker name (ca125, psa, cea, etc.)
    
    Returns:
        Configuration dict for the biomarker, or default template if not found
    """
    disease_site_lower = disease_site.lower() if disease_site else "default"
    marker_lower = marker.lower() if marker else None
    
    if disease_site_lower in KINETIC_BIOMARKER_CONFIG:
        disease_config = KINETIC_BIOMARKER_CONFIG[disease_site_lower]
        if marker_lower and marker_lower in disease_config:
            return disease_config[marker_lower]
    
    # Return default template
    return KINETIC_BIOMARKER_CONFIG["default"].get("marker_template", {})


def get_marker_for_disease(disease_site: str) -> Optional[str]:
    """
    Get the default kinetic biomarker marker for a disease site.
    
    Args:
        disease_site: Disease site (ovarian, prostate, etc.)
    
    Returns:
        Marker name (ca125, psa, etc.) or None if not configured
    """
    disease_site_lower = disease_site.lower() if disease_site else None
    
    if disease_site_lower in KINETIC_BIOMARKER_CONFIG:
        disease_config = KINETIC_BIOMARKER_CONFIG[disease_site_lower]
        # Return first marker (assuming one primary marker per disease)
        if disease_config:
            return list(disease_config.keys())[0]
    
    return None


def is_kinetic_biomarker_available(disease_site: str, marker: Optional[str] = None) -> bool:
    """
    Check if a kinetic biomarker is available for a disease site.
    
    Args:
        disease_site: Disease site (ovarian, prostate, etc.)
        marker: Optional marker name. If None, checks if any marker is available.
    
    Returns:
        True if biomarker is available, False otherwise
    """
    disease_site_lower = disease_site.lower() if disease_site else None
    
    if not disease_site_lower or disease_site_lower not in KINETIC_BIOMARKER_CONFIG:
        return False
    
    disease_config = KINETIC_BIOMARKER_CONFIG[disease_site_lower]
    
    if marker:
        return marker.lower() in disease_config
    else:
        return len(disease_config) > 0
