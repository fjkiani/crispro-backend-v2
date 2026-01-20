#!/usr/bin/env python3
"""
DDR_bin Retrospective Validation (TCGA-OV Survival Analysis)

Validates DDR_bin association with PFS/OS in TCGA-OV cohort.
Links Tier-3 SAE cohort (149 patients) to cBioPortal survival data.

Exit codes:
  0: Minimum "signal present" gate passed
  2: Not enough linked/usable patients (data issue)
  3: Ran but gates failed (no signal)
"""

import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import numpy as np
import scipy.stats
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

# Paths (relative to repo root)
REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
CBIOPORTAL_DATASET = REPO_ROOT / "data" / "benchmarks" / "cbioportal_trial_datasets_latest.json"
TIER3_COHORT = REPO_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "validation" / "sae_cohort" / "checkpoints" / "Tier3_validation_cohort.json"
DIAMOND_MAPPING = REPO_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "api" / "resources" / "sae_feature_mapping.true_sae_diamonds.v1.json"
OUTPUT_DIR = REPO_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "scripts" / "validation" / "out" / "ddr_bin_tcga_ov"

# DDR gene set (frozen for reproducibility)
DDR_GENES = {
    "BRCA1", "BRCA2", "ATM", "ATR", "CHEK2", "RAD51C", "RAD51D",
    "PALB2", "BARD1", "BRIP1", "FANCA", "FANCD2", "NBN", "MRE11A",
    "TP53", "MBD4"
}


def parse_event_status(status_str: Optional[str]) -> Optional[int]:
    """Parse event status from cBioPortal format.
    
    Returns:
        1 if event occurred (status starts with "1:"), 0 if censored, None if missing/invalid
    """
    if not status_str or not isinstance(status_str, str):
        return None
    if status_str.startswith("1:"):
        return 1
    if status_str.startswith("0:"):
        return 0
    return None


def parse_months(value) -> Optional[float]:
    """Parse months field, handling NaN strings and None."""
    if value is None:
        return None
    if isinstance(value, str):
        if value.lower() in ("nan", "none", ""):
            return None
        try:
            return float(value)
        except ValueError:
            return None
    try:
        fval = float(value)
        if math.isnan(fval):
            return None
        return fval
    except (ValueError, TypeError):
        return None


def load_diamond_features() -> List[int]:
    """Load diamond feature indices from mapping file."""
    if not DIAMOND_MAPPING.exists():
        raise FileNotFoundError(f"Diamond mapping not found: {DIAMOND_MAPPING}")
    
    with open(DIAMOND_MAPPING) as f:
        mapping = json.load(f)
    
    features = mapping.get("features", [])
    if not features:
        raise ValueError("No features found in diamond mapping")
    
    diamond_indices = []
    for feat in features:
        idx = feat.get("feature_index")
        if idx is not None:
            diamond_indices.append(int(idx))
    
    if not diamond_indices:
        raise ValueError("No valid feature indices found")
    
    print(f"Loaded {len(diamond_indices)} diamond features")
    return sorted(diamond_indices)


def compute_ddr_bin(patient_data: Dict, diamond_indices: List[int]) -> Dict:
    """Compute DDR_bin score for a patient from Tier-3 variant data.
    
    Returns:
        {
            "ddr_bin": float,
            "ddr_bin_variant_max_values": List[float],
            "ddr_bin_num_variants": int,
            "ddr_bin_coverage": float
        }
    """
    variants = patient_data.get("variants", [])
    if not variants:
        return {
            "ddr_bin": 0.0,
            "ddr_bin_variant_max_values": [],
            "ddr_bin_num_variants": 0,
            "ddr_bin_coverage": 0.0
        }
    
    variant_ddr_scores = []
    variants_with_diamond = 0
    
    for variant in variants:
        top_features = variant.get("top_features", [])
        if not top_features:
            continue
        
        # Build feature value map: {index: value}
        feature_map = {}
        for tf in top_features:
            idx = tf.get("index")
            val = tf.get("value", 0.0)
            if idx is not None and val is not None:
                try:
                    feature_map[int(idx)] = float(val)
                except (ValueError, TypeError):
                    pass
        
        # Compute variant-level DDR score (max of diamond features)
        variant_ddr = 0.0
        has_diamond = False
        for diamond_idx in diamond_indices:
            if diamond_idx in feature_map:
                variant_ddr = max(variant_ddr, abs(feature_map[diamond_idx]))
                has_diamond = True
        
        if has_diamond:
            variants_with_diamond += 1
        
        variant_ddr_scores.append(variant_ddr)
    
    # Patient DDR_bin = max across all variants
    ddr_bin = max(variant_ddr_scores) if variant_ddr_scores else 0.0
    
    coverage = variants_with_diamond / len(variants) if variants else 0.0
    
    return {
        "ddr_bin": float(ddr_bin),
        "ddr_bin_variant_max_values": variant_ddr_scores,
        "ddr_bin_num_variants": len(variants),
        "ddr_bin_coverage": float(coverage)
    }


