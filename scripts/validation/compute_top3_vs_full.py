#!/usr/bin/env python3
"""D6: Compare top-3 diamond composite vs full DDR_bin AUROC.

Uses top-3 diamonds from per_diamond_auroc.json.
Writes:
- out/ddr_bin_tcga_ov/top3_vs_full_comparison.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ddr_bin_analysis_utils import auroc_rank, patient_diamond_value, platinum_to_y

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
TIER3_COHORT = REPO_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "validation" / "sae_cohort" / "checkpoints" / "Tier3_validation_cohort.json"
OUT_DIR = REPO_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "scripts" / "validation" / "out" / "ddr_bin_tcga_ov"
PER_DIAMOND = OUT_DIR / "per_diamond_auroc.json"
REPORT_JSON = OUT_DIR / "report.json"


def main() -> int:
    if not PER_DIAMOND.exists():
        raise FileNotFoundError(f"Missing: {PER_DIAMOND}")

    with open(PER_DIAMOND) as f:
        pd = json.load(f)
    top3 = [int(r["feature_index"]) for r in pd.get("results", [])[:3]]
    if len(top3) != 3:
        raise RuntimeError(f"Could not determine top3 diamonds: {top3}")

    with open(TIER3_COHORT) as f:
        tier3 = json.load(f)
    patients = tier3.get("data", {})

    labeled = []
    for pid, pdata in patients.items():
        y = platinum_to_y(pdata.get("outcome"))
        if y is None:
            continue
        labeled.append((pid, int(y), pdata))

    y_arr = np.array([x[1] for x in labeled], dtype=int)

    # Top-3 composite = max of the 3 patient-level diamond values
    top3_scores = []
    for _, _, pdata in labeled:
        vals = [patient_diamond_value(pdata, d) for d in top3]
        top3_scores.append(float(max(vals) if vals else 0.0))

    top3_arr = np.array(top3_scores, dtype=float)
    auroc_top3 = auroc_rank(y_arr, top3_arr)

    # Full AUROC from Phase 1 report
    auroc_full = None
    if REPORT_JSON.exists():
        with open(REPORT_JSON) as f:
            rep = json.load(f)
        auroc_full = rep.get("platinum_response", {}).get("auroc_resistant")

    out = {
        "run_meta": {
            "per_diamond": str(PER_DIAMOND.relative_to(REPO_ROOT)),
            "tier3": str(TIER3_COHORT.relative_to(REPO_ROOT)),
            "positive_class": "resistant_refractory",
            "n_labeled": int(len(labeled)),
        },
        "top3_features": top3,
        "auroc_top3": float(auroc_top3),
        "auroc_full_9": float(auroc_full) if auroc_full is not None else None,
        "delta_full_minus_top3": float(auroc_full - auroc_top3) if auroc_full is not None else None,
        "recommendation": None,
    }

    if out["auroc_full_9"] is not None:
        if abs(out["delta_full_minus_top3"]) < 0.02:
            out["recommendation"] = "Use top-3 diamonds for production (within 0.02 AUROC of full)"
        else:
            out["recommendation"] = "Keep full 9-diamond DDR_bin (top-3 loses >0.02 AUROC)"

    out_path = OUT_DIR / "top3_vs_full_comparison.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Top-3 diamonds: {top3}")
    print(f"AUROC top-3: {auroc_top3:.3f}")
    if auroc_full is not None:
        print(f"AUROC full-9: {float(auroc_full):.3f}")
        print(f"Δ(full - top3): {float(auroc_full - auroc_top3):.3f}")
        print(f"Recommendation: {out['recommendation']}")
    print(f"Wrote: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
