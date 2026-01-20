#!/usr/bin/env python3
"""Generate Figure 2: ROC Curves for Publication

Creates ROC curves comparing:
- TRUE SAE (29 features) - AUROC 0.783
- PROXY SAE (DDR gene count) - AUROC 0.628
- Individual diamond features

Run:
  python scripts/publication/generate_roc_curves.py
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
except ImportError:
    print("matplotlib not installed. Run: pip install matplotlib")
    exit(1)

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import roc_curve, auc
except ImportError:
    print("scikit-learn not installed. Run: pip install scikit-learn")
    exit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]

TIER3_PATH = REPO_ROOT / "data/validation/sae_cohort/checkpoints/Tier3_validation_cohort.json"
BASELINE_PATH = REPO_ROOT / "data/validation/sae_cohort/checkpoints/true_sae_diamonds_baseline.v1.json"
MAPPING_PATH = REPO_ROOT / "api/resources/sae_feature_mapping.true_sae_diamonds.v1.json"

DDR_GENES = {
    'BRCA1', 'BRCA2', 'ATM', 'ATR', 'CHEK1', 'CHEK2', 'RAD51', 'PALB2',
    'MBD4', 'MLH1', 'MSH2', 'MSH6', 'PMS2', 'TP53', 'RAD50', 'NBN',
    'FANCA', 'FANCD2', 'BLM', 'WRN', 'RECQL4', 'PARP1', 'PARP2'
}


def load_data():
    tier3 = json.loads(TIER3_PATH.read_text())
    baseline = json.loads(BASELINE_PATH.read_text())
    mapping = json.loads(MAPPING_PATH.read_text())
    return tier3, baseline, mapping


def prepare_features(patients, feature_list):
    y = []
    X_proxy = []
    X_true = []
    
    for pid, pdata in patients.items():
        outcome = pdata.get("outcome")
        if outcome not in ("sensitive", "resistant", "refractory"):
            continue
        
        y.append(1 if outcome in ("resistant", "refractory") else 0)
        
        # PROXY: DDR gene count
        genes = set()
        for variant in pdata.get("variants", []):
            gene = variant.get("gene", "").upper()
            if gene:
                genes.add(gene)
        ddr_count = len(genes & DDR_GENES)
        X_proxy.append([ddr_count])
        
        # TRUE SAE
        feature_sums = {fidx: 0.0 for fidx in feature_list}
        for variant in pdata.get("variants", []):
            for tf in variant.get("top_features", []):
                fidx = tf.get("index")
                if fidx in feature_sums:
                    feature_sums[fidx] += float(tf.get("value", 0.0) or 0.0)
        X_true.append([feature_sums[fidx] for fidx in feature_list])
    
    return np.array(X_proxy), np.array(X_true), np.array(y)


def compute_roc_cv(X, y, n_splits=5):
    """Compute ROC curves for each CV fold and mean."""
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    
    tprs = []
    aucs = []
    mean_fpr = np.linspace(0, 1, 100)
    
    for train_idx, test_idx in cv.split(X, y):
        model = LogisticRegression(max_iter=3000, class_weight="balanced", random_state=42)
        model.fit(X[train_idx], y[train_idx])
        prob = model.predict_proba(X[test_idx])[:, 1]
        
        fpr, tpr, _ = roc_curve(y[test_idx], prob)
        roc_auc = auc(fpr, tpr)
        aucs.append(roc_auc)
        
        tpr_interp = np.interp(mean_fpr, fpr, tpr)
        tpr_interp[0] = 0.0
        tprs.append(tpr_interp)
    
    mean_tpr = np.mean(tprs, axis=0)
    mean_tpr[-1] = 1.0
    mean_auc = np.mean(aucs)
    std_auc = np.std(aucs)
    
    std_tpr = np.std(tprs, axis=0)
    tprs_upper = np.minimum(mean_tpr + std_tpr, 1)
    tprs_lower = np.maximum(mean_tpr - std_tpr, 0)
    
    return mean_fpr, mean_tpr, tprs_lower, tprs_upper, mean_auc, std_auc


def main():
    print("Loading data...")
    tier3, baseline, mapping = load_data()
    patients = tier3.get("data", {})
    feature_list = baseline["features"]["feature_list"]
    
    print("Preparing features...")
    X_proxy, X_true, y = prepare_features(patients, feature_list)
    
    print(f"Cohort: {len(y)} patients ({sum(y)} resistant, {len(y) - sum(y)} sensitive)")
    
    # Compute ROC curves
    print("Computing ROC curves...")
    fpr_proxy, tpr_proxy, tpr_proxy_lower, tpr_proxy_upper, auc_proxy, std_proxy = compute_roc_cv(X_proxy, y)
    fpr_true, tpr_true, tpr_true_lower, tpr_true_upper, auc_true, std_true = compute_roc_cv(X_true, y)
    
    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=(8, 8))
    
    # Random baseline
    ax.plot([0, 1], [0, 1], linestyle='--', lw=2, color='gray', label='Random (AUC = 0.50)', alpha=0.8)
    
    # PROXY SAE
    ax.plot(fpr_proxy, tpr_proxy, color='#E74C3C', lw=2.5,
            label=f'PROXY SAE (AUC = {auc_proxy:.3f} ± {std_proxy:.3f})')
    ax.fill_between(fpr_proxy, tpr_proxy_lower, tpr_proxy_upper, color='#E74C3C', alpha=0.2)
    
    # TRUE SAE
    ax.plot(fpr_true, tpr_true, color='#2ECC71', lw=2.5,
            label=f'TRUE SAE (AUC = {auc_true:.3f} ± {std_true:.3f})')
    ax.fill_between(fpr_true, tpr_true_lower, tpr_true_upper, color='#2ECC71', alpha=0.2)
    
    ax.set_xlim([-0.05, 1.05])
    ax.set_ylim([-0.05, 1.05])
    ax.set_xlabel('False Positive Rate', fontsize=14)
    ax.set_ylabel('True Positive Rate', fontsize=14)
    ax.set_title('ROC Curves: TRUE SAE vs PROXY SAE\n(Platinum Resistance Prediction, TCGA-OV)', fontsize=16)
    ax.legend(loc='lower right', fontsize=12)
    ax.grid(True, alpha=0.3)
    
    # Add delta annotation
    delta = auc_true - auc_proxy
    ax.annotate(f'ΔAUC = +{delta:.3f}', xy=(0.5, 0.3), fontsize=14, 
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # Save figure
    output_dir = REPO_ROOT / "publication" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "figure2_roc_curves.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved: {output_path}")
    
    # Also save as PDF
    output_path_pdf = output_dir / "figure2_roc_curves.pdf"
    plt.savefig(output_path_pdf, format='pdf', bbox_inches='tight')
    print(f"Saved: {output_path_pdf}")
    
    plt.close()
    
    print()
    print("=" * 60)
    print("FIGURE 2 GENERATED")
    print("=" * 60)
    print(f"PROXY SAE: AUROC = {auc_proxy:.3f} ± {std_proxy:.3f}")
    print(f"TRUE SAE: AUROC = {auc_true:.3f} ± {std_true:.3f}")
    print(f"DELTA: +{delta:.3f}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
