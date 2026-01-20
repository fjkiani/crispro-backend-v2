"""
Panel Configuration: Drug panel configuration management.
"""
from typing import Dict, Any, List


# Simple configurable panel (extensible via env or future DB)
DEFAULT_MM_PANEL: List[Dict[str, Any]] = [
    {"name": "BRAF inhibitor", "moa": "MAPK blockade", "pathway_weights": {"ras_mapk": 0.8, "tp53": 0.2}},
    {"name": "MEK inhibitor", "moa": "MAPK downstream blockade", "pathway_weights": {"ras_mapk": 0.9, "tp53": 0.1}},
    {"name": "IMiD", "moa": "immunomodulatory", "pathway_weights": {"ras_mapk": 0.2, "tp53": 0.3}},
    {"name": "Proteasome inhibitor", "moa": "proteostasis stress", "pathway_weights": {"ras_mapk": 0.3, "tp53": 0.4}},
    {"name": "Anti-CD38", "moa": "antibody", "pathway_weights": {"ras_mapk": 0.1, "tp53": 0.1}},
]

# Ovarian cancer drug panel
DEFAULT_OVARIAN_PANEL: List[Dict[str, Any]] = [
    # PARP / Platinum should primarily align to DDR (avoid accidental TP53-only alignment)
    {"name": "olaparib", "moa": "PARP inhibitor", "pathway_weights": {"ddr": 1.0}},
    {"name": "niraparib", "moa": "PARP inhibitor", "pathway_weights": {"ddr": 1.0}},
    {"name": "rucaparib", "moa": "PARP inhibitor", "pathway_weights": {"ddr": 1.0}},
    {"name": "carboplatin", "moa": "platinum alkylating agent", "pathway_weights": {"ddr": 1.0}},

    # Hard-set critical non-DDR mechanisms (so S/P/E can win beyond DDR→PARP)
    {"name": "adavosertib", "moa": "WEE1 inhibitor", "pathway_weights": {"tp53": 1.0}},
    {"name": "ceralasertib", "moa": "ATR inhibitor", "pathway_weights": {"ddr": 0.7, "tp53": 0.3}},
    {"name": "trametinib", "moa": "MEK inhibitor", "pathway_weights": {"ras_mapk": 1.0}},

    {"name": "bevacizumab", "moa": "anti-VEGF", "pathway_weights": {"vegf": 0.9}},
    {"name": "pembrolizumab", "moa": "anti-PD-1", "pathway_weights": {"io": 0.8}},
]



# Breast cancer drug panel (minimal for benchmarking)
DEFAULT_BREAST_PANEL: List[Dict[str, Any]] = [
    {"name": "olaparib", "moa": "PARP inhibitor", "pathway_weights": {"ddr": 1.0}},
    {"name": "talazoparib", "moa": "PARP inhibitor", "pathway_weights": {"ddr": 1.0}},
    {"name": "ceralasertib", "moa": "ATR inhibitor", "pathway_weights": {"ddr": 0.7, "tp53": 0.3}},
    {"name": "adavosertib", "moa": "WEE1 inhibitor", "pathway_weights": {"tp53": 1.0}},
    {"name": "trametinib", "moa": "MEK inhibitor", "pathway_weights": {"ras_mapk": 1.0}},
    {"name": "pembrolizumab", "moa": "anti-PD-1", "pathway_weights": {"io": 0.8}},
]

# Prostate cancer drug panel (minimal for benchmarking)
DEFAULT_PROSTATE_PANEL: List[Dict[str, Any]] = [
    {"name": "olaparib", "moa": "PARP inhibitor", "pathway_weights": {"ddr": 1.0}},
    {"name": "talazoparib", "moa": "PARP inhibitor", "pathway_weights": {"ddr": 1.0}},
    {"name": "ceralasertib", "moa": "ATR inhibitor", "pathway_weights": {"ddr": 0.7, "tp53": 0.3}},
    {"name": "adavosertib", "moa": "WEE1 inhibitor", "pathway_weights": {"tp53": 1.0}},
]



# Synthetic lethality publication panel (minimal, avoids non-specific chemo confounds)
# Goal: benchmark SL-specific ranking (PARP/ATR/WEE1) without carboplatin dominating ties.
DEFAULT_SL_PUBLICATION_PANEL: List[Dict[str, Any]] = [
    {"name": "olaparib", "moa": "PARP inhibitor", "pathway_weights": {"ddr": 1.0}},
    {"name": "niraparib", "moa": "PARP inhibitor", "pathway_weights": {"ddr": 1.0}},
    {"name": "rucaparib", "moa": "PARP inhibitor", "pathway_weights": {"ddr": 1.0}},
    {"name": "talazoparib", "moa": "PARP inhibitor", "pathway_weights": {"ddr": 1.0}},

    {"name": "ceralasertib", "moa": "ATR inhibitor", "pathway_weights": {"ddr": 0.7, "tp53": 0.3}},
    {"name": "adavosertib", "moa": "WEE1 inhibitor", "pathway_weights": {"tp53": 1.0}},

    # Non-SL targeted therapy candidates (for SL-negative cases to avoid PARP FP)
    {"name": "trametinib", "moa": "MEK inhibitor", "pathway_weights": {"ras_mapk": 1.0}},
    {"name": "osimertinib", "moa": "EGFR inhibitor", "pathway_weights": {"ras_mapk": 1.0}},
]

# Melanoma drug panel
DEFAULT_MELANOMA_PANEL: List[Dict[str, Any]] = [
    {"name": "BRAF inhibitor", "moa": "MAPK blockade", "pathway_weights": {"ras_mapk": 0.9}},
    {"name": "MEK inhibitor", "moa": "MAPK downstream blockade", "pathway_weights": {"ras_mapk": 0.9}},
    {"name": "pembrolizumab", "moa": "anti-PD-1", "pathway_weights": {"io": 0.8}},
    {"name": "nivolumab", "moa": "anti-PD-1", "pathway_weights": {"io": 0.8}},
    {"name": "ipilimumab", "moa": "anti-CTLA-4", "pathway_weights": {"io": 0.7}},
]


def get_default_panel() -> List[Dict[str, Any]]:
    """Get the default MM drug panel configuration."""
    return DEFAULT_MM_PANEL.copy()


def get_panel_for_disease(disease: str = None) -> List[Dict[str, Any]]:
    """
    Get disease-specific drug panel.
    
    Args:
        disease: Disease name (e.g., "ovarian_cancer", "melanoma", "multiple_myeloma")
        
    Returns:
        List of drug dictionaries with pathway weights
    """
    if not disease:
        return get_default_panel()  # Backward compatible
    
    disease_lower = disease.lower().replace(" ", "_")
    
    if "sl_publication" in disease_lower or disease_lower in {"sl", "synthetic_lethality"}:
        return DEFAULT_SL_PUBLICATION_PANEL.copy()
    if "ovarian" in disease_lower:
        return DEFAULT_OVARIAN_PANEL.copy()
    elif "breast" in disease_lower:
        return DEFAULT_BREAST_PANEL.copy()
    elif "prostate" in disease_lower:
        return DEFAULT_PROSTATE_PANEL.copy()
    elif "melanoma" in disease_lower:
        return DEFAULT_MELANOMA_PANEL.copy()
    elif "myeloma" in disease_lower or disease_lower == "mm":
        return DEFAULT_MM_PANEL.copy()
    
    # Fallback to MM panel for unknown diseases
    return get_default_panel()


