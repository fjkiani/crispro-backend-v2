#!/usr/bin/env python3
"""D8: Compare alternative aggregation methods for DDR_bin.

Computes patient scores from Tier3 cohort + diamond mapping, then AUROC for
platinum resistance for each aggregation.

Outputs:
- out/ddr_bin_tcga_ov/aggregation_comparison.json

NOTE: This is a research diagnostic. It does NOT change the validator.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ddr_bin_analysis_utils import auroc_rank, platinum_to_y, variant_ddr_scores

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
TIER3_COHORT = REPO_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "validation" / "sae_cohort" / "checkpoints" / "Tier3_validation_cohort.json"
DIAMOND_MAPPING = REPO_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "api" / "resources" / "sae_feature_mapping.true_sae_diamonds.v1.json"
OUT_DIR = REPO_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "scripts" / "validation" / "out" / "ddr_bin_tcga_ov"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(DIAMOND_MAPPING) as f:
        mapping = json.load(f)
    diamond_indices = [int(x["feature_index"]) for x in mapping.get("features", []) if "feature_index" in x]

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

    # Compute per-patient variant scores
    v_max_list = []
    v_sum_list = []
    for _, _, pdata in labeled:
        v_max, v_sum = variant_ddr_scores(pdata, diamond_indices)
        v_max_list.append(v_max)
        v_sum_list.append(v_sum)

    def score_max_of_max(v_max, v_sum):
        return float(max(v_max) if v_max else 0.0)

    def score_sum_of_max(v_max, v_sum):
        return float(sum(v_max) if v_max else 0.0)

    def score_top3_mean(v_max, v_sum):
        if not v_max:
            return 0.0
        vals = sorted(v_max)
        top = vals[-3:] if len(vals) >= 3 else vals
        return float(np.mean(top))

    def score_mean_of_sum(v_max, v_sum):
        # mean of per-variant sum across variants with any diamond hit
        if not v_sum:
            return 0.0
        return float(np.mean(v_sum))

    methods = {
        "max_of_max": score_max_of_max,
        "sum_of_max": score_sum_of_max,
        "top3_mean": score_top3_mean,
        "mean_of_sum": score_mean_of_sum,
    }

    results = []
    for name, fn in methods.items():
        scores = np.array([fn(v_max_list[i], v_sum_list[i]) for i in range(len(labeled))], dtype=float)
        auc = auroc_rank(y_arr, scores)
        results.append({
            "method": name,
            "auroc_resistant": float(auc),
            "n_labeled": int(len(labeled)),
            "notes": "higher score = more resistant" ,
        })

    results.sort(key=lambda x: x["auroc_resistant"], reverse=True)
    for i, r in enumerate(results, start=1):
        r["rank"] = i

    out = {
        "run_meta": {
            "tier3": str(TIER3_COHORT.relative_to(REPO_ROOT)),
            "diamonds": str(DIAMOND_MAPPING.relative_to(REPO_ROOT)),
            "positive_class": "resistant_refractory",
        },
        "results": results,
        "interpretation": "Compares alternative ways to aggregate per-variant diamond hits into a patient-level resistance score.",
    }

    out_path = OUT_DIR / "aggregation_comparison.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote: {out_path}")
    print("Ranking:")
    for r in results:
        print(f"  #{r['rank']} {r['method']}: AUROC={r['auroc_resistant']:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
