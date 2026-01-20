#!/usr/bin/env python3
"""D7: DDR_bin sparsity + nonzero-only AUROC + publication histogram.

Reads:
- out/ddr_bin_tcga_ov/linked_patients.csv
- out/ddr_bin_tcga_ov/report.json (for overall AUROC)

Writes:
- out/ddr_bin_tcga_ov/ddr_bin_distribution_analysis.json
- out/ddr_bin_tcga_ov/ddr_bin_histogram_publication.png
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ddr_bin_analysis_utils import auroc_rank, platinum_to_y

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
OUT_DIR = REPO_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "scripts" / "validation" / "out" / "ddr_bin_tcga_ov"
LINKED_CSV = OUT_DIR / "linked_patients.csv"
REPORT_JSON = OUT_DIR / "report.json"


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


def main() -> int:
    if not LINKED_CSV.exists():
        raise FileNotFoundError(f"Missing: {LINKED_CSV}")

    rows: List[Dict[str, str]] = []
    with open(LINKED_CSV, newline="") as f:
        rows = list(csv.DictReader(f))

    usable = []
    for r in rows:
        y = platinum_to_y((r.get("platinum_response") or "").strip())
        if y is None:
            continue
        s = _parse_float(r.get("ddr_bin"))
        if s is None:
            continue
        cov = _parse_float(r.get("ddr_bin_coverage"))
        nvar = _parse_float(r.get("ddr_bin_num_variants"))
        usable.append({
            "y": int(y),
            "ddr_bin": float(s),
            "coverage": float(cov) if cov is not None else None,
            "num_variants": int(nvar) if nvar is not None else None,
        })

    y_arr = np.array([u["y"] for u in usable], dtype=int)
    s_arr = np.array([u["ddr_bin"] for u in usable], dtype=float)

    n_total = int(len(usable))
    n_zero = int(np.sum(s_arr == 0.0))
    pct_zero = float(n_zero / n_total * 100.0) if n_total else 0.0

    # Nonzero-only AUROC
    mask_nz = s_arr > 0
    auroc_nonzero = None
    if int(np.sum(mask_nz)) >= 10:
        auroc_nonzero = float(auroc_rank(y_arr[mask_nz], s_arr[mask_nz]))

    # Overall AUROC from report
    auroc_all = None
    if REPORT_JSON.exists():
        with open(REPORT_JSON) as f:
            rep = json.load(f)
        auroc_all = rep.get("platinum_response", {}).get("auroc_resistant")

    # Coverage stats
    covs = np.array([u["coverage"] for u in usable if u["coverage"] is not None], dtype=float)
    nvars = np.array([u["num_variants"] for u in usable if u["num_variants"] is not None], dtype=float)

    analysis = {
        "n_labeled": n_total,
        "n_zero": n_zero,
        "pct_zero": pct_zero,
        "auroc_all": float(auroc_all) if auroc_all is not None else None,
        "auroc_nonzero_only": auroc_nonzero,
        "coverage": {
            "mean_ddr_bin_coverage": float(np.mean(covs)) if len(covs) else None,
            "median_ddr_bin_coverage": float(np.median(covs)) if len(covs) else None,
            "pct_patients_coverage_gt_0": float(np.mean(covs > 0) * 100.0) if len(covs) else None,
            "mean_num_variants": float(np.mean(nvars)) if len(nvars) else None,
            "median_num_variants": float(np.median(nvars)) if len(nvars) else None,
        },
        "interpretation": "Sparsity reflects diamond hits missing from top-K variant features; nonzero-only AUROC quantifies signal conditional on coverage.",
    }

    out_json = OUT_DIR / "ddr_bin_distribution_analysis.json"
    with open(out_json, "w") as f:
        json.dump(analysis, f, indent=2)

    # Publication histogram
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.hist(s_arr, bins=30, edgecolor="black", alpha=0.8)
    ax.set_xlabel("DDR_bin (resistance score)")
    ax.set_ylabel("Patients")
    ax.set_title("DDR_bin distribution (Tier-3 labeled cohort)")
    ax.grid(True, axis="y", alpha=0.25)
    ax.axvline(float(np.median(s_arr)), color="black", linestyle="--", linewidth=1.2)
    ax.text(0.02, 0.95, f"n={n_total} | zeros={pct_zero:.1f}%", transform=ax.transAxes, va="top")
    plt.tight_layout()

    out_png = OUT_DIR / "ddr_bin_histogram_publication.png"
    plt.savefig(out_png, dpi=300)
    plt.close()

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_png}")
    print(f"Zeros: {n_zero}/{n_total} ({pct_zero:.1f}%)")
    if auroc_all is not None:
        print(f"AUROC all: {float(auroc_all):.3f}")
    if auroc_nonzero is not None:
        print(f"AUROC nonzero-only: {float(auroc_nonzero):.3f} (n={int(np.sum(mask_nz))})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
