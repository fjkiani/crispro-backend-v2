#!/usr/bin/env python3
"""Competitive benchmark for DDR_bin (Phase 2 / A4).

Computes AUROC for predicting platinum resistance (resistant/refractory vs sensitive)
for:
- DDR_bin (from linked_patients.csv)
- gene_ddr flag (from linked_patients.csv; reported in both orientations)
- TP53 status (from cBioPortal mutations)
- TMB proxy (mutation count / exome_mb)

Writes:
- out/ddr_bin_tcga_ov/competitive_benchmark.json
- out/ddr_bin_tcga_ov/competitive_benchmark.png

Designed to run offline & deterministically.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
CBIOPORTAL_DATASET = REPO_ROOT / "data" / "benchmarks" / "cbioportal_trial_datasets_latest.json"
OUT_DIR = REPO_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "scripts" / "validation" / "out" / "ddr_bin_tcga_ov"
LINKED_CSV = OUT_DIR / "linked_patients.csv"
REPORT_JSON = OUT_DIR / "report.json"

EXOME_SIZE_MB_DEFAULT = 30.0


def _auroc_rank(y: np.ndarray, score: np.ndarray) -> float:
    """AUROC using Mann–Whitney rank formulation."""
    y = np.asarray(y).astype(int)
    score = np.asarray(score).astype(float)
    pos = score[y == 1]
    neg = score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")

    allv = np.concatenate([pos, neg])
    ranks = allv.argsort().argsort().astype(float) + 1.0
    rpos = ranks[: len(pos)].sum()
    auc = (rpos - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))
    return float(auc)


def _load_cbioportal_ov_patients() -> Dict[str, Dict]:
    if not CBIOPORTAL_DATASET.exists():
        raise FileNotFoundError(f"Missing cBioPortal dataset: {CBIOPORTAL_DATASET}")

    with open(CBIOPORTAL_DATASET) as f:
        studies = json.load(f)

    ov = None
    for s in studies:
        if s.get("study_id") == "ov_tcga":
            ov = s
            break

    if ov is None:
        raise ValueError("ov_tcga study not found in cBioPortal dataset")

    patients = {p.get("patient_id"): p for p in ov.get("patients", []) if p.get("patient_id")}
    return patients


def _extract_mutated_genes(mutations) -> List[str]:
    genes = set()
    if not mutations:
        return []
    for mut in mutations:
        if isinstance(mut, dict):
            g = mut.get("gene")
            if g:
                genes.add(str(g).upper())
        elif isinstance(mut, str):
            genes.add(mut.upper())
    return sorted(genes)


def _read_linked_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing linked_patients.csv: {path}")
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _parse_float(x: Optional[str]) -> Optional[float]:
    if x is None:
        return None
    x = str(x).strip()
    if x == "" or x.lower() == "nan":
        return None
    try:
        return float(x)
    except ValueError:
        return None


def _platinum_label_to_y(platinum_response: str) -> Optional[int]:
    if platinum_response not in ("sensitive", "resistant", "refractory"):
        return None
    return 1 if platinum_response in ("resistant", "refractory") else 0


def _compute_metrics(name: str, y: np.ndarray, score: np.ndarray) -> Dict:
    auc_res = _auroc_rank(y, score)
    # Explicit symmetric view (sensitive) for clarity
    auc_sens = _auroc_rank(1 - y, -score)
    return {
        "name": name,
        "n": int(len(y)),
        "auroc_resistant": float(auc_res),
        "auroc_sensitive": float(auc_sens),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    linked_rows = _read_linked_csv(LINKED_CSV)
    cbio_patients = _load_cbioportal_ov_patients()

    # Build aligned arrays
    y_list: List[int] = []
    ddr_bin_list: List[float] = []
    gene_ddr_list: List[int] = []
    tp53_list: List[int] = []
    mut_count_list: List[int] = []

    missing_cbio = 0

    for r in linked_rows:
        pid = r.get("patient_id")
        if not pid:
            continue

        y = _platinum_label_to_y((r.get("platinum_response") or "").strip())
        if y is None:
            continue

        ddr_bin = _parse_float(r.get("ddr_bin"))
        gene_ddr = _parse_float(r.get("gene_ddr"))
        if ddr_bin is None or gene_ddr is None:
            continue

        cb = cbio_patients.get(pid)
        if cb is None:
            missing_cbio += 1
            muts = []
        else:
            muts = cb.get("mutations", [])

        genes = _extract_mutated_genes(muts)
        tp53 = 1 if "TP53" in genes else 0
        mut_count = len(muts) if muts else 0

        y_list.append(int(y))
        ddr_bin_list.append(float(ddr_bin))
        gene_ddr_list.append(int(float(gene_ddr)))
        tp53_list.append(int(tp53))
        mut_count_list.append(int(mut_count))

    y_arr = np.array(y_list, dtype=int)
    ddr_bin_arr = np.array(ddr_bin_list, dtype=float)

    # gene_ddr orientation: report both; use the better one as competitor for resistance
    gene_ddr_arr = np.array(gene_ddr_list, dtype=float)
    gene_ddr_resistance_score = 1.0 - gene_ddr_arr

    tp53_arr = np.array(tp53_list, dtype=float)
    mut_count_arr = np.array(mut_count_list, dtype=float)
    tmb_arr = mut_count_arr / EXOME_SIZE_MB_DEFAULT

    # DDR_bin is already oriented as resistance score (higher => more resistant)
    m_ddr = _compute_metrics("DDR_bin (TRUE SAE)", y_arr, ddr_bin_arr)
    m_gene_inv = _compute_metrics("Gene DDR flag (1-gene_ddr)", y_arr, gene_ddr_resistance_score)
    m_gene_raw = _compute_metrics("Gene DDR flag (raw gene_ddr)", y_arr, gene_ddr_arr)
    m_tp53 = _compute_metrics("TP53 status", y_arr, tp53_arr)
    m_tmb = _compute_metrics(f"TMB (mut_count/{EXOME_SIZE_MB_DEFAULT}mb)", y_arr, tmb_arr)

    # Select gene competitor orientation as the best AUROC(resistant) (fair baseline)
    gene_best = m_gene_inv if m_gene_inv["auroc_resistant"] >= m_gene_raw["auroc_resistant"] else m_gene_raw

    # Threshold from report if present
    optimal_threshold = None
    if REPORT_JSON.exists():
        with open(REPORT_JSON) as f:
            rep = json.load(f)
        optimal_threshold = rep.get("platinum_response", {}).get("optimal_threshold")

    benchmark = {
        "run_meta": {
            "linked_csv": str(LINKED_CSV.relative_to(REPO_ROOT)),
            "cbioportal_dataset": str(CBIOPORTAL_DATASET.relative_to(REPO_ROOT)),
            "missing_cbioportal_records": int(missing_cbio),
            "exome_size_mb": EXOME_SIZE_MB_DEFAULT,
            "positive_class": "resistant_refractory",
            "optimal_threshold_ddr_bin": optimal_threshold,
        },
        "metrics": {
            "ddr_bin": m_ddr,
            "gene_ddr_best": gene_best,
            "gene_ddr_raw": m_gene_raw,
            "gene_ddr_inverted": m_gene_inv,
            "tp53": m_tp53,
            "tmb": m_tmb,
        },
        "deltas": {
            "ddr_bin_minus_gene_ddr_best": float(m_ddr["auroc_resistant"] - gene_best["auroc_resistant"]),
            "ddr_bin_minus_tp53": float(m_ddr["auroc_resistant"] - m_tp53["auroc_resistant"]),
            "ddr_bin_minus_tmb": float(m_ddr["auroc_resistant"] - m_tmb["auroc_resistant"]),
        },
        "interpretation": (
            "Higher DDR_bin predicts platinum resistance (resistant/refractory). "
            "Benchmark compares DDR_bin vs gene flag and negative controls (TP53, TMB)."
        ),
    }

    out_json = OUT_DIR / "competitive_benchmark.json"
    with open(out_json, "w") as f:
        json.dump(benchmark, f, indent=2)

    # Plot bar chart
    items = [
        ("DDR_bin", m_ddr["auroc_resistant"], "#2c3e50"),
        ("Gene DDR", gene_best["auroc_resistant"], "#7f8c8d"),
        ("TP53", m_tp53["auroc_resistant"], "#c0392b"),
        ("TMB", m_tmb["auroc_resistant"], "#8e44ad"),
    ]

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    names = [x[0] for x in items]
    aucs = [x[1] for x in items]
    colors = [x[2] for x in items]

    ax.bar(names, aucs, color=colors, edgecolor="black", linewidth=0.8)
    ax.axhline(0.5, color="black", linestyle="--", linewidth=1.0, alpha=0.7)
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("AUROC (predict resistant/refractory)")
    ax.set_title("Competitive Benchmark (Platinum Resistance)")

    for i, v in enumerate(aucs):
        ax.text(i, v + 0.02, f"{v:.3f}", ha="center", va="bottom", fontsize=10)

    ax.grid(True, axis="y", alpha=0.25)
    plt.tight_layout()

    out_png = OUT_DIR / "competitive_benchmark.png"
    plt.savefig(out_png, dpi=300)
    plt.close()

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_png}")

    # Print key headline
    print("\nHeadline:")
    print(f"  DDR_bin AUROC(resistant): {m_ddr['auroc_resistant']:.3f}")
    print(f"  Gene DDR (best) AUROC(resistant): {gene_best['auroc_resistant']:.3f}")
    print(f"  Δ DDR_bin - Gene DDR: {benchmark['deltas']['ddr_bin_minus_gene_ddr_best']:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
