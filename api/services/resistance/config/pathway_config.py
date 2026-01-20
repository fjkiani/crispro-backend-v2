"""
Pathway configuration constants.

Gene lists, weights, and thresholds for pathway-based detectors.
"""

# Pathway gene lists for post-treatment pathway profiling
# Source: POST_TREATMENT_PATHWAY_PROFILING.md (GSE165897 validation)
PATHWAY_GENE_LISTS = {
    "ddr": [
        "BRCA1", "BRCA2", "ATM", "ATR", "CHEK1", "CHEK2", "RAD51", "PARP1"
    ],
    "pi3k": [
        "PIK3CA", "AKT1", "AKT2", "PTEN", "MTOR"
    ],
    "vegf": [
        "VEGFA", "VEGFR1", "VEGFR2", "HIF1A"
    ],
}

# Composite score weights for post-treatment pathway profiling
# Source: GSE165897 validation (weighted composite preferred)
POST_TREATMENT_COMPOSITE_WEIGHTS = {
    "ddr": 0.4,   # DDR most critical for platinum resistance
    "pi3k": 0.3,  # PI3K and VEGF contribute equally
    "vegf": 0.3
}

# Resistance prediction thresholds for post-treatment pathway profiling
# Source: GSE165897 validation (median split)
POST_TREATMENT_RESISTANCE_THRESHOLDS = {
    "ddr_high": 0.65,   # High DDR → resistance
    "pi3k_high": 0.65,  # High PI3K → resistance
    "composite_high": 0.60  # High composite → resistance
}

# Pathway contribution weights for DNA repair capacity calculation
# Source: Manager C1 formula (DNA repair capacity = weighted pathway contributions)
PATHWAY_CONTRIBUTIONS = {
    "ddr": 0.60,  # DDR pathway (60% contribution to DNA repair capacity)
    "hrr": 0.20,  # HRR pathway (20% contribution)
    "exon": 0.20  # Exon disruption (20% contribution)
}

# 7D mechanism vector pathway order
# Order: DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux
PATHWAY_NAMES = ["DDR", "MAPK", "PI3K", "VEGF", "HER2", "IO", "Efflux"]
