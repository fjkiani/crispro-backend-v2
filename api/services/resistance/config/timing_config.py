"""
Timing & Chemosensitivity Configuration.

Disease- and regimen-specific parameters for timing engine.
All timing-related thresholds and cutpoints are centralized here.
"""

from typing import Optional

# Timing Configuration - Disease-Specific Parameters
TIMING_CONFIG = {
    "ovary": {
        "pfi_cutpoints_days": [180, 365],  # <6, 6–12, >12 months
        "pfi_categories": {
            "resistant": {"max_days": 180, "label": "<6m"},
            "partially_sensitive": {"min_days": 180, "max_days": 365, "label": "6-12m"},
            "sensitive": {"min_days": 365, "label": ">12m"}
        },
        "require_platinum_for_pfi": True,  # PFI only computed for platinum regimens
        "use_ca125_for_chemosensitivity": True,  # Use CA-125/KELIM features
        "pfi_event_definition": "next_platinum_or_progression"  # or "progression_only"
    },
    "endometrium": {
        "pfi_cutpoints_days": [180, 365],  # Recurrent endometrial cancer data
        "pfi_categories": {
            "resistant": {"max_days": 180, "label": "<6m"},
            "partially_sensitive": {"min_days": 180, "max_days": 365, "label": "6-12m"},
            "sensitive": {"min_days": 365, "label": ">12m"}
        },
        "require_platinum_for_pfi": True,
        "use_ca125_for_chemosensitivity": False,  # Endometrium doesn't use CA-125
        "pfi_event_definition": "next_platinum_or_progression"
    },
    "breast": {
        "pfi_cutpoints_days": [180, 365],  # Can differ if evidence supports it
        "pfi_categories": {
            "resistant": {"max_days": 180, "label": "<6m"},
            "partially_sensitive": {"min_days": 180, "max_days": 365, "label": "6-12m"},
            "sensitive": {"min_days": 365, "label": ">12m"}
        },
        "require_platinum_for_pfi": True,
        "use_ca125_for_chemosensitivity": False,  # Breast doesn't use CA-125
        "pfi_event_definition": "next_platinum_or_progression"
    },
    "pancreas": {
        "pfi_cutpoints_days": [180, 365],  # Default, can be calibrated
        "pfi_categories": {
            "resistant": {"max_days": 180, "label": "<6m"},
            "partially_sensitive": {"min_days": 180, "max_days": 365, "label": "6-12m"},
            "sensitive": {"min_days": 365, "label": ">12m"}
        },
        "require_platinum_for_pfi": True,
        "use_ca125_for_chemosensitivity": False,  # Pancreas doesn't use CA-125 (uses CA19-9, future)
        "pfi_event_definition": "next_platinum_or_progression"
    },
    "prostate": {
        "pfi_cutpoints_days": [180, 365],  # Default, can be calibrated
        "pfi_categories": {
            "resistant": {"max_days": 180, "label": "<6m"},
            "partially_sensitive": {"min_days": 180, "max_days": 365, "label": "6-12m"},
            "sensitive": {"min_days": 365, "label": ">12m"}
        },
        "require_platinum_for_pfi": True,
        "use_ca125_for_chemosensitivity": False,  # Prostate doesn't use CA-125 (uses PSA, future)
        "pfi_event_definition": "next_platinum_or_progression"
    },
    "default": {
        "pfi_cutpoints_days": [180, 365],  # Standard cutpoints
        "pfi_categories": {
            "resistant": {"max_days": 180, "label": "<6m"},
            "partially_sensitive": {"min_days": 180, "max_days": 365, "label": "6-12m"},
            "sensitive": {"min_days": 365, "label": ">12m"}
        },
        "require_platinum_for_pfi": True,
        "use_ca125_for_chemosensitivity": False,
        "pfi_event_definition": "next_platinum_or_progression"
    }
}

# Regimen Type Classifications
REGIMEN_TYPE_CLASSIFICATIONS = {
    "platinum": ["platinum", "carboplatin", "cisplatin", "oxaliplatin"],
    "PARPi": ["PARPi", "olaparib", "niraparib", "rucaparib", "talazoparib"],
    "ATR_inhibitor": ["ATRi", "ATR_inhibitor", "berzosertib", "ceralasertib"],
    "WEE1_inhibitor": ["WEE1i", "WEE1_inhibitor", "adavosertib"],
    "other_ddr_targeted": ["other_ddr_targeted", "CHK1", "POLQ", "DNA_PK"],
    "non_platinum_chemo": ["taxane", "anthracycline", "alkylating_agent", "antimetabolite"],
    "IO": ["PD1", "PDL1", "CTLA4", "checkpoint_inhibitor"],
}


def get_timing_config(disease_site: str) -> dict:
    """
    Get timing configuration for a given disease site.
    
    Args:
        disease_site: Disease site (ovary, endometrium, breast, pancreas, prostate, etc.)
    
    Returns:
        Timing configuration dictionary for the disease site, or default if not found
    """
    disease_site_lower = disease_site.lower() if disease_site else "default"
    return TIMING_CONFIG.get(disease_site_lower, TIMING_CONFIG["default"])


def is_platinum_regimen(regimen_type: str) -> bool:
    """
    Check if regimen type is platinum-based.
    
    Args:
        regimen_type: Regimen type string
    
    Returns:
        True if platinum regimen, False otherwise
    """
    if not regimen_type:
        return False
    regimen_lower = regimen_type.lower()
    platinum_types = [r.lower() for r in REGIMEN_TYPE_CLASSIFICATIONS.get("platinum", [])]
    return regimen_lower in platinum_types


def is_ddr_targeted_regimen(regimen_type: str) -> bool:
    """
    Check if regimen type is DDR-targeted (PARPi, ATRi, WEE1i, etc.).
    
    Args:
        regimen_type: Regimen type string
    
    Returns:
        True if DDR-targeted regimen, False otherwise
    """
    if not regimen_type:
        return False
    regimen_lower = regimen_type.lower()
    
    ddr_types = []
    for ddr_class in ["PARPi", "ATR_inhibitor", "WEE1_inhibitor", "other_ddr_targeted"]:
        ddr_types.extend([r.lower() for r in REGIMEN_TYPE_CLASSIFICATIONS.get(ddr_class, [])])
    
    return regimen_lower in ddr_types


def get_regimen_biomarker_class(regimen_type: str) -> Optional[str]:
    """
    Map regimen type to biomarker class (PARPi, ATRi, WEE1i, Other_DDRi).
    
    Args:
        regimen_type: Regimen type string
    
    Returns:
        Biomarker class string or None if not DDR-targeted
    """
    if not regimen_type:
        return None
    
    regimen_lower = regimen_type.lower()
    
    # Check each DDR class
    for ddr_class, type_list in REGIMEN_TYPE_CLASSIFICATIONS.items():
        if ddr_class in ["PARPi", "ATR_inhibitor", "WEE1_inhibitor", "other_ddr_targeted"]:
            if regimen_lower in [r.lower() for r in type_list]:
                if ddr_class == "ATR_inhibitor":
                    return "ATRi"
                elif ddr_class == "WEE1_inhibitor":
                    return "WEE1i"
                elif ddr_class == "other_ddr_targeted":
                    return "Other_DDRi"
                else:
                    return ddr_class
    
    return None
