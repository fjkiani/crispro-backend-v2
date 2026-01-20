#!/usr/bin/env python3
"""
Statistical analysis for synthetic lethality benchmark results.

Calculates:
- Bootstrap confidence intervals for AUROC
- Fisher's exact test for drug recommendation accuracy
- Sensitivity, specificity, PPV, NPV
"""
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple
from scipy import stats
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score

def bootstrap_ci(y_true: List[int], scores: List[float], n_bootstrap: int = 1000) -> Tuple[float, float]:
    """Bootstrap 95% CI for AUROC."""
    np.random.seed(42)
    aucs = []
    n = len(y_true)
    
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        y_boot = [y_true[i] for i in idx]
        s_boot = [scores[i] for i in idx]
        
        if sum(y_boot) > 0 and sum(y_boot) < len(y_boot):
            try:
                aucs.append(roc_auc_score(y_boot, s_boot))
            except:
                continue
    
    if not aucs:
        return 0.0, 0.0
    
    lower = np.percentile(aucs, 2.5)
    upper = np.percentile(aucs, 97.5)
    return float(lower), float(upper)

def fishers_exact_test(tp: int, fp: int, fn: int, tn: int) -> Dict[str, float]:
    """Fisher's exact test for 2x2 contingency table."""
    contingency = [[tp, fp], [fn, tn]]
    oddsratio, p_value = stats.fisher_exact(contingency)
    return {
        "odds_ratio": float(oddsratio),
        "p_value": float(p_value),
        "contingency_table": contingency
    }

def calculate_metrics(y_true: List[int], y_pred: List[int], scores: List[float]) -> Dict[str, Any]:
    """Calculate comprehensive metrics."""
    # Binary classification metrics
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    
    # Confusion matrix
    tp = sum(1 for i in range(len(y_true)) if y_true[i] == 1 and y_pred[i] == 1)
    fp = sum(1 for i in range(len(y_true)) if y_true[i] == 0 and y_pred[i] == 1)
    fn = sum(1 for i in range(len(y_true)) if y_true[i] == 1 and y_pred[i] == 0)
    tn = sum(1 for i in range(len(y_true)) if y_true[i] == 0 and y_pred[i] == 0)
    
    # Sensitivity, specificity, PPV, NPV
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    ppv = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0
    
    # AUROC
    try:
        auroc = roc_auc_score(y_true, scores)
        ci_lower, ci_upper = bootstrap_ci(y_true, scores)
    except:
        auroc = 0.0
        ci_lower, ci_upper = 0.0, 0.0
    
    # Fisher's exact test
    fisher = fishers_exact_test(tp, fp, fn, tn)
    
    return {
        "auroc": float(auroc),
        "auroc_ci_95": [ci_lower, ci_upper],
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "sensitivity": float(sensitivity),
        "specificity": float(specificity),
        "ppv": float(ppv),
        "npv": float(npv),
        "confusion_matrix": {
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "tn": int(tn)
        },
        "fishers_exact": fisher
    }

def analyze_benchmark_results(results_file: str = "results/benchmark_100_cached.json") -> Dict[str, Any]:
    """Analyze benchmark results with statistical tests."""
    print(f"Analyzing results from {results_file}...")
    
    if not Path(results_file).exists():
        print(f"❌ Results file not found: {results_file}")
        print("   Run benchmark first or use cached results")
        return {}
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    # Extract predictions and ground truth
    y_true = []
    y_pred = []
    scores = []
    
    for case in results.get("predictions", []):
        gt = case.get("ground_truth", {})
        pred = case.get("prediction", {})
        
        # Ground truth: SL detected (1) or not (0)
        sl_detected = 1 if gt.get("synthetic_lethality_detected", False) else 0
        y_true.append(sl_detected)
        
        # Prediction: Top drug recommended (1) or not (0)
        # For now, use confidence score > 0.5 as prediction
        confidence = pred.get("confidence", 0.0)
        scores.append(confidence)
        y_pred.append(1 if confidence > 0.5 else 0)
    
    if not y_true:
        print("❌ No predictions found in results")
        return {}
    
    # Calculate metrics
    metrics = calculate_metrics(y_true, y_pred, scores)
    
    # Print results
    print("=" * 60)
    print("Statistical Analysis Results")
    print("=" * 60)
    print(f"AUROC: {metrics['auroc']:.3f} (95% CI: {metrics['auroc_ci_95'][0]:.3f} - {metrics['auroc_ci_95'][1]:.3f})")
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall: {metrics['recall']:.3f}")
    print(f"F1 Score: {metrics['f1_score']:.3f}")
    print(f"Sensitivity: {metrics['sensitivity']:.3f}")
    print(f"Specificity: {metrics['specificity']:.3f}")
    print(f"PPV: {metrics['ppv']:.3f}")
    print(f"NPV: {metrics['npv']:.3f}")
    print(f"\nFisher's Exact Test:")
    print(f"  Odds Ratio: {metrics['fishers_exact']['odds_ratio']:.3f}")
    print(f"  p-value: {metrics['fishers_exact']['p_value']:.4f}")
    
    # Save results
    output_file = Path("results/statistical_analysis.json")
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    print(f"\n✅ Statistical analysis saved to {output_file}")
    
    return metrics

if __name__ == "__main__":
    import sys
    results_file = sys.argv[1] if len(sys.argv) > 1 else "results/benchmark_100_cached.json"
    analyze_benchmark_results(results_file)







