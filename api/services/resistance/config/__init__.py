"""
Configuration constants for resistance prediction modules.

All hard-coded values are centralized here for easier maintenance.
"""

from .pathway_config import (
    PATHWAY_GENE_LISTS,
    POST_TREATMENT_COMPOSITE_WEIGHTS,
    POST_TREATMENT_RESISTANCE_THRESHOLDS,
    PATHWAY_CONTRIBUTIONS,
    PATHWAY_NAMES,
)
from .risk_config import (
    RISK_STRATIFICATION_THRESHOLDS,
    CONFIDENCE_CONFIG,
)
from .treatment_config import (
    TREATMENT_LINE_MULTIPLIERS,
    CROSS_RESISTANCE_MULTIPLIER,
    MAX_PROBABILITY_CAP,
)
from .detector_config import (
    DNA_REPAIR_THRESHOLD,
    MM_HIGH_RISK_GENES,
)
from .ddr_config import (
    DDR_CONFIG,
    DDR_SCORE_WEIGHTS,
    PATHOGENIC_VARIANT_CLASSIFICATIONS,
    HRD_POSITIVE_STATUS_VALUES,
    CNA_LOSS_STATES,
    get_ddr_config,
    get_core_brca_genes,
)
from .timing_config import (
    TIMING_CONFIG,
    REGIMEN_TYPE_CLASSIFICATIONS,
    get_timing_config,
    is_platinum_regimen,
    is_ddr_targeted_regimen,
    get_regimen_biomarker_class,
)
from .kinetic_biomarker_config import (
    KINETIC_BIOMARKER_CONFIG,
    get_kinetic_biomarker_config,
    get_marker_for_disease,
    is_kinetic_biomarker_available,
)

__all__ = [
    # Pathway configuration
    "PATHWAY_GENE_LISTS",
    "POST_TREATMENT_COMPOSITE_WEIGHTS",
    "POST_TREATMENT_RESISTANCE_THRESHOLDS",
    "PATHWAY_CONTRIBUTIONS",
    "PATHWAY_NAMES",
    # Risk configuration
    "RISK_STRATIFICATION_THRESHOLDS",
    "CONFIDENCE_CONFIG",
    # Treatment configuration
    "TREATMENT_LINE_MULTIPLIERS",
    "CROSS_RESISTANCE_MULTIPLIER",
    "MAX_PROBABILITY_CAP",
    # Detector configuration
    "DNA_REPAIR_THRESHOLD",
    "MM_HIGH_RISK_GENES",
    # DDR configuration
    "DDR_CONFIG",
    "DDR_SCORE_WEIGHTS",
    "PATHOGENIC_VARIANT_CLASSIFICATIONS",
    "HRD_POSITIVE_STATUS_VALUES",
    "CNA_LOSS_STATES",
    "get_ddr_config",
    "get_core_brca_genes",
    # Timing configuration
    "TIMING_CONFIG",
    "REGIMEN_TYPE_CLASSIFICATIONS",
    "get_timing_config",
    "is_platinum_regimen",
    "is_ddr_targeted_regimen",
    "get_regimen_biomarker_class",
    # Kinetic biomarker configuration
    "KINETIC_BIOMARKER_CONFIG",
    "get_kinetic_biomarker_config",
    "get_marker_for_disease",
    "is_kinetic_biomarker_available",
]
