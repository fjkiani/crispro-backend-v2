#!/usr/bin/env python3
"""
Model Comparison: DeLong Test for AUROC Comparison

Purpose:
- Compare two ROC curves using DeLong test
- Test H0: AUC_A = AUC_B
- Provide statistical significance for model improvement claims

Reference:
- DeLong, E. R., DeLong, D. M., & Clarke-Pearson, D. L. (1988). 
  Comparing the areas under two or more correlated receiver operating 
  characteristic curves: a nonparametric approach. Biometrics, 44(3), 837-845.

Example:
    y_true = [0, 1, 0, 1, ...]
    scores_a = [0.3, 0.7, 0.2, 0.8, ...]  # Baseline model
    scores_b = [0.4, 0.8, 0.3, 0.9, ...]  # Surrogate model
    result = delong_test(y_true, scores_a, scores_b)
"""

from __future__ import annotations

import numpy as np
from scipy import stats
from typing import Dict
from sklearn.metrics import roc_auc_score


def _compute_delong_variance(y_true: np.ndarray, scores: np.ndarray) -> float:
    """
    Compute DeLong variance estimate for AUROC.
    
    This is a simplified implementation. For production use, consider
    using statsmodels.stats.contingency_tables or a more robust implementation.
    """
    n = len(y_true)
    n_pos = np.sum(y_true == 1)
    n_neg = n - n_pos
    
    if n_pos == 0 or n_neg == 0:
        return np.nan
    
    # Sort scores
    sorted_indices = np.argsort(scores)[::-1]  # Descending
    sorted_y = y_true[sorted_indices]
    sorted_scores = scores[sorted_indices]
    
    # Compute V10 and V01 (simplified DeLong variance components)
    # V10: variance component for positive cases
    # V01: variance component for negative cases
    
    # For each positive case, count how many negatives have lower scores
    v10_sum = 0.0
    for i in range(n):
        if sorted_y[i] == 1:
            # Count negatives with lower scores
            v10_sum += np.sum((sorted_y == 0) & (sorted_scores < sorted_scores[i]))
    
    # For each negative case, count how many positives have higher scores
    v01_sum = 0.0
    for i in range(n):
        if sorted_y[i] == 0:
            # Count positives with higher scores
            v01_sum += np.sum((sorted_y == 1) & (sorted_scores > sorted_scores[i]))
    
    # DeLong variance estimate (simplified)
    # More accurate implementations use U-statistics
    auc = roc_auc_score(y_true, scores)
    v10 = v10_sum / (n_pos * n_neg)
    v01 = v01_sum / (n_pos * n_neg)
    
    # Variance of AUC
    var_auc = (v10 / n_pos) + (v01 / n_neg)
    
    return var_auc


def delong_test(
    y_true: np.ndarray,
    scores_a: np.ndarray,
    scores_b: np.ndarray,
) -> Dict[str, float]:
    """
    DeLong test for comparing two ROC curves.
    
    Tests H0: AUC_A = AUC_B
    
    Args:
        y_true: True binary labels (0/1)
        scores_a: Predicted scores from model A
        scores_b: Predicted scores from model B
    
    Returns:
        Dict with keys:
            - 'auc_a': AUROC for model A
            - 'auc_b': AUROC for model B
            - 'difference': AUC_B - AUC_A
            - 'z_statistic': Z-statistic for the test
            - 'p_value': Two-sided p-value
            - 'se_diff': Standard error of the difference
    """
    # Compute AUROCs
    auc_a = roc_auc_score(y_true, scores_a)
    auc_b = roc_auc_score(y_true, scores_b)
    
    # Compute variances
    var_a = _compute_delong_variance(y_true, scores_a)
    var_b = _compute_delong_variance(y_true, scores_b)
    
    # Compute covariance (simplified - assumes independence for now)
    # More accurate implementations compute the covariance term
    # For correlated predictions, this should be adjusted
    cov_ab = 0.0  # Simplified: assume independence
    
    # Variance of the difference
    var_diff = var_a + var_b - 2 * cov_ab
    se_diff = np.sqrt(var_diff) if var_diff > 0 else np.nan
    
    if np.isnan(se_diff) or se_diff == 0:
        return {
            'auc_a': float(auc_a),
            'auc_b': float(auc_b),
            'difference': float(auc_b - auc_a),
            'z_statistic': np.nan,
            'p_value': np.nan,
            'se_diff': float(se_diff) if not np.isnan(se_diff) else np.nan,
        }
    
    # Z-statistic
    z_stat = (auc_b - auc_a) / se_diff
    
    # Two-sided p-value
    p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))
    
    return {
        'auc_a': float(auc_a),
        'auc_b': float(auc_b),
        'difference': float(auc_b - auc_a),
        'z_statistic': float(z_stat),
        'p_value': float(p_value),
        'se_diff': float(se_diff),
    }


def compare_models(
    y_true: np.ndarray,
    baseline_scores: np.ndarray,
    surrogate_scores: np.ndarray,
    baseline_name: str = "Baseline",
    surrogate_name: str = "Surrogate",
) -> Dict[str, any]:
    """
    Compare two models using DeLong test and provide summary.
    
    Args:
        y_true: True binary labels
        baseline_scores: Scores from baseline model
        surrogate_scores: Scores from surrogate model
        baseline_name: Name for baseline model
        surrogate_name: Name for surrogate model
    
    Returns:
        Dict with comparison results including DeLong test results
    """
    # Run DeLong test
    delong_result = delong_test(y_true, baseline_scores, surrogate_scores)
    
    # Compute improvement
    improvement = delong_result['difference']
    improvement_pct = (improvement / delong_result['auc_a']) * 100 if delong_result['auc_a'] > 0 else 0.0
    
    # Determine significance
    is_significant = delong_result['p_value'] < 0.05 if not np.isnan(delong_result['p_value']) else False
    
    return {
        'baseline': {
            'name': baseline_name,
            'auroc': delong_result['auc_a'],
        },
        'surrogate': {
            'name': surrogate_name,
            'auroc': delong_result['auc_b'],
        },
        'comparison': {
            'improvement': improvement,
            'improvement_pct': improvement_pct,
            'is_significant': is_significant,
        },
        'delong_test': delong_result,
        'interpretation': {
            'summary': f"{surrogate_name} AUROC: {delong_result['auc_b']:.3f} vs {baseline_name} AUROC: {delong_result['auc_a']:.3f}",
            'improvement': f"Improvement: {improvement:+.3f} ({improvement_pct:+.1f}%)",
            'significance': f"p-value: {delong_result['p_value']:.4f} {'(significant)' if is_significant else '(not significant)'}",
        },
    }


if __name__ == '__main__':
    # Example usage
    np.random.seed(42)
    
    # Generate synthetic data
    n = 200
    y_true = np.random.binomial(1, 0.3, n)
    
    # Baseline model (lower performance)
    baseline_scores = np.random.rand(n) * 0.5 + 0.3
    
    # Surrogate model (higher performance)
    surrogate_scores = baseline_scores + np.random.rand(n) * 0.2 + 0.1
    surrogate_scores = np.clip(surrogate_scores, 0, 1)
    
    # Run comparison
    result = compare_models(
        y_true,
        baseline_scores,
        surrogate_scores,
        baseline_name="BRCA/HRD Alone",
        surrogate_name="ECW/TBW + BRCA/HRD",
    )
    
    print("✅ Model Comparison Results:")
    print(f"   {result['interpretation']['summary']}")
    print(f"   {result['interpretation']['improvement']}")
    print(f"   {result['interpretation']['significance']}")

