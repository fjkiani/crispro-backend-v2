#!/usr/bin/env python3
"""Head-to-Head Comparison: PROXY SAE vs TRUE SAE

This is the CRITICAL analysis for the publication.
Compares gene-level (PROXY) vs feature-level (TRUE SAE) on the SAME 149 patients.

Run:
  python scripts/publication/head_to_head_proxy_vs_true.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]

TIER3_PATH = REPO_ROOT / "data/validation/sae_cohort/checkpoints/Tier3_validation_cohort.json"
MAPPING_PATH = REPO_ROOT / "api/resources/sae_feature_mapping.true_sae_diamonds.v1.json"
BASELINE_PATH = REPO_ROOT / "data/validation/sae_cohort/checkpoints/true_sae_diamonds_baseline.v1.json"

# DDR genes for PROXY SAE
DDR_GENES = {
    'BRCA1', 'BRCA2', 'ATM', 'ATR', 'CHEK1', 'CHEK2', 'RAD51', 'PALB2',
    'MBD4', 'MLH1', 'MSH2', 'MSH6', 'PMS2', 'TP53', 'RAD50', 'NBN',
    'FANCA', 'FANCD2', 'BLM', 'WRN', 'RECQL4', 'PARP1', 'PARP2'
}


def auc_roc(y_true, scores):
    """AUROC via Mann-Whitney U (handles ties)."""
    pairs = list(zip(scores, y_true))
    pairs.sort(key=lambda x: x[0])

    n_pos = sum(y_true)
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5

    ranks = [0.0] * len(pairs)
    i = 0
    r = 1
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (r + (r + (j - i) - 1)) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        r += (j - i)
        i = j

    sum_ranks_pos = sum(rank for rank, (_, y) in zip(ranks, pairs) if y == 1)
    u = sum_ranks_pos - (n_pos * (n_pos + 1) / 2.0)
    return float(u / (n_pos * n_neg))


def compute_proxy_score(patient_data):
    """Compute PROXY SAE score (DDR gene count) for a patient."""
    genes = set()
    for variant in patient_data.get("variants", []):
        gene = variant.get("gene", "").upper()
        if gene:
            genes.add(gene)
    
    ddr_count = len(genes & DDR_GENES)
    return min(1.0, ddr_count / 3.0)


def compute_true_sae_score(patient_data, feature_list):
    """Compute TRUE SAE score (sum of feature values) for a patient."""
    feature_sums = {fidx: 0.0 for fidx in feature_list}
    
    for variant in patient_data.get("variants", []):
        for tf in variant.get("top_features", []):
            fidx = tf.get("index")
            if fidx in feature_sums:
                feature_sums[fidx] += float(tf.get("value", 0.0) or 0.0)
    
    return sum(feature_sums.values())


def bootstrap_ci(y_true, scores, n_bootstrap=1000, alpha=0.05):
    """Bootstrap 95% CI for AUROC."""
    np.random.seed(42)
    aucs = []
    n = len(y_true)
    
    for _ in range(n_bootstrap):
        idx = np.random.choice(n, size=n, replace=True)
        y_boot = [y_true[i] for i in idx]
        s_boot = [scores[i] for i in idx]
        
        if sum(y_boot) > 0 and sum(y_boot) < len(y_boot):
            aucs.append(auc_roc(y_boot, s_boot))
    
    lower = np.percentile(aucs, alpha / 2 * 100)
    upper = np.percentile(aucs, (1 - alpha / 2) * 100)
    return float(lower), float(upper)


def main():
    print("=" * 80)
    print("HEAD-TO-HEAD COMPARISON: PROXY SAE vs TRUE SAE")
    print("=" * 80)
    print()
    
    # Load data
    tier3 = json.loads(TIER3_PATH.read_text())
    mapping = json.loads(MAPPING_PATH.read_text())
    baseline = json.loads(BASELINE_PATH.read_text())
    
    patients = tier3.get("data", {})
    feature_list = baseline["features"]["feature_list"]
    
    # Prepare labels and scores
    patient_ids = []
    y_true = []
    proxy_scores = []
    true_scores = []
    
    for pid, pdata in patients.items():
        outcome = pdata.get("outcome")
        if outcome not in ("sensitive", "resistant", "refractory"):
            continue
        
        patient_ids.append(pid)
        y_true.append(1 if outcome in ("resistant", "refractory") else 0)
        proxy_scores.append(compute_proxy_score(pdata))
        true_scores.append(compute_true_sae_score(pdata, feature_list))
    
    # Basic stats
    n_total = len(y_true)
    n_pos = sum(y_true)
    n_neg = n_total - n_pos
    
    print(f"Cohort: {n_total} patients ({n_pos} resistant, {n_neg} sensitive)")
    print()
    
    # Compute AUROCs
    proxy_auroc = auc_roc(y_true, proxy_scores)
    true_auroc = auc_roc(y_true, true_scores)
    
    # Bootstrap CIs
    proxy_ci = bootstrap_ci(y_true, proxy_scores)
    true_ci = bootstrap_ci(y_true, true_scores)
    
    # Delta
    delta_auroc = true_auroc - proxy_auroc
    
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    print(f"PROXY SAE (DDR gene count):")
    print(f"  AUROC: {proxy_auroc:.3f}")
    print(f"  95% CI: [{proxy_ci[0]:.3f}, {proxy_ci[1]:.3f}]")
    print()
    print(f"TRUE SAE (29 features):")
    print(f"  AUROC: {true_auroc:.3f}")
    print(f"  95% CI: [{true_ci[0]:.3f}, {true_ci[1]:.3f}]")
    print()
    print(f"DELTA (TRUE - PROXY): {delta_auroc:+.3f}")
    print()
    
    # Interpretation
    print("=" * 80)
    print("INTERPRETATION")
    print("=" * 80)
    print()
    
    if delta_auroc > 0.05:
        interpretation = "TRUE SAE provides meaningful improvement over PROXY SAE"
    elif delta_auroc > 0:
        interpretation = "TRUE SAE provides marginal improvement over PROXY SAE"
    elif delta_auroc > -0.05:
        interpretation = "TRUE SAE performs comparably to PROXY SAE (no significant difference)"
    else:
        interpretation = "PROXY SAE outperforms TRUE SAE (unexpected)"
    
    print(f"  {interpretation}")
    print()
    
    # Additional analysis: Score distributions
    print("=" * 80)
    print("SCORE DISTRIBUTIONS")
    print("=" * 80)
    print()
    
    proxy_pos = [s for s, y in zip(proxy_scores, y_true) if y == 1]
    proxy_neg = [s for s, y in zip(proxy_scores, y_true) if y == 0]
    true_pos = [s for s, y in zip(true_scores, y_true) if y == 1]
    true_neg = [s for s, y in zip(true_scores, y_true) if y == 0]
    
    print(f"PROXY SAE:")
    print(f"  Resistant: mean={np.mean(proxy_pos):.3f}, std={np.std(proxy_pos):.3f}")
    print(f"  Sensitive: mean={np.mean(proxy_neg):.3f}, std={np.std(proxy_neg):.3f}")
    print()
    print(f"TRUE SAE:")
    print(f"  Resistant: mean={np.mean(true_pos):.3f}, std={np.std(true_pos):.3f}")
    print(f"  Sensitive: mean={np.mean(true_neg):.3f}, std={np.std(true_neg):.3f}")
    print()
    
    # Save results
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "cohort": {
            "total": n_total,
            "positive": n_pos,
            "negative": n_neg
        },
        "proxy_sae": {
            "method": "DDR_gene_count / 3.0",
            "auroc": proxy_auroc,
            "ci_95": list(proxy_ci),
            "score_resistant_mean": float(np.mean(proxy_pos)),
            "score_sensitive_mean": float(np.mean(proxy_neg))
        },
        "true_sae": {
            "method": "29_feature_sum",
            "auroc": true_auroc,
            "ci_95": list(true_ci),
            "score_resistant_mean": float(np.mean(true_pos)),
            "score_sensitive_mean": float(np.mean(true_neg))
        },
        "delta_auroc": delta_auroc,
        "interpretation": interpretation
    }
    
    output_dir = Path(__file__).resolve().parent / "results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"head_to_head_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(json.dumps(results, indent=2))
    
    print(f"Results saved to: {output_path}")
    print()
    
    # Table for publication
    print("=" * 80)
    print("TABLE 4: HEAD-TO-HEAD COMPARISON (For Publication)")
    print("=" * 80)
    print()
    print("| Method | AUROC | 95% CI | Resistant Mean | Sensitive Mean |")
    print("|--------|-------|--------|----------------|----------------|")
    print(f"| PROXY SAE | {proxy_auroc:.3f} | [{proxy_ci[0]:.3f}, {proxy_ci[1]:.3f}] | {np.mean(proxy_pos):.3f} | {np.mean(proxy_neg):.3f} |")
    print(f"| TRUE SAE | {true_auroc:.3f} | [{true_ci[0]:.3f}, {true_ci[1]:.3f}] | {np.mean(true_pos):.3f} | {np.mean(true_neg):.3f} |")
    print()
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