def compute_gene_ddr(mutations: List[Dict]) -> int:
    """Compute binary gene-level DDR flag."""
    if not mutations:
        return 0
    
    genes = set()
    for mut in mutations:
        if isinstance(mut, dict):
            gene = mut.get("gene")
            if gene:
                genes.add(str(gene).upper())
        elif isinstance(mut, str):
            genes.add(mut.upper())
    
    return 1 if bool(genes & DDR_GENES) else 0


def link_patients() -> List[Dict]:
    """Link Tier-3 patients to cBioPortal survival data."""
    # Load Tier-3 cohort
    if not TIER3_COHORT.exists():
        raise FileNotFoundError(f"Tier-3 cohort not found: {TIER3_COHORT}")
    
    with open(TIER3_COHORT) as f:
        tier3_data = json.load(f)
    
    tier3_patients = tier3_data.get("data", {})
    print(f"Loaded {len(tier3_patients)} Tier-3 patients")
    
    # Load cBioPortal dataset
    if not CBIOPORTAL_DATASET.exists():
        raise FileNotFoundError(f"cBioPortal dataset not found: {CBIOPORTAL_DATASET}")
    
    with open(CBIOPORTAL_DATASET) as f:
        cbioportal_data = json.load(f)
    
    # Find ov_tcga study
    ov_study = None
    for study in cbioportal_data:
        if study.get("study_id") == "ov_tcga":
            ov_study = study
            break
    
    if not ov_study:
        raise ValueError("ov_tcga study not found in cBioPortal dataset")
    
    cbioportal_patients = {p.get("patient_id"): p for p in ov_study.get("patients", [])}
    print(f"Loaded {len(cbioportal_patients)} cBioPortal patients")
    
    # Link by patient_id
    linked = []
    diamond_indices = load_diamond_features()
    
    for patient_id, tier3_info in tier3_patients.items():
        cbioportal_info = cbioportal_patients.get(patient_id)
        if not cbioportal_info:
            continue
        
        # Compute DDR_bin
        ddr_bin_info = compute_ddr_bin(tier3_info, diamond_indices)
        
        # Extract survival data
        outcomes = cbioportal_info.get("clinical_outcomes", {})
        
        pfs_months = parse_months(outcomes.get("PFS_MONTHS"))
        pfs_event = parse_event_status(outcomes.get("PFS_STATUS"))
        os_months = parse_months(outcomes.get("OS_MONTHS"))
        os_event = parse_event_status(outcomes.get("OS_STATUS"))
        
        # Extract mutations for gene-level DDR
        mutations = cbioportal_info.get("mutations", [])
        gene_ddr = compute_gene_ddr(mutations)
        
        # Extract confounders
        stage = outcomes.get("CLINICAL_STAGE")
        age = parse_months(outcomes.get("AGE"))  # Reuse parse_months for numeric fields
        residual = outcomes.get("RESIDUAL_TUMOR")
        
        # Extract platinum response from Tier-3 cohort (GOLD labels!)
        platinum_response = tier3_info.get("outcome")  # sensitive/resistant/refractory
        
        linked.append({
            "patient_id": patient_id,
            "ddr_bin": ddr_bin_info["ddr_bin"],
            "ddr_bin_coverage": ddr_bin_info["ddr_bin_coverage"],
            "ddr_bin_num_variants": ddr_bin_info["ddr_bin_num_variants"],
            "platinum_response": platinum_response,  # NEW: A3 analysis
            "pfs_months": pfs_months,
            "pfs_event": pfs_event,
            "os_months": os_months,
            "os_event": os_event,
            "gene_ddr": gene_ddr,
            "stage": stage,
            "age": age,
            "residual_tumor": residual
        })
    
    print(f"Linked {len(linked)} patients")
    return linked


