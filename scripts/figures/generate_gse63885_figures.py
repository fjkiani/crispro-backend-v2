#!/usr/bin/env python3
"""
Generate publication-quality figures for GSE63885 platinum resistance validation.

Outputs (to Publication-1 figures dir):
  - fig_gse63885_roc_mfap4.(png|pdf)
  - fig_gse63885_roc_emt_score.(png|pdf)
  - fig_gse63885_box_mfap4_by_platinum.(png|pdf)
  - fig_gse63885_box_emt_by_platinum.(png|pdf)
  - fig_gse63885_cohort_flow.(png|pdf)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
import os


ROOT = Path(__file__).resolve().parents[2]  # .../oncology-backend-minimal
DATA_DIR = ROOT / "data" / "external" / "GSE63885"
SERIES_MATRIX = DATA_DIR / "GSE63885_series_matrix.txt"
SAMPLE_ANN = DATA_DIR / "sample_annotations.csv"
PROBE_MAP = DATA_DIR / "emt_probe_mapping.json"

REPO_ROOT = ROOT.parents[1]  # .../crispr-assistant-main
PUB_DIR = REPO_ROOT / ".cursor" / "MOAT" / "SAE_INTELLIGENCE" / "Publication-1" / "SAE_RESISTANCE"
FIG_DIR = PUB_DIR / "figures"


def _ensure_dirs() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)


def _find_expr_start(lines: List[str]) -> int:
    for i, line in enumerate(lines):
        if line.startswith('"ID_REF"') or line.startswith("ID_REF"):
            return i
    raise RuntimeError("Could not find expression header row (ID_REF) in series matrix")


def load_expression() -> pd.DataFrame:
    lines = SERIES_MATRIX.read_text().split("\n")
    start = _find_expr_start(lines)
    df = pd.read_csv(SERIES_MATRIX, sep="\t", skiprows=start, index_col=0, comment="!")
    df = df.dropna(how="all")
    return df


def load_labels() -> pd.DataFrame:
    df = pd.read_csv(SAMPLE_ANN)
    # Normalize label field (keep NA rows for flow diagram)
    df["platinum_sensitivity"] = df["platinum_sensitivity"].astype(str).str.strip()
    df["is_labeled"] = ~df["platinum_sensitivity"].isin(["NA", ""])
    df["is_resistant"] = (df["platinum_sensitivity"] == "resistant").astype(int)
    return df


def zscore(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    sd = np.nanstd(v)
    if sd == 0 or np.isnan(sd):
        return v * 0.0
    return (v - np.nanmean(v)) / sd


def roc_curve_points(y: np.ndarray, s: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    # minimal ROC computation without sklearn dependency in figures script
    # (we still use sklearn for AUROC if available, but points are computed here)
    order = np.argsort(-s)  # descending score
    y = y[order]
    # thresholds at each unique score
    tps = np.cumsum(y == 1)
    fps = np.cumsum(y == 0)
    tp = tps / max(1, (y == 1).sum())
    fp = fps / max(1, (y == 0).sum())
    # include (0,0)
    return np.concatenate([[0.0], fp]), np.concatenate([[0.0], tp])


def auroc(y: np.ndarray, s: np.ndarray) -> float:
    try:
        from sklearn.metrics import roc_auc_score
        return float(roc_auc_score(y, s))
    except Exception:
        # fallback: trapezoid over ROC
        fpr, tpr = roc_curve_points(y, s)
        return float(np.trapezoid(tpr, fpr))


def save_fig(fig: plt.Figure, stem: str) -> None:
    fig.tight_layout()
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=250)
    fig.savefig(FIG_DIR / f"{stem}.pdf")
    plt.close(fig)


def main() -> int:
    _ensure_dirs()

    if os.getenv("DEBUG_PATHS") == "1":
        print(f"[DEBUG] ROOT={ROOT}")
        print(f"[DEBUG] DATA_DIR={DATA_DIR}")
        print(f"[DEBUG] SAMPLE_ANN={SAMPLE_ANN} exists={SAMPLE_ANN.exists()}")
        print(f"[DEBUG] SERIES_MATRIX={SERIES_MATRIX} exists={SERIES_MATRIX.exists()}")
        print(f"[DEBUG] PROBE_MAP={PROBE_MAP} exists={PROBE_MAP.exists()}")
        print(f"[DEBUG] FIG_DIR={FIG_DIR}")

    labels = load_labels()
    expr = load_expression()
    probe_map: Dict[str, List[str]] = json.loads(PROBE_MAP.read_text())

    # Only labeled samples for ROC/boxplots
    lab = labels[labels["is_labeled"]].copy()
    y = lab["is_resistant"].to_numpy().astype(int)
    sample_ids = lab["sample_id"].astype(str).tolist()

    # EMT genes via probe mapping (mean across probes)
    gene_vals: Dict[str, np.ndarray] = {}
    for gene, probes in probe_map.items():
        probes = [p for p in probes if p in expr.index]
        if not probes:
            continue
        v = expr.loc[probes, sample_ids].mean(axis=0).to_numpy(dtype=float)
        gene_vals[gene] = v

    # Build MFAP4 and EMT score (z-scored as in our analysis)
    mfap4 = zscore(gene_vals["MFAP4"])
    efemp1 = zscore(gene_vals["EFEMP1"])
    vim = zscore(gene_vals["VIM"])
    cdh1 = zscore(gene_vals["CDH1"])
    snai1 = zscore(gene_vals["SNAI1"])

    emt_score = (mfap4 + efemp1 + vim - cdh1) / 4.0

    # --- ROC: MFAP4 ---
    a_mfap4 = auroc(y, mfap4)
    fpr, tpr = roc_curve_points(y, mfap4)
    fig = plt.figure(figsize=(5.2, 4.4))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(fpr, tpr, linewidth=2.2, label=f"MFAP4 (AUROC={a_mfap4:.3f})")
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("GSE63885: MFAP4 predicts platinum resistance")
    ax.legend(loc="lower right", frameon=False)
    save_fig(fig, "fig_gse63885_roc_mfap4")

    # --- ROC: EMT score ---
    a_emt = auroc(y, emt_score)
    fpr, tpr = roc_curve_points(y, emt_score)
    fig = plt.figure(figsize=(5.2, 4.4))
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(fpr, tpr, linewidth=2.2, label=f"EMT score (AUROC={a_emt:.3f})")
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("GSE63885: EMT score predicts platinum resistance")
    ax.legend(loc="lower right", frameon=False)
    save_fig(fig, "fig_gse63885_roc_emt_score")

    # --- Boxplot: MFAP4 by label ---
    fig = plt.figure(figsize=(5.2, 4.4))
    ax = fig.add_subplot(1, 1, 1)
    groups = [mfap4[y == 0], mfap4[y == 1]]
    ax.boxplot(groups, tick_labels=["Sensitive", "Resistant"], showfliers=False)
    ax.set_ylabel("MFAP4 expression (z-score)")
    ax.set_title("GSE63885: MFAP4 by platinum sensitivity")
    save_fig(fig, "fig_gse63885_box_mfap4_by_platinum")

    # --- Boxplot: EMT score by label ---
    fig = plt.figure(figsize=(5.2, 4.4))
    ax = fig.add_subplot(1, 1, 1)
    groups = [emt_score[y == 0], emt_score[y == 1]]
    ax.boxplot(groups, tick_labels=["Sensitive", "Resistant"], showfliers=False)
    ax.set_ylabel("EMT score (z-score composite)")
    ax.set_title("GSE63885: EMT score by platinum sensitivity")
    save_fig(fig, "fig_gse63885_box_emt_by_platinum")

    # --- Cohort flow diagram (simple) ---
    n_total = len(labels)
    n_labeled = int(labels["is_labeled"].sum())
    n_res = int(labels.loc[labels["is_labeled"], "is_resistant"].sum())
    n_sens = n_labeled - n_res
    fig = plt.figure(figsize=(6.8, 3.4))
    ax = fig.add_subplot(1, 1, 1)
    ax.axis("off")
    txt = (
        "GSE63885 cohort flow\\n\\n"
        f"Total samples: {n_total}\\n"
        f"Labeled platinum sensitivity: {n_labeled}\\n"
        f"  Sensitive: {n_sens}\\n"
        f"  Resistant: {n_res}\\n"
        f"Unlabeled/NA: {n_total - n_labeled}"
    )
    ax.text(0.02, 0.95, txt, va="top", ha="left", fontsize=12)
    save_fig(fig, "fig_gse63885_cohort_flow")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


