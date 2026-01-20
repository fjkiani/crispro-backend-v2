"""
Configuration for Universal Complete Care Orchestrator

Disease-specific configurations for SOC recommendations and biomarker thresholds.
"""

from typing import Dict, Any, Optional, Tuple
from api.services.disease_normalization import validate_disease_type as _shared_validate_disease_type

# SOC Recommendations by Disease Type
SOC_RECOMMENDATIONS = {
    "ovarian_cancer_hgs": {
        "first_line": {
            "regimen": "Carboplatin + Paclitaxel + Bevacizumab",
            "nccn_category": "Category 1",
            "rationale": "NCCN-preferred first-line therapy for advanced ovarian cancer",
            "dosing": {
                "carboplatin": "AUC 5-6 IV every 3 weeks",
                "paclitaxel": "175 mg/m² IV every 3 weeks",
                "bevacizumab": "15 mg/kg IV every 3 weeks (maintenance)"
            }
        },
        "second_line": {
            "regimen": "PARP inhibitor maintenance (if HRD+) or Platinum-based re-challenge",
            "nccn_category": "Category 1",
            "rationale": "HRD-positive patients benefit from PARP maintenance"
        }
    },
    "breast_cancer": {
        "first_line": {
            "regimen": "Doxorubicin + Cyclophosphamide → Paclitaxel",
            "nccn_category": "Category 1",
            "rationale": "Standard AC-T regimen for early-stage breast cancer"
        }
    },
    "colorectal_cancer": {
        "first_line": {
            "regimen": "FOLFOX or FOLFIRI",
            "nccn_category": "Category 1",
            "rationale": "Standard first-line therapy for metastatic colorectal cancer"
        }
    },
    "melanoma": {
        "first_line": {
            "regimen": "Nivolumab + Ipilimumab or Pembrolizumab",
            "nccn_category": "Category 1",
            "rationale": "Immune checkpoint inhibitors for advanced melanoma"
        }
    },
    "multiple_myeloma": {
        "first_line": {
            "regimen": "VRd (Bortezomib + Lenalidomide + Dexamethasone)",
            "nccn_category": "Category 1",
            "rationale": "Standard induction therapy for newly diagnosed multiple myeloma"
        }
    }
}

# Biomarker Configurations by Disease Type
BIOMARKER_CONFIG = {
    "ovarian_cancer_hgs": {
        "primary_biomarker": "ca125",
        "thresholds": {
            "normal": 35.0,
            "elevated": 35.0,
            "high": 100.0,
            "very_high": 500.0
        }
    },
    "prostate_cancer": {
        "primary_biomarker": "psa",
        "thresholds": {
            "normal": 4.0,
            "elevated": 4.0,
            "high": 10.0,
            "very_high": 20.0
        }
    },
    "colorectal_cancer": {
        "primary_biomarker": "cea",
        "thresholds": {
            "normal": 3.0,
            "elevated": 3.0,
            "high": 10.0,
            "very_high": 50.0
        }
    }
}


def validate_disease_type(disease: str) -> Tuple[bool, str]:
    """Validate and normalize disease type (shared implementation).

    IMPORTANT: no risky defaults (unknown stays 'unknown').
    """
    return _shared_validate_disease_type(disease)


def get_soc_recommendation(disease_type: str, treatment_line: str = "first_line") -> Optional[Dict[str, Any]]:
    """
    Get SOC recommendation for disease type and treatment line.
    
    Args:
        disease_type: Normalized disease type
        treatment_line: Treatment line (first_line, second_line, etc.)
    
    Returns:
        SOC recommendation dict or None if not found
    """
    is_valid, normalized_disease = validate_disease_type(disease_type)
    
    if not is_valid or normalized_disease not in SOC_RECOMMENDATIONS:
        return None
    
    disease_soc = SOC_RECOMMENDATIONS[normalized_disease]
    
    # Try specific treatment line
    if treatment_line in disease_soc:
        return disease_soc[treatment_line]
    
    # Fallback to first_line
    if "first_line" in disease_soc:
        return disease_soc["first_line"]
    
    return None


def get_biomarker_config(disease_type: str) -> Optional[Dict[str, Any]]:
    """
    Get biomarker configuration for disease type.
    
    Args:
        disease_type: Normalized disease type
    
    Returns:
        Biomarker config dict or None if not found
    """
    is_valid, normalized_disease = validate_disease_type(disease_type)
    
    if normalized_disease not in BIOMARKER_CONFIG:
        return None
    
    return BIOMARKER_CONFIG[normalized_disease]




