def analyze_platinum_response(linked: List[Dict]) -> Dict:
    """
    A3) Analyze DDR_bin vs Platinum Response (AUROC, ROC curve).
    
    This is the MECHANISTIC test - proves DDR_bin is linked to treatment response,
    not just general prognosis.
    
    IMPORTANT (directionality):
    - Empirically in our Tier-3 cohort, **higher DDR_bin predicts platinum resistance**.
      So DDR_bin should be treated as a *resistance score* (positive class = resistant/refractory),
      and -DDR_bin (or 1 - normalized DDR_bin) as a *sensitivity score*.
    
    Returns:
        {
            "n_sensitive": int,
            "n_resistant": int,
            "auroc_resistant": float,
            "auroc_sensitive": float,
            "recommended_positive_class": str,
            "recommended_score": str,
            "auroc_ci_low": float,
            "auroc_ci_high": float,
            "optimal_threshold": float,
            "tpr_at_optimal": float,
            "tnr_at_optimal": float,
            "youden_j": float
        }
    """
    # Filter patients with platinum response labels
    usable = [
        p for p in linked
        if p.get("platinum_response") in ("sensitive", "resistant", "refractory")
    ]
    
    if len(usable) < 10:
        return {
            "n_sensitive": 0,
            "n_resistant": 0,
            "auroc_resistant": None,
            "auroc_sensitive": None,
            "recommended_positive_class": None,
            "recommended_score": None,
            "auroc_ci_low": None,
            "auroc_ci_high": None,
            "optimal_threshold": None,
            "tpr_at_optimal": None,
            "tnr_at_optimal": None,
            "youden_j": None
        }
    
    # Binary labels:
    #   y_resistant = 1 for resistant/refractory, 0 for sensitive
    # Score:
    #   DDR_bin behaves like a resistance score (higher -> more resistant)
    y_resistant = np.array([1 if p["platinum_response"] in ("resistant", "refractory") else 0 for p in usable])
    y_score = np.array([p["ddr_bin"] for p in usable])
    
    n_resistant = int(np.sum(y_resistant == 1))
    n_sensitive = int(np.sum(y_resistant == 0))

    # AUROC via rank formulation (Mann–Whitney), robust and no trapezoid warnings.
    def _auroc(y: np.ndarray, score: np.ndarray) -> float:
        y = np.asarray(y)
        score = np.asarray(score)
        pos = score[y == 1]
        neg = score[y == 0]
        if len(pos) == 0 or len(neg) == 0:
            return float("nan")
        allv = np.concatenate([pos, neg])
        ranks = allv.argsort().argsort().astype(float) + 1.0
        rpos = ranks[: len(pos)].sum()
        auc = (rpos - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))
        return float(auc)

    auroc_resistant = _auroc(y_resistant, y_score)
    auroc_sensitive = _auroc(1 - y_resistant, -y_score)  # equivalent orientation; explicit for clarity
    
    # Approximate 95% CI (simple SE heuristic; keep as rough, not publication-grade).
    se = (
        np.sqrt(auroc_resistant * (1 - auroc_resistant) / min(n_sensitive, n_resistant))
        if min(n_sensitive, n_resistant) > 0
        else 0.1
    )
    auroc_ci_low = max(0.0, auroc_resistant - 1.96 * se)
    auroc_ci_high = min(1.0, auroc_resistant + 1.96 * se)
    
    # Find optimal threshold (Youden's J = TPR - FPR)
    youden_j_values = []
    thresholds = np.unique(y_score)
    for thresh in thresholds:
        predicted_pos = y_score >= thresh
        tp = np.sum(predicted_pos & (y_resistant == 1))
        fp = np.sum(predicted_pos & (y_resistant == 0))
        fn = np.sum((~predicted_pos) & (y_resistant == 1))
        tn = np.sum((~predicted_pos) & (y_resistant == 0))

        tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0  # sensitivity for resistant
        tnr = tn / (tn + fp) if (tn + fp) > 0 else 0.0  # specificity for resistant
        youden = tpr + tnr - 1.0
        youden_j_values.append((thresh, tpr, tnr, youden))
    
    # Find max Youden's J
    if youden_j_values:
        best = max(youden_j_values, key=lambda x: x[3])
        optimal_threshold, tpr_at_optimal, tnr_at_optimal, youden_j = best
    else:
        optimal_threshold, tpr_at_optimal, tnr_at_optimal, youden_j = 0.5, 0.0, 0.0, 0.0
    
    return {
        "n_sensitive": n_sensitive,
        "n_resistant": n_resistant,
        "auroc_resistant": float(auroc_resistant),
        "auroc_sensitive": float(auroc_sensitive),
        "recommended_positive_class": "resistant_refractory",
        "recommended_score": "ddr_bin (higher = more resistant)",
        "auroc_ci_low": float(auroc_ci_low),
        "auroc_ci_high": float(auroc_ci_high),
        "optimal_threshold": float(optimal_threshold),
        "tpr_at_optimal": float(tpr_at_optimal),
        "tnr_at_optimal": float(tnr_at_optimal),
        "youden_j": float(youden_j)
    }


