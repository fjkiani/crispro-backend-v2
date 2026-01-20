"""
Biomarker Configuration for Universal Biomarker Intelligence

Disease-specific biomarker thresholds and response expectations.
"""

from typing import Dict, Any, Optional


# Biomarker Thresholds by Disease Type
BIOMARKER_THRESHOLDS = {
    "ovarian_cancer_hgs": {
        "ca125": {
            "burden_thresholds": {
                "MINIMAL": (0, 100),
                "MODERATE": (100, 500),
                "SIGNIFICANT": (500, 1000),
                "EXTENSIVE": (1000, float('inf'))
            },
            "normal_upper_limit": 35.0,
            "response_expectations": {
                "cycle3_drop_percent": 70,  # GOG-218, ICON7
                "cycle6_drop_percent": 90,
                "complete_response_threshold": 35,
                "resistance_threshold_percent": 50
            },
            "clinical_trials": ["GOG-218", "ICON7"],
            "guidelines": "NCCN Guidelines v2024"
        }
    },
    "prostate_cancer": {
        "psa": {
            "burden_thresholds": {
                "MINIMAL": (0, 4),
                "MODERATE": (4, 10),
                "SIGNIFICANT": (10, 20),
                "EXTENSIVE": (20, float('inf'))
            },
            "normal_upper_limit": 4.0,
            "response_expectations": {
                "cycle3_drop_percent": 50,  # PSA response typically slower
                "cycle6_drop_percent": 70,
                "complete_response_threshold": 0.1,  # PSA <0.1 ng/mL = undetectable
                "resistance_threshold_percent": 30
            },
            "clinical_trials": ["CHAARTED", "STAMPEDE"],
            "guidelines": "NCCN Guidelines v2024"
        }
    },
    "colorectal_cancer": {
        "cea": {
            "burden_thresholds": {
                "MINIMAL": (0, 3),
                "MODERATE": (3, 10),
                "SIGNIFICANT": (10, 50),
                "EXTENSIVE": (50, float('inf'))
            },
            "normal_upper_limit": 3.0,
            "response_expectations": {
                "cycle3_drop_percent": 60,  # CEA response patterns
                "cycle6_drop_percent": 80,
                "complete_response_threshold": 3.0,
                "resistance_threshold_percent": 40
            },
            "clinical_trials": ["FOLFOX", "FOLFIRI"],
            "guidelines": "NCCN Guidelines v2024"
        }
    }
}

# Biomarker Type Mapping by Disease
BIOMARKER_BY_DISEASE = {
    "ovarian_cancer_hgs": "ca125",
    "ovarian_cancer": "ca125",
    "hgsoc": "ca125",
    "prostate_cancer": "psa",
    "prostate": "psa",
    "colorectal_cancer": "cea",
    "colorectal": "cea",
    "crc": "cea"
}


def get_biomarker_config(disease_type: str, biomarker_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get biomarker configuration for disease type.
    
    Args:
        disease_type: Normalized disease type
        biomarker_type: Specific biomarker type (if None, uses primary biomarker for disease)
    
    Returns:
        Biomarker config dict or None if not found
    """
    # Normalize disease type
    disease_lower = disease_type.lower().strip()
    
    # Get primary biomarker if not specified
    if not biomarker_type:
        biomarker_type = BIOMARKER_BY_DISEASE.get(disease_lower)
        if not biomarker_type:
            # Try direct match
            if disease_lower in BIOMARKER_THRESHOLDS:
                # Get first biomarker for this disease
                biomarkers = BIOMARKER_THRESHOLDS[disease_lower]
                if biomarkers:
                    biomarker_type = list(biomarkers.keys())[0]
    
    if not biomarker_type or disease_lower not in BIOMARKER_THRESHOLDS:
        return None
    
    disease_config = BIOMARKER_THRESHOLDS.get(disease_lower, {})
    return disease_config.get(biomarker_type)


def get_primary_biomarker(disease_type: str) -> Optional[str]:
    """
    Get primary biomarker type for disease.
    
    Args:
        disease_type: Normalized disease type
    
    Returns:
        Biomarker type string or None
    """
    disease_lower = disease_type.lower().strip()
    return BIOMARKER_BY_DISEASE.get(disease_lower)




















