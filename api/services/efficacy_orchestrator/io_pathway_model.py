"""
IO Pathway Prediction Model (GSE91061, AUC = 0.780)

Modular model for pathway-based IO response prediction.
Extracted from sporadic_gates.py for clarity and testability.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

# ============================================================================
# GSE91061 IO PATHWAY DEFINITIONS (Validated AUC = 0.780)
# ============================================================================
# Pre-treatment IO pathway signatures predict anti-PD-1 response
# Validated on GSE91061 (n=51 melanoma samples, nivolumab)
# ============================================================================

IO_PATHWAYS = {
    'TIL_INFILTRATION': [
        'CD8A', 'CD8B', 'CD3D', 'CD3E', 'CD3G',
        'CD4', 'CD2', 'GZMA', 'GZMB', 'PRF1', 
        'IFNG', 'TNF', 'IL2'
    ],
    
    'T_EFFECTOR': [
        'CD274',      # PD-L1
        'PDCD1LG2',   # PD-L2
        'IDO1', 'IDO2',
        'CXCL9', 'CXCL10', 'CXCL11',  # IFNγ-induced chemokines
        'HLA-DRA', 'HLA-DRB1',
        'STAT1', 'IRF1', 'IFNG'
    ],
    
    'ANGIOGENESIS': [
        'VEGFA', 'VEGFB', 'VEGFC', 'VEGFD',
        'KDR', 'FLT1', 'FLT4',  # VEGF receptors
        'ANGPT1', 'ANGPT2', 'TEK',
        'PECAM1', 'VWF'
    ],
    
    'TGFB_RESISTANCE': [
        'TGFB1', 'TGFB2', 'TGFB3',
        'TGFBR1', 'TGFBR2', 'TGFBR3',
        'SMAD2', 'SMAD3', 'SMAD4', 'SMAD7'
    ],
    
    'MYELOID_INFLAMMATION': [
        'IL6', 'IL1B', 'IL8', 'CXCL8',
        'CXCL1', 'CXCL2', 'CXCL3',
        'PTGS2',  # COX2
        'CCL2', 'CCL3', 'CCL4',
        'S100A8', 'S100A9', 'S100A12'
    ],
    
    'PROLIFERATION': [
        'MKI67', 'PCNA', 'TOP2A',
        'CCNA2', 'CCNB1', 'CCNB2',
        'CDK1', 'CDK2', 'CDK4',
        'CDC20', 'AURKA', 'AURKB'
    ],
    
    'IMMUNOPROTEASOME': [
        'PSMB8', 'PSMB9', 'PSMB10',  # Immunoproteasome subunits
        'TAP1', 'TAP2',  # Antigen processing
        'B2M',  # Beta-2-microglobulin
        'HLA-A', 'HLA-B', 'HLA-C'  # MHC-I
    ],
    
    'EXHAUSTION': [
        'PDCD1',   # PD-1
        'CTLA4', 'LAG3', 'TIGIT', 'HAVCR2',  # TIM-3
        'BTLA', 'CD96', 'VSIR'  # VISTA
    ]
}

# ============================================================================
# GSE91061 LOGISTIC REGRESSION MODEL (UNSTANDARDIZED COEFFICIENTS)
# ============================================================================
# CRITICAL: These coefficients are UNSTANDARDIZED (for use with raw pathway scores)
# Original LR was trained on StandardScaler-normalized data, then converted back
# to unstandardized form for direct application to raw pathway scores.
#
# Extraction method:
#   1. Train LR on StandardScaler-normalized pathway scores
#   2. Convert coefficients: coef_unstd = coef_std / std(X)
#   3. Convert intercept: intercept_unstd = intercept_std - sum(coef_std * mean(X) / std(X))
#
# Validation: Verified against gse91061_analysis_with_composites.csv
# ============================================================================

IO_LR_COEFFICIENTS = {
    'EXHAUSTION': 0.747468,         # Strongest positive predictor (unstandardized)
    'TIL_INFILTRATION': 0.513477,   # Second strongest positive predictor (unstandardized)
    'ANGIOGENESIS': 0.365093,       # Moderate positive (unstandardized)
    'MYELOID_INFLAMMATION': 0.077617, # Weak positive (unstandardized)
    'TGFB_RESISTANCE': -0.369679,   # Weak negative (resistance, unstandardized)
    'T_EFFECTOR': -0.145055,        # Weak negative (counterintuitive, unstandardized)
    'PROLIFERATION': -0.357712,     # Moderate negative (unstandardized)
    'IMMUNOPROTEASOME': -0.819168   # Strongest negative (counterintuitive, unstandardized)
}

# Logistic regression intercept (UNSTANDARDIZED, from GSE91061 training)
# Extracted from actual LR model: intercept_unstd = 4.038603
IO_LR_INTERCEPT = 4.038603


def compute_io_pathway_scores(
    expression_data: pd.DataFrame,
    pathway_genes: Dict[str, List[str]] = None
) -> Dict[str, float]:
    """
    Compute IO pathway scores from expression data.
    
    Args:
        expression_data: DataFrame with genes as index, samples as columns
                        Expression values should be TPM or normalized counts
        pathway_genes: Dictionary mapping pathway names to gene lists
                       Defaults to IO_PATHWAYS
    
    Returns:
        Dictionary mapping pathway names to scores (mean log2(TPM+1))
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if pathway_genes is None:
        pathway_genes = IO_PATHWAYS
    
    pathway_scores = {}
    
    for pathway_name, gene_list in pathway_genes.items():
        # Find genes present in expression matrix
        available_genes = [g for g in gene_list if g in expression_data.index]
        
        if len(available_genes) == 0:
            logger.warning(f"⚠️  No genes found for {pathway_name} in expression data")
            pathway_scores[pathway_name] = np.nan
            continue
        
        # Log2 transform (TPM data is usually NOT log-transformed)
        expr_subset = expression_data.loc[available_genes]
        expr_log = np.log2(expr_subset + 1)
        
        # Mean expression across genes (single sample or mean across samples)
        if expr_log.shape[1] == 1:
            # Single sample
            score = expr_log.mean(axis=0).iloc[0]
        else:
            # Multiple samples - take mean across samples
            score = expr_log.mean(axis=0).mean()
        
        pathway_scores[pathway_name] = float(score)
        
        coverage = len(available_genes) / len(gene_list) * 100
        logger.debug(f"✓ {pathway_name}: {len(available_genes)}/{len(gene_list)} genes ({coverage:.1f}%)")
    
    return pathway_scores


