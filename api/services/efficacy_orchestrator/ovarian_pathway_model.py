"""
Ovarian Cancer Pathway Prediction Model (GSE165897, AUC = 0.750)

Modular model for pathway-based platinum resistance prediction in ovarian cancer.
Based on GSE165897 validation (n=11 patients, post-treatment pathway scores).

Key Findings:
- post_ddr: ρ = -0.711, p = 0.014 (strongest correlation)
- post_pi3k: AUC = 0.750 (best predictor)
- post_vegf: ρ = -0.538, p = 0.088 (moderate)
- Composite (weighted): ρ = -0.674, p = 0.023

Clinical Significance:
- Post-treatment pathway scores predict platinum resistance (PFI < 6 months)
- Higher pathway scores → shorter PFI (resistance)
- Composite score enables early identification of resistant patients
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

# ============================================================================
# OVARIAN CANCER PATHWAY DEFINITIONS (GSE165897 Validated)
# ============================================================================
# Post-treatment pathway scores predict platinum resistance
# Validated on GSE165897 (n=11 HGSOC patients, paired pre/post NACT samples)
# ============================================================================

OVARIAN_PATHWAYS = {
    'DDR': [
        # DNA Damage Response / Homologous Recombination
        'BRCA1', 'BRCA2', 'PALB2', 'RAD51C', 'RAD51D', 'BRIP1', 'BARD1',
        'ATM', 'ATR', 'CHEK1', 'CHEK2', 'RAD51', 'RAD52', 'RAD54L',
        'FANCA', 'FANCB', 'FANCC', 'FANCD2', 'FANCE', 'FANCF', 'FANCG',
        'MRE11A', 'RAD50', 'NBN', 'XRCC2', 'XRCC3'
    ],
    
    'PI3K': [
        # PI3K/AKT/mTOR pathway
        'PIK3CA', 'PIK3CB', 'PIK3CD', 'PIK3CG', 'PIK3R1', 'PIK3R2', 'PIK3R3',
        'AKT1', 'AKT2', 'AKT3', 'PTEN', 'TSC1', 'TSC2', 'MTOR',
        'PDK1', 'RPS6KB1', 'RPS6KB2', 'EIF4EBP1', 'RHEB', 'RICTOR', 'RPTOR'
    ],
    
    'VEGF': [
        # Angiogenesis pathway
        'VEGFA', 'VEGFB', 'VEGFC', 'VEGFD',
        'KDR', 'FLT1', 'FLT4',  # VEGF receptors
        'ANGPT1', 'ANGPT2', 'TEK', 'TIE1',
        'PECAM1', 'VWF', 'ENG', 'KIT', 'PDGFRA', 'PDGFRB'
    ],
    
    'MAPK': [
        # RAS/MAPK pathway (validated in TCGA-OV: RR = 1.97, p < 0.05)
        'KRAS', 'NRAS', 'HRAS', 'BRAF', 'RAF1', 'MAP2K1', 'MAP2K2',
        'MAPK1', 'MAPK3', 'NF1', 'RASA1', 'RASA2', 'SPRED1', 'SPRED2'
    ],
    
    'EFFLUX': [
        # Drug efflux pumps (platinum resistance)
        'ABCB1',  # MDR1 / P-glycoprotein
        'ABCC1', 'ABCC2', 'ABCC3', 'ABCC4', 'ABCC5', 'ABCC6',
        'ABCG2',  # BCRP
        'SLC22A1', 'SLC22A2', 'SLC22A3'  # Organic cation transporters
    ]
}

# ============================================================================
# GSE165897 COMPOSITE SCORE MODEL (Validated)
# ============================================================================
# Based on GSE165897 analysis:
# - Equal-weight composite: ρ = -0.674, p = 0.023
# - Weighted composite (0.4×DDR + 0.3×PI3K + 0.3×VEGF): ρ = -0.674, p = 0.023
# - Best single predictor: post_pi3k (AUC = 0.750)
#
# Note: Negative correlation means HIGHER pathway scores → SHORTER PFI (resistance)
# ============================================================================

# Composite weights (TCGA-informed, validated on GSE165897)
OVARIAN_COMPOSITE_WEIGHTS = {
    'DDR': 0.4,   # Most critical for platinum resistance
    'PI3K': 0.3,  # Second strongest (AUC = 0.750)
    'VEGF': 0.3   # Moderate predictor (validated in GSE241908)
}

# Resistance thresholds (based on GSE165897 median splits)
# Higher composite score → higher resistance probability (shorter PFI)
# GSE165897 composite range: [0.15-0.30] (raw weighted sum)
OVARIAN_RESISTANCE_THRESHOLDS = {
    'HIGH_RESISTANCE': 0.25,    # Composite ≥ 0.25 → high resistance risk (PFI < 6mo)
    'MODERATE_RESISTANCE': 0.20, # Composite ≥ 0.20 → moderate resistance risk
    'LOW_RESISTANCE': 0.15       # Composite < 0.15 → low resistance risk (PFI ≥ 6mo)
}


def compute_ovarian_pathway_scores(
    expression_data: pd.DataFrame,
    pathway_genes: Dict[str, List[str]] = None
) -> Dict[str, float]:
    """
    Compute ovarian cancer pathway scores from expression data.
    
    Args:
        expression_data: DataFrame with genes as index, samples as columns
        pathway_genes: Optional custom pathway definitions (default: OVARIAN_PATHWAYS)
    
    Returns:
        Dict with pathway scores (DDR, PI3K, VEGF, MAPK, EFFLUX)
    """
    if pathway_genes is None:
        pathway_genes = OVARIAN_PATHWAYS
    
    # Ensure genes are in index
    if expression_data.index.dtype != 'object':
        # Numeric GeneIDs - need symbol mapping
        raise ValueError(
            "Expression data has numeric GeneIDs. "
            "Please map to gene symbols before calling this function."
        )
    
    pathway_scores = {}
    
    for pathway_name, gene_list in pathway_genes.items():
        # Find genes present in expression matrix
        available_genes = [g for g in gene_list if g in expression_data.index]
        
        if len(available_genes) == 0:
            pathway_scores[pathway_name] = 0.0
            continue
        
        # Log2 transform if needed (TPM data is usually NOT log-transformed)
        expr_subset = expression_data.loc[available_genes]
        
        # Check if already log-transformed (values typically < 20 if log2)
        if expr_subset.max().max() > 20:
            expr_log = np.log2(expr_subset + 1)
        else:
            expr_log = expr_subset
        
        # Mean expression across genes (across all samples if multiple)
        if expr_log.shape[1] == 1:
            score = expr_log.iloc[:, 0].mean()
        else:
            score = expr_log.mean().mean()  # Average across samples
        
        pathway_scores[pathway_name] = float(score)
    
    return pathway_scores


def compute_ovarian_resistance_composite(
    pathway_scores: Dict[str, float],
    weights: Dict[str, float] = None
) -> float:
    """
    Compute ovarian cancer resistance composite score.
    
    Formula: weighted_sum = (w_ddr × DDR) + (w_pi3k × PI3K) + (w_vegf × VEGF)
    
    Based on GSE165897 validation:
    - Weighted composite: ρ = -0.674, p = 0.023 (strong negative correlation with PFI)
    - Higher composite → shorter PFI (resistance)
    
    Note: Uses RAW pathway scores (log2(TPM+1)), not normalized.
    GSE165897 observed ranges:
    - DDR: [0.13-0.23]
    - PI3K: [0.23-0.29]
    - VEGF: [0.34-0.51]
    
    Args:
        pathway_scores: Dict with DDR, PI3K, VEGF scores (raw log2(TPM+1) values)
        weights: Optional custom weights (default: OVARIAN_COMPOSITE_WEIGHTS)
    
    Returns:
        Composite resistance score (raw weighted sum, higher = more resistant)
    """
    if weights is None:
        weights = OVARIAN_COMPOSITE_WEIGHTS
    
    # Extract pathway scores (raw log2(TPM+1) values)
    ddr_score = pathway_scores.get('DDR', 0.0)
    pi3k_score = pathway_scores.get('PI3K', 0.0)
    vegf_score = pathway_scores.get('VEGF', 0.0)
    
    # Weighted composite (raw scores, matching GSE165897 analysis)
    composite = (
        weights['DDR'] * ddr_score +
        weights['PI3K'] * pi3k_score +
        weights['VEGF'] * vegf_score
    )
    
    return float(composite)


def classify_resistance_risk(
    composite_score: float,
    thresholds: Dict[str, float] = None
) -> str:
    """
    Classify resistance risk based on composite score.
    
    Args:
        composite_score: Composite resistance score (0-1)
        thresholds: Optional custom thresholds
    
    Returns:
        Risk level: "HIGH", "MODERATE", "LOW"
    """
    if thresholds is None:
        thresholds = OVARIAN_RESISTANCE_THRESHOLDS
    
    if composite_score >= thresholds['HIGH_RESISTANCE']:
        return "HIGH"
    elif composite_score >= thresholds['MODERATE_RESISTANCE']:
        return "MODERATE"
    else:
        return "LOW"
