#!/usr/bin/env python3
"""Generate Figure 3: DDR_bin Distribution for Publication

Creates box/violin plot showing DDR_bin scores for resistant vs sensitive patients.

Run:
  python scripts/publication/generate_ddr_bin_distribution.py
"""

import json
import numpy as np
from pathlib import Path
from scipy import stats

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')
except ImportError:
    print("matplotlib not installed. Run: pip install matplotlib")
    exit(1)

REPO_ROOT = Path(__file__).resolve().parents[2]

TIER3_PATH = REPO_ROOT / "data/validation/sae_cohort/checkpoints/Tier3_validation_cohort.json"
MAPPING_PATH = REPO_ROOT / "api/resources/sae_feature_mapping.true_sae_diamonds.v1.json"


def load_data():
    tier3 = json.loads(TIER3_PATH.read_text())
    mapping = json.loads(MAPPING_PATH.read_text())
    return tier3, mapping


def compute_ddr_bin(patient_data, diamond_features):
    """Compute DDR_bin score for a patient."""
    feature_sums = {fidx: 0.0 for fidx in diamond_features}
    
    for variant in patient_data.get("variants", []):
        for tf in variant.get("top_features", []):
            fidx = tf.get("index")
            if fidx in feature_sums:
                feature_sums[fidx] += float(tf.get("value", 0.0) or 0.0)
    
    return sum(feature_sums.values()) / len(diamond_features) if diamond_features else 0.0


def main():
    print("Loading data...")
    tier3, mapping = load_data()
    patients = tier3.get("data", {})
    diamond_features = [f["feature_index"] for f in mapping.get("features", [])]
    
    print(f"Diamond features: {len(diamond_features)}")
    
    # Compute DDR_bin for each patient
    resistant_scores = []
    sensitive_scores = []
    
    for pid, pdata in patients.items():
        outcome = pdata.get("outcome")
        if outcome not in ("sensitive", "resistant", "refractory"):
            continue
        
        ddr_bin = compute_ddr_bin(pdata, diamond_features)
        
        if outcome in ("resistant", "refractory"):
            resistant_scores.append(ddr_bin)
        else:
            sensitive_scores.append(ddr_bin)
    
    print(f"Resistant: n={len(resistant_scores)}, mean={np.mean(resistant_scores):.3f}")
    print(f"Sensitive: n={len(sensitive_scores)}, mean={np.mean(sensitive_scores):.3f}")
    
    # Statistical test
    stat, pvalue = stats.mannwhitneyu(resistant_scores, sensitive_scores, alternative='greater')
    effect_size = (np.mean(resistant_scores) - np.mean(sensitive_scores)) / np.sqrt(
        (np.var(resistant_scores) + np.var(sensitive_scores)) / 2
    )
    
    print(f"Mann-Whitney U: p={pvalue:.4f}")
    print(f"Cohen's d: {effect_size:.3f}")
    
    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=(8, 6))
    
    # Box plot with individual points
    data = [sensitive_scores, resistant_scores]
    labels = [f'Sensitive\n(n={len(sensitive_scores)})', f'Resistant\n(n={len(resistant_scores)})']
    colors = ['#3498DB', '#E74C3C']
    
    bp = ax.boxplot(data, labels=labels, patch_artist=True, widths=0.6)
    
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    
    for median in bp['medians']:
        median.set(color='black', linewidth=2)
    
    # Add individual points with jitter
    for i, (d, c) in enumerate(zip(data, colors)):
        x = np.random.normal(i + 1, 0.08, size=len(d))
        ax.scatter(x, d, alpha=0.5, color=c, s=30, edgecolors='white', linewidth=0.5)
    
    ax.set_ylabel('DDR_bin Score (mean of 9 diamond features)', fontsize=12)
    ax.set_title('DDR_bin Distribution: Resistant vs Sensitive\n(TCGA-OV Platinum Response)', fontsize=14)
    
    # Add statistics annotation
    ymax = max(max(resistant_scores), max(sensitive_scores))
    ax.annotate(f'Mann-Whitney U\np = {pvalue:.4f}', 
                xy=(1.5, ymax * 0.95), ha='center', fontsize=11,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    ax.annotate(f"Cohen's d = {effect_size:.2f}", 
                xy=(1.5, ymax * 0.80), ha='center', fontsize=11,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    ax.grid(True, alpha=0.3, axis='y')
    
    # Save figure
    output_dir = REPO_ROOT / "publication" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "figure3_ddr_bin_distribution.png"
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved: {output_path}")
    
    output_path_pdf = output_dir / "figure3_ddr_bin_distribution.pdf"
    plt.savefig(output_path_pdf, format='pdf', bbox_inches='tight')
    print(f"Saved: {output_path_pdf}")
    
    plt.close()
    
    print()
    print("=" * 60)
    print("FIGURE 3 GENERATED")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