def logistic_regression_composite(
    pathway_scores: Dict[str, float],
    coefficients: Dict[str, float] = None,
    intercept: float = None
) -> float:
    """
    Compute logistic regression composite score for IO response prediction.
    
    Uses UNSTANDARDIZED coefficients (for direct application to raw pathway scores).
    
    Args:
        pathway_scores: Dictionary mapping pathway names to scores
        coefficients: Dictionary mapping pathway names to LR coefficients
                     Defaults to IO_LR_COEFFICIENTS (unstandardized)
        intercept: Logistic regression intercept
                  Defaults to IO_LR_INTERCEPT (unstandardized)
    
    Returns:
        Composite score (0-1 probability of IO response)
    """
    if coefficients is None:
        coefficients = IO_LR_COEFFICIENTS
    
    if intercept is None:
        intercept = IO_LR_INTERCEPT
    
    # Compute linear combination (unstandardized)
    linear_score = intercept
    
    for pathway_name, coefficient in coefficients.items():
        if pathway_name in pathway_scores:
            score = pathway_scores[pathway_name]
            if not np.isnan(score):
                linear_score += coefficient * score
    
    # Apply sigmoid to get probability
    # sigmoid(x) = 1 / (1 + exp(-x))
    composite_prob = 1.0 / (1.0 + np.exp(-linear_score))
    
    return float(composite_prob)