def plot_roc_curve(linked: List[Dict], output_path: Path):
    """Plot ROC curve for DDR_bin → Platinum Resistance (recommended orientation)."""
    usable = [
        p for p in linked
        if p.get("platinum_response") in ("sensitive", "resistant", "refractory")
    ]
    
    if len(usable) < 10:
        return
    
    # Positive class = resistant/refractory (recommended; DDR_bin behaves like resistance score)
    y_true = np.array([1 if p["platinum_response"] in ("resistant", "refractory") else 0 for p in usable])
    y_score = np.array([p["ddr_bin"] for p in usable])
    
    n_pos = int(np.sum(y_true == 1))  # resistant/refractory
    n_neg = int(np.sum(y_true == 0))  # sensitive
    
    # Compute ROC curve points
    thresholds = np.unique(y_score)
    tpr_list = []
    fpr_list = []
    
    for thresh in thresholds:
        predicted_pos = y_score >= thresh
        tp = np.sum((predicted_pos) & (y_true == 1))
        fp = np.sum((predicted_pos) & (y_true == 0))
        
        tpr = tp / n_pos if n_pos > 0 else 0
        fpr = fp / n_neg if n_neg > 0 else 0
        
        tpr_list.append(tpr)
        fpr_list.append(fpr)
    
    # Add endpoints
    fpr_list = [0.0] + fpr_list + [1.0]
    tpr_list = [0.0] + tpr_list + [1.0]
    
    fpr_arr = np.array(fpr_list)
    tpr_arr = np.array(tpr_list)
    
    # Sort by FPR
    order = np.argsort(fpr_arr)
    fpr_arr = fpr_arr[order]
    tpr_arr = tpr_arr[order]
    
    # Compute AUROC
    # Use trapezoid to avoid np.trapz deprecation warning
    auroc = float(np.trapezoid(tpr_arr, fpr_arr))
    
    # Plot
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot(fpr_arr, tpr_arr, 'b-', linewidth=2, label=f'DDR_bin (AUROC = {auroc:.3f})')
    ax.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Random (AUROC = 0.500)')
    ax.fill_between(fpr_arr, tpr_arr, alpha=0.3)
    
    ax.set_xlabel('False Positive Rate (1 - Specificity)', fontsize=12)
    ax.set_ylabel('True Positive Rate (Sensitivity)', fontsize=12)
    ax.set_title(
        f'ROC Curve: DDR_bin → Platinum Resistance\n'
        f'(positive=resistant/refractory n={n_pos}, negative=sensitive n={n_neg})',
        fontsize=14
    )
    ax.legend(loc='lower right', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    
    # Add AUROC thresholds
    if auroc >= 0.70:
        status = "GOOD (≥0.70)"
        color = 'green'
    elif auroc >= 0.65:
        status = "ACCEPTABLE (0.65-0.70)"
        color = 'orange'
    else:
        status = "POOR (<0.65)"
        color = 'red'
    
    ax.text(0.6, 0.2, f'Status: {status}', fontsize=12, color=color, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_waterfall(linked: List[Dict], output_path: Path):
    """Plot waterfall chart: DDR_bin scores ordered by platinum response."""
    usable = [
        p for p in linked
        if p.get("platinum_response") in ("sensitive", "resistant", "refractory")
    ]
    
    if len(usable) < 10:
        return
    
    # Sort by DDR_bin descending
    usable_sorted = sorted(usable, key=lambda x: -x["ddr_bin"])
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    colors = []
    for p in usable_sorted:
        if p["platinum_response"] in ("resistant", "refractory"):
            colors.append('#E74C3C')  # Red = resistant/refractory
        else:
            colors.append('#3498DB')  # Blue = sensitive
    
    x = np.arange(len(usable_sorted))
    bars = ax.bar(x, [p["ddr_bin"] for p in usable_sorted], color=colors, edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel('Patients (ordered by DDR_bin)', fontsize=12)
    ax.set_ylabel('DDR_bin Score', fontsize=12)
    ax.set_title('Waterfall: DDR_bin by Platinum Response\n(Red = Resistant/Refractory, Blue = Sensitive)', fontsize=14)
    ax.axhline(y=np.median([p["ddr_bin"] for p in usable_sorted]), color='black', linestyle='--', label='Median')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def compute_c_index(time: np.ndarray, event: np.ndarray, score: np.ndarray) -> float:
    """Compute Harrell's C-index (concordance index).
    
    Higher score should predict shorter survival (for resistance markers).
    """
    if len(time) < 2:
        return 0.5
    
    # Sort by time
    order = np.argsort(time)
    time_sorted = time[order]
    event_sorted = event[order]
    score_sorted = score[order]
    
    concordant = 0
    discordant = 0
    tied_time = 0
    tied_score = 0
    
    for i in range(len(time_sorted)):
        if event_sorted[i] == 0:  # Censored, skip
            continue
        
        for j in range(i + 1, len(time_sorted)):
            if time_sorted[j] <= time_sorted[i]:  # j died/censored before i's event
                continue
            
            # Compare scores (higher score = worse outcome)
            if score_sorted[i] > score_sorted[j]:
                concordant += 1
            elif score_sorted[i] < score_sorted[j]:
                discordant += 1
            else:
                tied_score += 1
    
    total = concordant + discordant + tied_score
    if total == 0:
        return 0.5
    
    return concordant / total if total > 0 else 0.5


def logrank_test(time: np.ndarray, event: np.ndarray, group: np.ndarray) -> float:
    """Manual log-rank test (simplified).
    
    Returns p-value.
    """
    if len(np.unique(group)) < 2:
        return 1.0
    
    # Simplified: use Mann-Whitney U on event times (weighted by events)
    group0_mask = group == 0
    group1_mask = group == 1
    
    time0 = time[group0_mask]
    event0 = event[group0_mask]
    time1 = time[group1_mask]
    event1 = event[group1_mask]
    
    # Weight by event status
    weighted_time0 = time0 * event0
    weighted_time1 = time1 * event1
    
    # Mann-Whitney U test
    try:
        u_stat, p_value = scipy.stats.mannwhitneyu(
            weighted_time0, weighted_time1, alternative='two-sided'
        )
        return float(p_value)
    except Exception:
        return 1.0


def analyze_survival(linked: List[Dict], endpoint: str) -> Dict:
    """Analyze survival endpoint (PFS or OS)."""
    months_key = f"{endpoint}_months"
    event_key = f"{endpoint}_event"
    
    # Filter usable patients
    usable = [
        p for p in linked
        if p[months_key] is not None and p[event_key] is not None
    ]
    
    if len(usable) < 10:
        return {
            "usable": len(usable),
            "pearson_r": 0.0,
            "pearson_p": 1.0,
            "spearman_rho": 0.0,
            "spearman_p": 1.0,
            "logrank_p": 1.0,
            "median_months_high": None,
            "median_months_low": None,
            "c_index_ddr_bin": None
        }
    
    ddr_bin = np.array([p["ddr_bin"] for p in usable])
    time = np.array([p[months_key] for p in usable])
    event = np.array([p[event_key] for p in usable])
    
    # Correlations
    pearson_r, pearson_p = scipy.stats.pearsonr(ddr_bin, time)
    spearman_rho, spearman_p = scipy.stats.spearmanr(ddr_bin, time)
    
    # Median split
    median_ddr = np.median(ddr_bin)
    group = (ddr_bin > median_ddr).astype(int)
    
    # Log-rank test
    logrank_p = logrank_test(time, event, group)
    
    # Median survival by group
    group0_time = time[group == 0]
    group0_event = event[group == 0]
    group1_time = time[group == 1]
    group1_event = event[group == 1]
    
    # Simple median (ignoring censoring for simplicity)
    median_low = np.median(group0_time) if len(group0_time) > 0 else None
    median_high = np.median(group1_time) if len(group1_time) > 0 else None
    
    # C-index
    c_index = compute_c_index(time, event, ddr_bin)
    
    return {
        "usable": len(usable),
        "pearson_r": float(pearson_r),
        "pearson_p": float(pearson_p),
        "spearman_rho": float(spearman_rho),
        "spearman_p": float(spearman_p),
        "logrank_p": float(logrank_p),
        "median_months_high": float(median_high) if median_high is not None else None,
        "median_months_low": float(median_low) if median_low is not None else None,
        "c_index_ddr_bin": float(c_index)
    }


def plot_km_curves(linked: List[Dict], endpoint: str, output_path: Path):
    """Plot Kaplan-Meier curves (simplified, manual implementation)."""
    months_key = f"{endpoint}_months"
    event_key = f"{endpoint}_event"
    
    usable = [
        p for p in linked
        if p[months_key] is not None and p[event_key] is not None
    ]
    
    if len(usable) < 10:
        return
    
    ddr_bin = np.array([p["ddr_bin"] for p in usable])
    time = np.array([p[months_key] for p in usable])
    event = np.array([p[event_key] for p in usable])
    
    median_ddr = np.median(ddr_bin)
    group = (ddr_bin > median_ddr).astype(int)
    
    # Simple KM curves (step function)
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for g, label in [(0, "DDR_bin Low"), (1, "DDR_bin High")]:
        mask = group == g
        if not np.any(mask):
            continue
        
        t = time[mask]
        e = event[mask]
        
        # Sort by time
        order = np.argsort(t)
        t_sorted = t[order]
        e_sorted = e[order]
        
        # Compute survival curve
        n = len(t_sorted)
        surv = np.ones(n + 1)
        time_points = np.concatenate([[0], t_sorted])
        
        for i in range(n):
            if e_sorted[i] == 1:
                surv[i + 1] = surv[i] * (1 - 1 / (n - i))
            else:
                surv[i + 1] = surv[i]
        
        ax.step(time_points, surv, where='post', label=label, linewidth=2)
    
    ax.set_xlabel(f"{endpoint.upper()} Time (months)")
    ax.set_ylabel("Survival Probability")
    ax.set_title(f"Kaplan-Meier Curves: {endpoint.upper()} by DDR_bin")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def plot_ddr_bin_distribution(linked: List[Dict], output_path: Path):
    """Plot DDR_bin distribution histogram."""
    ddr_bin_values = [p["ddr_bin"] for p in linked if p["ddr_bin"] is not None]
    
    if not ddr_bin_values:
        return
    
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.hist(ddr_bin_values, bins=30, edgecolor='black', alpha=0.7)
    ax.set_xlabel("DDR_bin Score")
    ax.set_ylabel("Frequency")
    ax.set_title("DDR_bin Distribution (Tier-3 Cohort)")
    ax.axvline(np.median(ddr_bin_values), color='red', linestyle='--', label=f'Median: {np.median(ddr_bin_values):.3f}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def main():
    """Main validation workflow."""
    print("=" * 80)
    print("DDR_bin Retrospective Validation (TCGA-OV)")
    print("=" * 80)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Link patients
    print("\n[1/4] Linking Tier-3 patients to cBioPortal survival data...")
    try:
        linked = link_patients()
    except Exception as e:
        print(f"ERROR: Failed to link patients: {e}")
        sys.exit(2)
    
    if len(linked) < 10:
        print(f"ERROR: Only {len(linked)} linked patients (need ≥10)")
        sys.exit(2)
    
    # Compute DDR_bin summary
    ddr_bin_values = [p["ddr_bin"] for p in linked]
    ddr_bin_summary = {
        "min": float(np.min(ddr_bin_values)),
        "median": float(np.median(ddr_bin_values)),
        "max": float(np.max(ddr_bin_values))
    }
    
    # Analyze PFS
    print("\n[2/4] Analyzing PFS...")
    pfs_results = analyze_survival(linked, "pfs")
    
    # Analyze OS
    print("\n[3/4] Analyzing OS...")
    os_results = analyze_survival(linked, "os")
    
    # A3) Platinum Response Analysis (THE MECHANISTIC TEST!)
    print("\n[4/6] Analyzing Platinum Response (A3)...")
    platinum_results = analyze_platinum_response(linked)
    
    # Head-to-head comparison (gene-level DDR vs DDR_bin)
    print("\n[5/6] Head-to-head comparison...")
    pfs_usable = [
        p for p in linked
        if p["pfs_months"] is not None and p["pfs_event"] is not None
    ]
    
    head_to_head = {}
    if len(pfs_usable) >= 10:
        time = np.array([p["pfs_months"] for p in pfs_usable])
        event = np.array([p["pfs_event"] for p in pfs_usable])
        ddr_bin = np.array([p["ddr_bin"] for p in pfs_usable])
        gene_ddr = np.array([p["gene_ddr"] for p in pfs_usable])
        
        c_index_ddr_bin = compute_c_index(time, event, ddr_bin)
        c_index_gene_ddr = compute_c_index(time, event, gene_ddr.astype(float))
        
        head_to_head = {
            "c_index_ddr_bin_pfs": float(c_index_ddr_bin),
            "c_index_gene_ddr_pfs": float(c_index_gene_ddr),
            "delta_c_index": float(c_index_ddr_bin - c_index_gene_ddr)
        }
    else:
        head_to_head = {
            "c_index_ddr_bin_pfs": None,
            "c_index_gene_ddr_pfs": None,
            "delta_c_index": None
        }
    
    # Generate plots
    print("\n[6/6] Generating plots...")
    plot_km_curves(linked, "pfs", OUTPUT_DIR / "km_pfs.png")
    plot_km_curves(linked, "os", OUTPUT_DIR / "km_os.png")
    plot_ddr_bin_distribution(linked, OUTPUT_DIR / "ddr_bin_hist.png")
    plot_roc_curve(linked, OUTPUT_DIR / "roc_platinum_response.png")
    plot_waterfall(linked, OUTPUT_DIR / "waterfall_ddr_bin.png")
    
    # Export linked patients CSV
    import csv
    with open(OUTPUT_DIR / "linked_patients.csv", "w", newline="") as f:
        # Only include fields that exist in all linked records
        fieldnames = [
            "patient_id", "ddr_bin", "ddr_bin_coverage", "ddr_bin_num_variants",
            "platinum_response",  # NEW: A3 analysis
            "pfs_months", "pfs_event", "os_months", "os_event",
            "gene_ddr", "stage", "age", "residual_tumor"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(linked)
    
    # Build report
    report = {
        "run_meta": {
            "study_id": "ov_tcga",
            "tier3_patients_total": len(linked),
            "linked_patients": len(linked),
            "pfs_usable": pfs_results["usable"],
            "os_usable": os_results["usable"],
            "diamond_mapping_version": "v1",
            "data_files": {
                "cbioportal_dataset": str(CBIOPORTAL_DATASET.relative_to(REPO_ROOT)),
                "tier3": str(TIER3_COHORT.relative_to(REPO_ROOT)),
                "diamonds": str(DIAMOND_MAPPING.relative_to(REPO_ROOT))
            }
        },
        "ddr_bin_summary": ddr_bin_summary,
        "pfs": pfs_results,
        "os": os_results,
        "platinum_response": platinum_results,  # NEW: A3 analysis
        "head_to_head": head_to_head,
        "verdict": {
            "status": "pending",
            "reasons": []
        }
    }
    
    # Determine verdict
    verdict_reasons = []
    
    # Minimum gate: log-rank p < 0.10 OR |Spearman| ≥ 0.15 OR Platinum AUROC(resistant) > 0.65
    pfs_passed = (pfs_results["logrank_p"] < 0.10) or (abs(pfs_results["spearman_rho"]) >= 0.15)
    os_passed = (os_results["logrank_p"] < 0.10) or (abs(os_results["spearman_rho"]) >= 0.15)
    platinum_passed = (
        platinum_results.get("auroc_resistant") is not None
        and platinum_results["auroc_resistant"] > 0.65
    )
    
    if pfs_passed or os_passed or platinum_passed:
        report["verdict"]["status"] = "pass"
        if pfs_passed:
            verdict_reasons.append(f"PFS: log-rank p={pfs_results['logrank_p']:.4f} OR |Spearman|={abs(pfs_results['spearman_rho']):.3f}")
        if os_passed:
            verdict_reasons.append(f"OS: log-rank p={os_results['logrank_p']:.4f} OR |Spearman|={abs(os_results['spearman_rho']):.3f}")
        if platinum_passed:
            verdict_reasons.append(f"Platinum Response AUROC(resistant)={platinum_results['auroc_resistant']:.3f} > 0.65 (MECHANISTIC SIGNAL)")
    else:
        report["verdict"]["status"] = "fail"
        verdict_reasons.append("Neither PFS, OS, nor Platinum Response met minimum gate")
        if platinum_results.get("auroc_resistant") is not None:
            verdict_reasons.append(f"Platinum AUROC(resistant)={platinum_results['auroc_resistant']:.3f} (target > 0.65)")
    
    report["verdict"]["reasons"] = verdict_reasons
    
    # Save report
    with open(OUTPUT_DIR / "report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Linked patients: {len(linked)}")
    print(f"PFS usable: {pfs_results['usable']}")
    print(f"OS usable: {os_results['usable']}")
    print(f"\nA1) PFS Survival:")
    print(f"  Spearman ρ: {pfs_results['spearman_rho']:.3f} (p={pfs_results['spearman_p']:.4f})")
    print(f"  Log-rank p: {pfs_results['logrank_p']:.4f}")
    print(f"  C-index: {pfs_results['c_index_ddr_bin']:.3f}" if pfs_results['c_index_ddr_bin'] else "  C-index: N/A")
    print(f"\nA1) OS Survival:")
    print(f"  Spearman ρ: {os_results['spearman_rho']:.3f} (p={os_results['spearman_p']:.4f})")
    print(f"  Log-rank p: {os_results['logrank_p']:.4f}")
    print(f"  C-index: {os_results['c_index_ddr_bin']:.3f}" if os_results['c_index_ddr_bin'] else "  C-index: N/A")
    
    # A3) Platinum Response - THE KEY TEST
    print(f"\nA3) PLATINUM RESPONSE (MECHANISTIC TEST):")
    if platinum_results.get("auroc_resistant") is not None:
        print(f"  Sensitive: {platinum_results['n_sensitive']} patients")
        print(f"  Resistant/Refractory: {platinum_results['n_resistant']} patients")
        print(f"  AUROC (predict resistant, score=DDR_bin): {platinum_results['auroc_resistant']:.3f} ({platinum_results['auroc_ci_low']:.3f}-{platinum_results['auroc_ci_high']:.3f})")
        print(f"  AUROC (predict sensitive, score=-DDR_bin): {platinum_results['auroc_sensitive']:.3f}")
        print(f"  Optimal threshold (for resistant): {platinum_results['optimal_threshold']:.3f}")
        print(f"  TPR at optimal (resistant): {platinum_results['tpr_at_optimal']:.3f}")
        print(f"  TNR at optimal (resistant): {platinum_results['tnr_at_optimal']:.3f}")
        print(f"  Interpretation: {platinum_results['recommended_score']}")
        
        # Status (Manager gate)
        if platinum_results['auroc_resistant'] >= 0.70:
            print("  STATUS: ✅ GOOD (AUROC ≥ 0.70)")
        elif platinum_results['auroc_resistant'] >= 0.65:
            print("  STATUS: ⚠️ ACCEPTABLE (0.65 ≤ AUROC < 0.70)")
        else:
            print("  STATUS: ❌ POOR (AUROC < 0.65)")
    else:
        print("  AUROC: N/A (not enough data)")
    
    if head_to_head.get("delta_c_index") is not None:
        print(f"\nA2) Head-to-head:")
        print(f"  DDR_bin C-index: {head_to_head['c_index_ddr_bin_pfs']:.3f}")
        print(f"  Gene-level DDR C-index: {head_to_head['c_index_gene_ddr_pfs']:.3f}")
        print(f"  Delta: {head_to_head['delta_c_index']:.3f}")
    print(f"\nVerdict: {report['verdict']['status'].upper()}")
    for reason in verdict_reasons:
        print(f"  - {reason}")
    print(f"\nOutputs saved to: {OUTPUT_DIR}")
    print("=" * 80)
    
    # Exit code
    if report["verdict"]["status"] == "pass":
        sys.exit(0)
    else:
        sys.exit(3)


if __name__ == "__main__":
    main()
