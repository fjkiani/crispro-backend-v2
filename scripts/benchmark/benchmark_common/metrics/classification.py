"""
Classification Metrics Module

Compute classification metrics (AUC, sensitivity, specificity) for progression prediction.
"""

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve
from typing import List, Dict, Any


def compute_classification_metrics(
    predictions: List[Dict[str, Any]],
    patients: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute classification metrics (AUC for progression prediction).
    
    Args:
        predictions: List of prediction results (may include errors)
        patients: List of patient dicts with clinical_outcomes
    
    Returns:
        Dict with roc_auc, pr_auc, sensitivity, specificity, etc.
    """
    print(f"\n📊 Computing classification metrics...")
    
    # Create patient lookup
    patient_lookup = {p.get("patient_id"): p for p in patients}
    
    response_labels = []
    response_scores = []
    
    for pred in predictions:
        if "error" in pred:
            continue
        
        patient_id = pred.get("patient_id")
        patient = patient_lookup.get(patient_id)
        
        if not patient:
            continue
        
        # Handle both top_drug dict and direct efficacy_score
        if isinstance(pred.get("top_drug"), dict):
            efficacy_score = pred.get("top_drug", {}).get("efficacy_score", 0.0)
        else:
            efficacy_score = pred.get("efficacy_score", 0.0)
        
        outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
        pfs_status = outcomes.get("PFS_STATUS", "")
        
        # Use parser to handle all formats
        from benchmark_common.utils.pfs_status_parser import parse_pfs_status
        event, status = parse_pfs_status(pfs_status)
        
        if event is not None:
            # event=0 means censored (good, no progression)
            # event=1 means progressed (poor, progression occurred)
            # For classification: 1 = good (no progression), 0 = poor (progression)
            response_labels.append(1 - event)  # Invert: 0→1 (good), 1→0 (poor)
            response_scores.append(efficacy_score)
    
    if len(response_labels) >= 20 and len(set(response_labels)) >= 2:
        try:
            roc_auc = roc_auc_score(response_labels, response_scores)
            pr_auc = average_precision_score(response_labels, response_scores)
            
            # Compute optimal threshold
            fpr, tpr, thresholds = roc_curve(response_labels, response_scores)
            optimal_idx = np.argmax(tpr - fpr)
            optimal_threshold = thresholds[optimal_idx]
            
            # Compute sensitivity and specificity at optimal threshold
            predictions_binary = (np.array(response_scores) >= optimal_threshold).astype(int)
            tp = np.sum((predictions_binary == 1) & (np.array(response_labels) == 1))
            tn = np.sum((predictions_binary == 0) & (np.array(response_labels) == 0))
            fp = np.sum((predictions_binary == 1) & (np.array(response_labels) == 0))
            fn = np.sum((predictions_binary == 0) & (np.array(response_labels) == 1))
            
            sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            
            metrics = {
                "roc_auc": float(roc_auc),
                "pr_auc": float(pr_auc),
                "sensitivity": float(sensitivity),
                "specificity": float(specificity),
                "optimal_threshold": float(optimal_threshold),
                "n_patients": len(response_scores),
                "n_events": sum(1 for l in response_labels if l == 0),  # Progressions
                "n_censored": sum(1 for l in response_labels if l == 1)  # Censored (good)
            }
            print(f"   ✅ Response Classification: AUC={roc_auc:.3f}, Sens={sensitivity:.3f}, Spec={specificity:.3f} (n={len(response_scores)})")
            return metrics
        except Exception as e:
            error_msg = {"error": str(e), "n_patients": len(response_scores)}
            print(f"   ⚠️  Response Classification: Error - {e}")
            return error_msg
    else:
        error_msg = {"error": "Insufficient data", "n_patients": len(response_scores)}
        print(f"   ⚠️  Response Classification: Insufficient data (n={len(response_scores)})")
        return error_msg


