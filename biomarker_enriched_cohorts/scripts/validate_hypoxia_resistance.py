#!/usr/bin/env python3
"""Hypoxia surrogate validation for platinum resistance prediction (RUO).

Purpose
- Validate hypoxia scores (BUFFA/RAGNUM/WINTER) as surrogate biomarkers for platinum resistance
- Compare hypoxia-only vs BRCA/HRD baseline vs combined
- Produce publication-ready metrics + figures

Primary endpoint (classification)
- platinum_resistant (boolean label from cohort JSON)

Secondary endpoint (survival)
- Kaplan–Meier + log-rank + Cox HR for High vs Low hypoxia (median split)

Outputs (written under biomarker_enriched_cohorts/)
- reports/validate_hypoxia_resistance_<tag>.json
- reports/validate_hypoxia_resistance_<tag>.md
- figures/figure_hypoxia_km_curves_<tag>.png
- figures/figure_hypoxia_roc_curves_<tag>.png

Notes / Claim discipline
- DeLong p-values are computed using our simplified implementati in `model_comparison.py`.
  It currently assumes independence (covariance term set to 0). Treat p-values as RUO / approximate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Local imports (scripts live in same folder)
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from _validation_utils import km_and_logrank, now_utc_iso, write_json, write_md
from baseline_comparison_io import cox_hr
from logistic_validation import logistic_auroc_cv
from model_comparison import compare_models


def load_hypoxia_cohort(cohort_path: Path) -> pd.DataFrame:
    """Load hypoxia-enriched cohort JSON into a flat DataFrame."""
    data = json.loads(cohort_path.read_text(encoding="utf-8"))
    patients = (data.get("cohort") or {}).get("patients") or []

    rows = []
    for pt in patients:
        hypoxia = pt.get("hypoxia") or {}
        outcomes = pt.get("outcomes") or {}
        biomarkers = pt.get("biomarkers") or {}

        rows.append(
            {
                "patient_id": pt.get("patient_id"),
                "buffa_hypoxia_score": hypoxia.get("buffa_score"),
                "ragnum_hypoxia_score": hypoxia.get("ragnum_score"),
                "winter_hypoxia_score": hypoxia.get("winter_score"),
                "pfs_days": outcomes.get("pfs_days"),
                "pfs_event": outcomes.get("pfs_event"),
                "pfs_months": outcomes.get("pfs_months"),
                "os_days": outcomes.get("os_days"),
                "os_event": outcomes.get("os_event"),
                "os_months": outcomes.get("os_months"),
                "platinum_resistant": pt.get("platinum_resistant"),
                "age": (pt.get("demographics") or {}).get("age"),
                "brca_somatic": biomarkers.get("brca_somatic"),
                "brca_germline": biomarkers.get("brca_germline"),
                "hrd_proxy": biomarkers.get("hrd_proxy"),
                "brca_mutated": biomarkers.get("brca_mutated", False),
                "hrd_high": biomarkers.get("hrd_high", False),
            }
        )

    df = pd.DataFrame(rows)

    # HRD proxy: cohort stores categorical labels (e.g., 'HRD-High'), so derive a numeric score
    if 'hrd_proxy' in df.columns:
        df['hrd_proxy'] = df['hrd_proxy'].astype('object')
        _hrd_map = {
            'HRD-Low': 0.0,
            'HRD-Intermediate': 0.5,
            'HRD-High': 1.0,
            'low': 0.0,
            'intermediate': 0.5,
            'high': 1.0,
        }
        df['hrd_proxy_score'] = df['hrd_proxy'].map(_hrd_map)
        # if numeric values are present, fall back to numeric coercion
        mask = df['hrd_proxy_score'].isna()
        if mask.any():
            df.loc[mask, 'hrd_proxy_score'] = pd.to_numeric(df.loc[mask, 'hrd_proxy'], errors='coerce')

    # numeric casts
    for col in [
        "buffa_hypoxia_score",
        "ragnum_hypoxia_score",
        "winter_hypoxia_score",
        "pfs_days",
        "os_days",
        "pfs_months",
        "os_months",
        "age",
        "hrd_proxy",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # boolean-ish casts (keep as bool/NaN)
    for col in ["pfs_event", "os_event", "platinum_resistant", "brca_mutated", "hrd_high"]:
        if col in df.columns:
            df[col] = df[col].map(
                lambda x: True
                if x is True or x == 1
                else (False if x is False or x == 0 else np.nan)
            )

    return df


def create_hypoxia_groups(df: pd.DataFrame, score_col: str) -> tuple[pd.DataFrame, float]:
    """Create High/Low hypoxia groups via median split (ties go to Low)."""
    df = df.copy()
    median_score = float(df[score_col].median())

    df["hypoxia_group"] = pd.Series([None] * len(df), dtype="object")
    known = df[score_col].notna()

    df.loc[known & (df[score_col] > median_score), "hypoxia_group"] = "High"
    df.loc[known & (df[score_col] <= median_score), "hypoxia_group"] = "Low"

    return df, median_score


def plot_km_curves(km_stats: Dict[str, Any], title: str, out_path: Path) -> None:
    kmf_a = km_stats.get("kmf_a")
    kmf_b = km_stats.get("kmf_b")
    if kmf_a is None or kmf_b is None:
        return

    _, ax = plt.subplots(figsize=(10, 6))
    kmf_a.plot_survival_function(ax=ax, ci_show=True, label=kmf_a.label)
    kmf_b.plot_survival_function(ax=ax, ci_show=True, label=kmf_b.label)

    ax.set_title(title)
    ax.set_xlabel("Days")
    ax.set_ylabel("Survival Probability")
    ax.grid(True, alpha=0.25)

    p_value = km_stats.get("p_value")
    if p_value is not None:
        ax.text(
            0.98,
            0.02,
            f"Log-rank p={p_value:.3g}",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
        )

    ax.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()


def plot_roc_curves(
    hypoxia_result: Dict[str, Any],
    baseline_result: Dict[str, Any],
    combined_result: Dict[str, Any],
    out_path: Path,
) -> None:
    _, ax = plt.subplots(figsize=(8, 8))

    def plot_one(res: Dict[str, Any], label: str, style: str = "-") -> None:
        roc = res.get("roc_curve") or {}
        if not roc:
            return
        ax.plot(
            roc["fpr"],
            roc["tpr"],
            label=f"{label} (AUC={res['auroc']:.3f})",
            linewidth=2,
            linestyle=style,
        )

    plot_one(hypoxia_result, "Hypoxia")
    plot_one(baseline_result, "BRCA/HRD")
    plot_one(combined_result, "Hypoxia + BRCA/HRD", style="--")

    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Random")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curves: Hypoxia vs Baseline vs Combined")
    ax.legend()
    ax.grid(True, alpha=0.25)

    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()


def _endpoint_label(time_col: str) -> str:
    t = time_col.lower()
    if t.startswith("pfs"):
        return "PFS"
    if t.startswith("os"):
        return "OS"
    return time_col


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort_json", type=str, required=True, help="Path to hypoxia-enriched cohort JSON")
    ap.add_argument("--time_col", type=str, default="pfs_days", help="Time column for survival analysis")
    ap.add_argument("--event_col", type=str, default="pfs_event", help="Event column for survival analysis")
    ap.add_argument(
        "--hypoxia_score",
        type=str,
        default="buffa",
        choices=["buffa", "ragnum", "winter"],
        help="Hypoxia score to use",
    )
    ap.add_argument("--tag", type=str, default=None, help="Tag for output files")

    # Optional feature lifts (simple, reproducible, no new data dependencies)
    ap.add_argument("--include_age", action="store_true", help="Add age to baseline/combined models")
    ap.add_argument(
        "--use_hrd_proxy_continuous",
        action="store_true",
        help="Use continuous hrd_proxy instead of hrd_high for baseline/combined models",
    )

    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    cohort_path = Path(args.cohort_json)
    if not cohort_path.exists():
        print(f"❌ Cohort file not found: {cohort_path}")
        return 1

    tag = args.tag or cohort_path.stem
    figures_dir = root / "figures"
    reports_dir = root / "reports"
    figures_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    score_col = f"{args.hypoxia_score}_hypoxia_score"
    endpoint = _endpoint_label(args.time_col)

    print("=" * 80)
    print("HYPOXIA SURROGATE VALIDATION FOR PLATINUM RESISTANCE")
    print("=" * 80)

    # Step 1: Load cohort
    print("\n📊 Step 1: Loading hypoxia-enriched cohort...")
    df = load_hypoxia_cohort(cohort_path)
    print(f"   ✅ Loaded {len(df)} patients")

    if score_col not in df.columns:
        print(f"   ❌ Hypoxia score column not found: {score_col}")
        return 1

    n_resistant = int((df.get("platinum_resistant") == True).sum())
    n_sensitive = int((df.get("platinum_resistant") == False).sum())
    print(f"   ✅ Platinum Resistant: {n_resistant} patients")
    print(f"   ✅ Platinum Sensitive: {n_sensitive} patients")

    # Step 2: Create hypoxia groups
    print(f"\n📊 Step 2: Creating hypoxia groups ({args.hypoxia_score.upper()}, median split)...")
    df, median_score = create_hypoxia_groups(df, score_col=score_col)
    n_high = int((df["hypoxia_group"] == "High").sum())
    n_low = int((df["hypoxia_group"] == "Low").sum())
    print(f"   ✅ High Hypoxia: {n_high} patients (median threshold: {median_score:.3f})")
    print(f"   ✅ Low Hypoxia: {n_low} patients")

    # Step 3: Survival analysis
    print("\n📊 Step 3: Running survival analysis (KM + log-rank + Cox)...")
    survival_df = df[df[[args.time_col, args.event_col, "hypoxia_group"]].notna().all(axis=1)].copy()
    survival_df = survival_df[survival_df["hypoxia_group"].isin(["High", "Low"])]

    if len(survival_df) < 20:
        print(f"   ⚠️  Insufficient data for survival analysis (n={len(survival_df)})")
        return 1

    km_stats = km_and_logrank(
        df=survival_df,
        time_col=args.time_col,
        event_col=args.event_col,
        group_col="hypoxia_group",
        group_a="Low",
        group_b="High",
    )

    p_lr = km_stats.get("p_value")
    med_low = km_stats.get("median_days_a")
    med_high = km_stats.get("median_days_b")

    if p_lr is not None:
        print(f"   ✅ Log-rank p-value: {p_lr:.4g}")

    print(f"   ✅ Median {endpoint} (Low): {med_low if med_low is not None else 'NR'} days")
    print(f"   ✅ Median {endpoint} (High): {med_high if med_high is not None else 'NR'} days")

    hr, (hr_lo, hr_hi), cox_p = cox_hr(
        survival_df,
        time_col=args.time_col,
        event_col=args.event_col,
        group_col="hypoxia_group",
        pos_label="High",
    )

    if hr is not None and hr_lo is not None and hr_hi is not None and cox_p is not None:
        print(f"   ✅ Cox HR (High vs Low): {hr:.2f} ({hr_lo:.2f}-{hr_hi:.2f}), p={cox_p:.4g}")

    km_fig_path = figures_dir / f"figure_hypoxia_km_curves_{tag}.png"
    plot_km_curves(km_stats, f"{endpoint} by hypoxia group ({args.hypoxia_score.upper()}, {tag})", km_fig_path)
    print(f"   ✅ Saved KM curves: {km_fig_path}")

    # Step 4: Classification validation
    print("\n📊 Step 4: Running classification validation (LogReg CV AUROC)...")

    feature_baseline = ["brca_mutated", "hrd_high"]
    if args.use_hrd_proxy_continuous:
        feature_baseline = ["brca_mutated", "hrd_proxy_score"]

    if args.include_age:
        feature_baseline = feature_baseline + ["age"]

    feature_hypoxia = [score_col]
    feature_combined = [score_col] + feature_baseline

    needed_cols = ["platinum_resistant"] + list(dict.fromkeys(feature_combined))
    classification_df = df[df[needed_cols].notna().all(axis=1)].copy()

    if len(classification_df) < 20:
        print(f"   ⚠️  Insufficient data for classification (n={len(classification_df)})")
        return 1

    y = classification_df["platinum_resistant"].astype(int).values

    print(f"   ✅ Classification n={len(classification_df)} using features: baseline={feature_baseline}")

    # Model 1: hypoxia only
    X_hypoxia = classification_df[feature_hypoxia].values
    hypoxia_result = logistic_auroc_cv(X_hypoxia, y, cv=5)
    print(f"      ✅ Hypoxia AUROC: {hypoxia_result['auroc']:.3f} ({hypoxia_result['ci_lower']:.3f}-{hypoxia_result['ci_upper']:.3f})")

    # Model 2: baseline
    X_baseline = classification_df[feature_baseline].values
    baseline_result = logistic_auroc_cv(X_baseline, y, cv=5)
    print(f"      ✅ Baseline AUROC: {baseline_result['auroc']:.3f} ({baseline_result['ci_lower']:.3f}-{baseline_result['ci_upper']:.3f})")

    # Model 3: combined
    X_combined = classification_df[feature_combined].values
    combined_result = logistic_auroc_cv(X_combined, y, cv=5)
    print(f"      ✅ Combined AUROC: {combined_result['auroc']:.3f} ({combined_result['ci_lower']:.3f}-{combined_result['ci_upper']:.3f})")

    # Step 5: DeLong comparisons on out-of-fold scores
    print("\n📊 Step 5: Comparing models (DeLong test; RUO approx)...")
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    cv_splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    baseline_model = LogisticRegression(max_iter=1000, random_state=42)
    combined_model = LogisticRegression(max_iter=1000, random_state=42)
    hypoxia_model = LogisticRegression(max_iter=1000, random_state=42)

    baseline_scores = cross_val_predict(baseline_model, X_baseline, y, cv=cv_splitter, method="predict_proba")[:, 1]
    combined_scores = cross_val_predict(combined_model, X_combined, y, cv=cv_splitter, method="predict_proba")[:, 1]
    hypoxia_scores = cross_val_predict(hypoxia_model, X_hypoxia, y, cv=cv_splitter, method="predict_proba")[:, 1]

    combined_vs_baseline = compare_models(
        y,
        baseline_scores,
        combined_scores,
        baseline_name="Baseline",
        surrogate_name="Hypoxia+Baseline",
    )
    hypoxia_vs_baseline = compare_models(
        y,
        baseline_scores,
        hypoxia_scores,
        baseline_name="Baseline",
        surrogate_name="Hypoxia",
    )

    print(
        f"   ✅ Combined vs baseline: ΔAUROC={combined_vs_baseline['comparison']['improvement']:+.3f}, "
        f"p={combined_vs_baseline['delong_test']['p_value']:.4g}"
    )
    print(
        f"   ✅ Hypoxia vs baseline: ΔAUROC={hypoxia_vs_baseline['comparison']['improvement']:+.3f}, "
        f"p={hypoxia_vs_baseline['delong_test']['p_value']:.4g}"
    )

    roc_fig_path = figures_dir / f"figure_hypoxia_roc_curves_{tag}.png"
    plot_roc_curves(hypoxia_result, baseline_result, combined_result, roc_fig_path)
    print(f"   ✅ Saved ROC curves: {roc_fig_path}")

    # Step 6: Compile + write reports
    print("\n📊 Step 6: Writing receipts...")

    results: Dict[str, Any] = {
        "run": {
            "generated_at": now_utc_iso(),
            "cohort_path": str(cohort_path),
            "tag": tag,
            "hypoxia_score_used": args.hypoxia_score.upper(),
            "median_threshold": float(median_score),
            "endpoint": {"time_col": args.time_col, "event_col": args.event_col, "label": endpoint},
            "notes": {
                "delong_assumption": "Simplified DeLong variance; covariance assumed 0 (treat p-values as approximate / RUO).",
            },
            "feature_flags": {
                "include_age": bool(args.include_age),
                "use_hrd_proxy_continuous": bool(args.use_hrd_proxy_continuous),         },
        },
        "cohort": {
            "n_total": int(len(df)),
            "n_high_hypoxia": int(n_high),
            "n_low_hypoxia": int(n_low),
            "n_resistant": int(n_resistant),
            "n_sensitive": int(n_sensitive),
        },
        "survival_analysis": {
            "n_analyzed": int(len(survival_df)),
            "logrank_p_value": p_lr,
            "logrank_statistic": km_stats.get("test_statistic"),
            "median_low_days": med_low,
            "median_high_days": med_high,
            "cox_hr_high_vs_low": hr,
            "cox_hr_ci": [hr_lo, hr_hi] if hr is not None else None,
            "cox_p_value": cox_p,
        },
        "classification_validation": {
            "n_analyzed": int(len(classification_df)),
            "features": {
                "hypoxia": feature_hypoxia,
                "baseline": feature_baseline,
                "combined": feature_combined,
            },
            "hypoxia": hypoxia_result,
            "baseline": baseline_result,
            "combined": combined_result,
            "model_comparison": {
                "hypoxia_vs_baseline": hypoxia_vs_baseline,
                "combined_vs_baseline": combined_vs_baseline,
            },
        },
        "figures": {
            "km_curves": str(km_fig_path),
            "roc_curves": str(roc_fig_path),
        },
    }

    # Convenience fields for downstream readers
    results['classification_validation']['models'] = [
        {'name': 'hypoxia', 'features': feature_hypoxia, **hypoxia_result},
        {'name': 'baseline', 'features': feature_baseline, **baseline_result},
        {'name': 'combined', 'features': feature_combined, **combined_result},
    ]
    results['classification_validation']['delong_comparisons'] = [
        {
            'a': 'combined',
            'b': 'baseline',
            'delta_auroc': combined_vs_baseline['comparison']['improvement'],
            'p_value': combined_vs_baseline['delong_test']['p_value'],
            'assumption': results['run']['notes']['delong_assumption'],
        },
        {
            'a': 'hypoxia',
            'b': 'baseline',
            'delta_auroc': hypoxia_vs_baseline['comparison']['improvement'],
            'p_value': hypoxia_vs_baseline['delong_test']['p_value'],
            'assumption': results['run']['notes']['delong_assumption'],
        },
    ]
    # Back-compat alias (some scripts use results['classification'])
    results['classification'] = results['classification_validation']

    json_path = reports_dir / f"validate_hypoxia_resistance_{tag}.json"
    write_json(json_path, results)

    def _fmt(x: Optional[float]) -> str:
        if x is None:
            return "NR"
        try:
            return f"{float(x):.2f}"
        except Exception:
            return "NR"

    md_lines = [
        "# Hypoxia Surrogate Validation for Platinum Resistance",
        "",
        f"**Generated:** {results['run']['generated_at']}",
        f"**Cohort:** {tag}",
        f"**Hypoxia score:** {args.hypoxia_score.upper()} (median split threshold={median_score:.3f})",
        f"**Endpoint:** {endpoint} ({args.time_col}/{args.event_col})",
        "",
        "## Cohort",
        f"- N total: {results['cohort']['n_total']}",
        f"- Platinum resistant: {results['cohort']['n_resistant']} ({(results['cohort']['n_resistant']/max(1, results['cohort']['n_total'])*100):.1f}%)",
        f"- High hypoxia: {results['cohort']['n_high_hypoxia']} ({(results['cohort']['n_high_hypoxia']/max(1, results['cohort']['n_total'])*100):.1f}%)",
        "",
        "## Survival (High vs Low hypoxia)",
        f"- Log-rank p: {p_lr if p_lr is not None else 'NA'}",
        f"- Median {endpoint} Low: {_fmt(med_low)} days",
        f"- Median {endpoint} High: {_fmt(med_high)} days",
        f"- Cox HR (High vs Low): {_fmt(hr)} (CI {_fmt(hr_lo)}–{_fmt(hr_hi)}), p={cox_p if cox_p is not None else 'NA'}",
        "",
        "## Classification (5-fold CV logistic regression)",
        f"- n analyzed: {results['classification_validation']['n_analyzed']}",
        f"- Baseline features: {', '.join(feature_baseline)}",
        "",
        "### AUROC",
        f"- Hypoxia: {hypoxia_result['auroc']:.3f} ({hypoxia_result['ci_lower']:.3f}-{hypoxia_result['ci_upper']:.3f})",
        f"- Baseline: {baseline_result['auroc']:.3f} ({baseline_result['ci_lower']:.3f}-{baseline_result['ci_upper']:.3f})",
        f"- Combined: {combined_result['auroc']:.3f} ({combined_result['ci_lower']:.3f}-{combined_result['ci_upper']:.3f})",
        "",
        "### DeLong comparisons (RUO approx)",
        f"- Combined vs baseline: Δ={combined_vs_baseline['comparison']['improvement']:+.3f}, p={combined_vs_baseline['delong_test']['p_value']:.4g}",
        f"- Hypoxia vs baseline: Δ={hypoxia_vs_baseline['comparison']['improvement']:+.3f}, p={hypoxia_vs_baseline['delong_test']['p_value']:.4g}",
        "",
        "## Figures",
        f"- KM curves: {km_fig_path.name}",
        f"- ROC curves: {roc_fig_path.name}",
    ]

    md_path = reports_dir / f"validate_hypoxia_resistance_{tag}.md"
    write_md(md_path, "\n".join(md_lines))

    print(f"   ✅ Saved JSON report: {json_path}")
    print(f"   ✅ Saved Markdown report: {md_path}")

    print("=" * 80)
    print("✅ HYPOXIA VALIDATION COMPLETE")
    print(f"   • Hypoxia AUROC: {hypoxia_result['auroc']:.3f}")
    print(f"   • Baseline AUROC: {baseline_result['auroc']:.3f}")
    print(f"   • Combined AUROC: {combined_result['auroc']:.3f}")
    print(f"   • Combined ΔAUROC: {combined_vs_baseline['comparison']['improvement']:+.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
