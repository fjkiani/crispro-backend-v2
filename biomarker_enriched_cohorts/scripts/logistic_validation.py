#!/usr/bin/env python3
"""
Logistic Regression Validation with Cross-Validation and Bootstrap CIs

Purpose:
- Fit logistic regression models with cross-validation
- Compute AUROC with bootstrap confidence intervals
- Support binary classification tasks (e.g., platinum resistance prediction)

Example:
    X = features (numpy array or DataFrame)
    y = binary labels (0/1)
    result = logistic_auroc_cv(X, y, cv=5)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Optional, Union
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.metrics import roc_auc_score, roc_curve, precision_score, recall_score, confusion_matrix


def bootstrap_auroc_ci(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    n_boot: int = 1000,
    seed: int = 7,
    confidence_level: float = 0.95,
) -> Dict[str, float]:
    """
    Compute bootstrap confidence intervals for AUROC.
    
    Uses stratified bootstrap to avoid degenerate resamples.
    
    Args:
        y_true: True binary labels (0/1)
        y_pred_proba: Predicted probabilities
        n_boot: Number of bootstrap iterations
        seed: Random seed
        confidence_level: Confidence level (default: 0.95 for 95% CI)
    
    Returns:
        Dict with keys: 'mean', 'p025', 'p50', 'p975' (or adjusted for confidence_level)
    """
    np.random.seed(seed)
    
    n = len(y_true)
    alpha = 1 - confidence_level
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100
    
    # Stratified bootstrap: sample within each class
    bootstrapped_aurocs = []
    
    for _ in range(n_boot):
        # Sample indices within each class
        pos_indices = np.where(y_true == 1)[0]
        neg_indices = np.where(y_true == 0)[0]
        
        if len(pos_indices) == 0 or len(neg_indices) == 0:
            continue
        
        # Bootstrap sample within each class
        pos_boot = np.random.choice(pos_indices, size=len(pos_indices), replace=True)
        neg_boot = np.random.choice(neg_indices, size=len(neg_indices), replace=True)
        
        # Combine
        boot_indices = np.concatenate([pos_boot, neg_boot])
        boot_y_true = y_true[boot_indices]
        boot_y_pred = y_pred_proba[boot_indices]
        
        # Compute AUROC
        try:
            auroc = roc_auc_score(boot_y_true, boot_y_pred)
            bootstrapped_aurocs.append(auroc)
        except ValueError:
            # Skip if degenerate (all same class)
            continue
    
    if not bootstrapped_aurocs:
        return {
            'mean': np.nan,
            'p025': np.nan,
            'p50': np.nan,
            'p975': np.nan,
        }
    
    bootstrapped_aurocs = np.array(bootstrapped_aurocs)
    
    return {
        'mean': float(np.mean(bootstrapped_aurocs)),
        'p025': float(np.percentile(bootstrapped_aurocs, lower_percentile)),
        'p50': float(np.median(bootstrapped_aurocs)),
        'p975': float(np.percentile(bootstrapped_aurocs, upper_percentile)),
    }


def logistic_auroc_cv(
    X: Union[np.ndarray, pd.DataFrame],
    y: np.ndarray,
    cv: int = 5,
    random_state: int = 42,
    max_iter: int = 1000,
    n_bootstrap: int = 1000,
) -> Dict[str, Union[float, Dict[str, float]]]:
    """
    Cross-validated AUROC for logistic regression with bootstrap CIs.
    
    Args:
        X: Feature matrix (n_samples, n_features)
        y: Binary labels (0/1)
        cv: Number of CV folds
        random_state: Random seed
        max_iter: Maximum iterations for logistic regression
        n_bootstrap: Number of bootstrap iterations for CI
    
    Returns:
        Dict with keys:
            - 'auroc': Mean AUROC
            - 'ci_lower': Lower bound of 95% CI
            - 'ci_upper': Upper bound of 95% CI
            - 'ci_details': Full bootstrap CI details
            - 'sensitivity': Sensitivity at optimal threshold
            - 'specificity': Specificity at optimal threshold
            - 'ppv': Positive predictive value
            - 'npv': Negative predictive value
    """
    # Convert to numpy if needed
    if isinstance(X, pd.DataFrame):
        X = X.values
    if isinstance(y, pd.Series):
        y = y.values
    
    # Fit model with cross-validation
    model = LogisticRegression(max_iter=max_iter, random_state=random_state)
    cv_splitter = StratifiedKFold(n_splits=cv, shuffle=True, random_state=random_state)
    
    # Get cross-validated probability predictions
    y_pred_proba = cross_val_predict(
        model, X, y, cv=cv_splitter, method='predict_proba'
    )[:, 1]
    
    # Compute AUROC
    auroc = roc_auc_score(y, y_pred_proba)
    
    # Bootstrap CI
    ci_details = bootstrap_auroc_ci(y, y_pred_proba, n_boot=n_bootstrap)
    
    # Find optimal threshold (Youden's J: sensitivity + specificity - 1)
    fpr, tpr, thresholds = roc_curve(y, y_pred_proba)
    j_scores = tpr - fpr
    optimal_idx = np.argmax(j_scores)
    optimal_threshold = thresholds[optimal_idx]
    
    # Compute metrics at optimal threshold
    y_pred = (y_pred_proba >= optimal_threshold).astype(int)
    
    tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()
    
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    ppv = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0
    
    return {
        'auroc': float(auroc),
        'ci_lower': ci_details['p025'],
        'ci_upper': ci_details['p975'],
        'ci_details': ci_details,
        'sensitivity': float(sensitivity),
        'specificity': float(specificity),
        'ppv': float(ppv),
        'npv': float(npv),
        'optimal_threshold': float(optimal_threshold),
        'roc_curve': {
            'fpr': fpr.tolist(),
            'tpr': tpr.tolist(),
            'thresholds': thresholds.tolist(),
        },
    }


if __name__ == '__main__':
    # Example usage
    from sklearn.datasets import make_classification
    
    # Generate synthetic data
    X, y = make_classification(
        n_samples=200,
        n_features=5,
        n_informative=3,
        n_redundant=1,
        n_classes=2,
        random_state=42,
    )
    
    # Run validation
    result = logistic_auroc_cv(X, y, cv=5)
    
    print("✅ Logistic Regression CV Results:")
    print(f"   AUROC: {result['auroc']:.3f} ({result['ci_lower']:.3f}-{result['ci_upper']:.3f})")
    print(f"   Sensitivity: {result['sensitivity']:.3f}")
    print(f"   Specificity: {result['specificity']:.3f}")
    print(f"   PPV: {result['ppv']:.3f}")
    print(f"   NPV: {result['npv']:.3f}")

