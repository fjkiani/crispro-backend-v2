"""
DDR (DNA Damage Response) Deficiency Configuration.

Disease- and site-specific parameters for DDR_bin scoring engine.
All thresholds, gene lists, and rules can be tuned per disease while maintaining the same core architecture.
"""

# DDR Configuration - Disease-Specific Parameters
DDR_CONFIG = {
    "ovary": {
        "hrd_score_cutoff": 42,  # GIS-like threshold for HRD+ (Myriad MyChoice HRD)
        "core_hrr_genes": [
            "BRCA1", "BRCA2", "RAD51C", "RAD51D",
            "PALB2", "BARD1", "BRIP1"
        ],
        "extended_ddr_genes": [
            "ATM", "ATR", "CHEK1", "CHEK2",
            "FANCA", "FANCD2", "RAD50", "MRE11", "NBN", "POLQ"
        ],
        "require_biallelic_if_cn_available": True,  # Require CNA confirmation for BRCA biallelic
        "rules_priority": [
            "BRCA_pathogenic",
            "HRD_score_high",
            "core_hrr_pathogenic",
            "extended_ddr_pathogenic"
        ],
        "expected_prevalence_ddr_defective": 0.50,  # Approximate prevalence in ovarian cancer
        "expected_parpi_benefit_hr": 0.40,  # Approximate HR for PARPi benefit in DDR_defective vs proficient
    },
    "breast": {
        "hrd_score_cutoff": 42,  # Can differ per disease if evidence supports it
        "core_hrr_genes": [
            "BRCA1", "BRCA2", "PALB2",
            "RAD51C", "RAD51D", "BARD1", "BRIP1"
        ],
        "extended_ddr_genes": [
            "ATM", "ATR", "CHEK2",
            "FANCA", "FANCD2", "RAD50", "MRE11", "NBN"
        ],
        "require_biallelic_if_cn_available": True,
        "rules_priority": [
            "BRCA_pathogenic",
            "HRD_score_high",
            "core_hrr_pathogenic",
            "extended_ddr_pathogenic"
        ],
        "expected_prevalence_ddr_defective": 0.25,  # Approximate prevalence in breast cancer (TNBC higher)
        "expected_parpi_benefit_hr": 0.45,  # Approximate HR for PARPi benefit
    },
    "pancreas": {
        "hrd_score_cutoff": 42,  # Default, can be calibrated
        "core_hrr_genes": [
            "BRCA1", "BRCA2", "PALB2"
        ],
        "extended_ddr_genes": [
            "ATM", "ATR", "CHEK2"
        ],
        "require_biallelic_if_cn_available": False,  # May be less strict for pancreas
        "rules_priority": [
            "BRCA_pathogenic",
            "HRD_score_high",
            "core_hrr_pathogenic"
        ],
        "expected_prevalence_ddr_defective": 0.15,  # Approximate prevalence in pancreatic cancer
        "expected_parpi_benefit_hr": 0.50,  # Approximate HR for PARPi benefit
    },
    "prostate": {
        "hrd_score_cutoff": 42,  # Default, can be calibrated
        "core_hrr_genes": [
            "BRCA1", "BRCA2", "ATM"
        ],
        "extended_ddr_genes": [
            "CHEK2", "BRCA2"  # BRCA2 can appear in extended for prostate context
        ],
        "require_biallelic_if_cn_available": False,
        "rules_priority": [
            "BRCA_pathogenic",
            "HRD_score_high",
            "core_hrr_pathogenic"
        ],
        "expected_prevalence_ddr_defective": 0.10,  # Approximate prevalence in prostate cancer
        "expected_parpi_benefit_hr": 0.55,  # Approximate HR for PARPi benefit
    },
    "default": {
        "hrd_score_cutoff": 42,  # Standard GIS-like threshold
        "core_hrr_genes": [
            "BRCA1", "BRCA2", "PALB2", "RAD51C", "RAD51D"
        ],
        "extended_ddr_genes": [
            "ATM", "ATR", "CHEK2", "FANCA", "FANCD2", "RAD50", "MRE11", "NBN"
        ],
        "require_biallelic_if_cn_available": False,  # Default: less strict
        "rules_priority": [
            "BRCA_pathogenic",
            "HRD_score_high",
            "core_hrr_pathogenic",
            "extended_ddr_pathogenic"
        ],
        "expected_prevalence_ddr_defective": 0.20,  # Generic estimate
        "expected_parpi_benefit_hr": 0.45,  # Generic estimate
    }
}

# DDR Score Weights (for continuous scoring)
DDR_SCORE_WEIGHTS = {
    "BRCA_pathogenic": 3.0,      # Highest weight (BRCA most impactful)
    "HRD_positive": 2.5,         # High weight (genomic scar)
    "core_hrr_pathogenic": 2.0,  # Medium-high weight (core HRR pathway)
    "extended_ddr_pathogenic": 1.0,  # Lower weight (extended DDR pathway)
}

# Pathogenic variant classifications (to be considered for DDR_defective)
PATHOGENIC_VARIANT_CLASSIFICATIONS = [
    "pathogenic",
    "likely_pathogenic",
    "pathogenic_variant",
    "likely_pathogenic_variant",
]

# HRD Positive Status Values (from assays)
HRD_POSITIVE_STATUS_VALUES = [
    "HRD_positive",
    "HRD+",
    "HRD_POSITIVE",
    "positive",
    "POSITIVE",
]

# Copy-number states indicating loss (for biallelic detection)
CNA_LOSS_STATES = [
    "deletion",
    "loss",
    "loss_of_heterozygosity",
    "LOH",
    "homozygous_deletion",
]


def get_ddr_config(disease_site: str) -> dict:
    """
    Get DDR configuration for a given disease site.
    
    Args:
        disease_site: Disease site (ovary, breast, pancreas, prostate, etc.)
    
    Returns:
        DDR configuration dictionary for the disease site, or default if not found
    """
    disease_site_lower = disease_site.lower() if disease_site else "default"
    return DDR_CONFIG.get(disease_site_lower, DDR_CONFIG["default"])


def get_core_brca_genes() -> list:
    """Get list of core BRCA genes (BRCA1, BRCA2)."""
    return ["BRCA1", "BRCA2"]
