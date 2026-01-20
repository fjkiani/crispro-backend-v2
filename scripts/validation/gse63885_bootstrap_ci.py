#!/usr/bin/env python3
"""
Bootstrap confidence intervals and PR-AUC for GSE63885 MFAP4 / EMT biomarkers.

This strengthens the manuscript by reporting uncertainty (AUROC CI) and imbalance-aware PR-AUC.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]  # oncology-backend-minimal
DATA_DIR = ROOT / "data" / "external" / "GSE63885"
SERIES_MATRIX = DATA_DIR / "GSE63885_series_matrix.txt"
SAMPLE_ANN = DATA_DIR / "sample_annotations.csv"
PROBE_MAP = DATA_DIR / "emt_probe_mapping.json"
OUT_JSON = DATA_DIR / "emt_bootstrap_ci_results.json"


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


def zscore(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    sd = np.nanstd(v)
    if sd == 0 or np.isnan(sd):
        return v * 0.0
    return (v - np.nanmean(v)) / sd


def auroc(y: np.ndarray, s: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def pr_auc(y: np.ndarray, s: np.ndarray) -> float:
    from sklearn.metrics import average_precision_score
    return float(average_precision_score(y, s))


def bootstrap_metrics(y: np.ndarray, s: np.ndarray, n_boot: int = 5000, seed: int = 7) -> Dict[str, Dict[str, float]]:
    rng = np.random.default_rng(seed)
    n = len(y)
    aucs = []
    pras = []
    # Stratified bootstrap: sample within class to avoid degenerate resamples
    idx0 = np.where(y == 0)[0]
    idx1 = np.where(y == 1)[0]
    for _ in range(n_boot):
        b0 = rng.choice(idx0, size=len(idx0), replace=True)
        b1 = rng.choice(idx1, size=len(idx1), replace=True)
        b = np.concatenate([b0, b1])
        aucs.append(auroc(y[b], s[b]))
        pras.append(pr_auc(y[b], s[b]))
    aucs = np.array(aucs)
    pras = np.array(pras)
    def ci(arr):
        return {
            "mean": float(arr.mean()),
            "p025": float(np.quantile(arr, 0.025)),
            "p50": float(np.quantile(arr, 0.50)),
            "p975": float(np.quantile(arr, 0.975)),
        }
    return {"auroc": ci(aucs), "prauc": ci(pras)}


def main() -> int:
    labels = pd.read_csv(SAMPLE_ANN)
    labels["platinum_sensitivity"] = labels["platinum_sensitivity"].astype(str).str.strip()
    labeled = labels[~labels["platinum_sensitivity"].isin(["NA", ""])].copy()
    y = (labeled["platinum_sensitivity"] == "resistant").astype(int).to_numpy()
    sample_ids = labeled["sample_id"].astype(str).tolist()

    expr = load_expression()
    probe_map: Dict[str, List[str]] = json.loads(PROBE_MAP.read_text())

    gene_vals: Dict[str, np.ndarray] = {}
    for gene, probes in probe_map.items():
        probes = [p for p in probes if p in expr.index]
        if not probes:
            continue
        gene_vals[gene] = expr.loc[probes, sample_ids].mean(axis=0).to_numpy(dtype=float)

    mfap4 = zscore(gene_vals["MFAP4"])
    efemp1 = zscore(gene_vals["EFEMP1"])
    vim = zscore(gene_vals["VIM"])
    cdh1 = zscore(gene_vals["CDH1"])
    snai1 = zscore(gene_vals["SNAI1"])
    emt_score = (mfap4 + efemp1 + vim - cdh1) / 4.0

    out = {
        "dataset": "GSE63885",
        "counts": {"n": int(len(y)), "n_pos_resistant": int(y.sum()), "n_neg_sensitive": int((y == 0).sum())},
        "point_estimates": {
            "auroc_mfap4": auroc(y, mfap4),
            "prauc_mfap4": pr_auc(y, mfap4),
            "auroc_emt_score": auroc(y, emt_score),
            "prauc_emt_score": pr_auc(y, emt_score),
            "auroc_snai1": auroc(y, snai1),
            "prauc_snai1": pr_auc(y, snai1),
        },
        "bootstrap": {
            "mfap4": bootstrap_metrics(y, mfap4),
            "emt_score": bootstrap_metrics(y, emt_score),
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"Wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


