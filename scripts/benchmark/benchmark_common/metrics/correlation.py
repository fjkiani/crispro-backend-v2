"""
Correlation Metrics Module

Compute correlation between predicted efficacy scores and actual outcomes (PFS, OS).
"""

import numpy as np
from scipy import stats
from typing import List, Dict, Any


def compute_correlation_metrics(
    predictions: List[Dict[str, Any]],
    patients: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute correlation metrics between predictions and outcomes.
    
    Args:
        predictions: List of prediction results (may include errors)
        patients: List of patient dicts with clinical_outcomes
    
    Returns:
        Dict with pfs_correlation and os_correlation metrics
    """
    print(f"\n📊 Computing correlation metrics...")
    
    # Create patient lookup
    patient_lookup = {p.get("patient_id"): p for p in patients}
    
    # Extract data for correlation
    pfs_scores = []
    pfs_months = []
    os_scores = []
    os_months = []
    
    for pred in predictions:
        if "error" in pred:
            continue
        
        patient_id = pred.get("patient_id")
        patient = patient_lookup.get(patient_id)
        
        if not patient:
            continue
        
        outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
        # Handle both top_drug dict and direct efficacy_score
        if isinstance(pred.get("top_drug"), dict):
            efficacy_score = pred.get("top_drug", {}).get("efficacy_score", 0.0)
        else:
            efficacy_score = pred.get("efficacy_score", 0.0)
        
        # PFS data
        pfs_months_val = outcomes.get("PFS_MONTHS")
        if pfs_months_val is not None:
            try:
                pfs_months.append(float(pfs_months_val))
                pfs_scores.append(efficacy_score)
            except (ValueError, TypeError):
                pass
        
        # OS data
        os_months_val = outcomes.get("OS_MONTHS")
        if os_months_val is not None:
            try:
                os_months.append(float(os_months_val))
                os_scores.append(efficacy_score)
            except (ValueError, TypeError):
                pass
    
    metrics = {}
    
    # PFS Correlation (filter NaN/Inf)
    if len(pfs_scores) >= 10:
        pfs_valid_mask = ~(np.isnan(pfs_scores) | np.isinf(pfs_scores) | np.isnan(pfs_months) | np.isinf(pfs_months))
        pfs_scores_clean = np.array(pfs_scores)[pfs_valid_mask]
        pfs_months_clean = np.array(pfs_months)[pfs_valid_mask]
        print(f"   Filtered: {len(pfs_scores_clean)}/{len(pfs_scores)} valid PFS pairs")
        
        if len(pfs_scores_clean) >= 10:
            pfs_pearson = stats.pearsonr(pfs_scores_clean, pfs_months_clean)
            pfs_spearman = stats.spearmanr(pfs_scores_clean, pfs_months_clean)
            metrics["pfs_correlation"] = {
                "pearson_r": float(pfs_pearson[0]),
                "pearson_p_value": float(pfs_pearson[1]),
                "spearman_rho": float(pfs_spearman[0]),
                "spearman_p_value": float(pfs_spearman[1]),
                "n_patients": len(pfs_scores_clean),
                "filtered_out": len(pfs_scores) - len(pfs_scores_clean)
            }
            print(f"   ✅ PFS Correlation: r={pfs_pearson[0]:.3f}, p={pfs_pearson[1]:.4f} (n={len(pfs_scores_clean)})")
        else:
            metrics["pfs_correlation"] = {"error": "Insufficient valid data after filtering", "n_patients": len(pfs_scores_clean)}
            print(f"   ⚠️  PFS Correlation: Insufficient data after filtering (n={len(pfs_scores_clean)})")
    else:
        metrics["pfs_correlation"] = {"error": "Insufficient data", "n_patients": len(pfs_scores)}
        print(f"   ⚠️  PFS Correlation: Insufficient data (n={len(pfs_scores)})")
    
    # OS Correlation (filter NaN/Inf)
    if len(os_scores) >= 10:
        os_valid_mask = ~(np.isnan(os_scores) | np.isinf(os_scores) | np.isnan(os_months) | np.isinf(os_months))
        os_scores_clean = np.array(os_scores)[os_valid_mask]
        os_months_clean = np.array(os_months)[os_valid_mask]
        print(f"   Filtered: {len(os_scores_clean)}/{len(os_scores)} valid OS pairs")
        
        if len(os_scores_clean) >= 10:
            os_pearson = stats.pearsonr(os_scores_clean, os_months_clean)
            os_spearman = stats.spearmanr(os_scores_clean, os_months_clean)
            metrics["os_correlation"] = {
                "pearson_r": float(os_pearson[0]),
                "pearson_p_value": float(os_pearson[1]),
                "spearman_rho": float(os_spearman[0]),
                "spearman_p_value": float(os_spearman[1]),
                "n_patients": len(os_scores_clean),
                "filtered_out": len(os_scores) - len(os_scores_clean)
            }
            print(f"   ✅ OS Correlation: r={os_pearson[0]:.3f}, p={os_pearson[1]:.4f} (n={len(os_scores_clean)})")
        else:
            metrics["os_correlation"] = {"error": "Insufficient valid data after filtering", "n_patients": len(os_scores_clean)}
            print(f"   ⚠️  OS Correlation: Insufficient data after filtering (n={len(os_scores_clean)})")
    else:
        metrics["os_correlation"] = {"error": "Insufficient data", "n_patients": len(os_scores)}
        print(f"   ⚠️  OS Correlation: Insufficient data (n={len(os_scores)})")
    
    return metrics


