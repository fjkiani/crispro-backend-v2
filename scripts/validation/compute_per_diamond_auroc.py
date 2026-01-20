#!/usr/bin/env python3
"""D5: Per-diamond AUROC ranking (platinum resistance).

Outputs:
- out/ddr_bin_tcga_ov/per_diamond_auroc.json
- out/ddr_bin_tcga_ov/per_diamond_auroc.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from ddr_bin_analysis_utils import auroc_rank, patient_diamond_value, platinum_to_y

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

    rows = []
    for pid, pdata in patients.items():
        y = platinum_to_y(pdata.get("outcome"))
        if y is None:
            continue
        rows.append((pid, int(y), pdata))

    if len(rows) < 10:
        raise RuntimeError(f"Too few labeled patients: {len(rows)}")

    y_arr = np.array([r[1] for r in rows], dtype=int)

    results = []
    for idx in diamond_indices:
        scores = np.array([patient_diamond_value(r[2], idx) for r in rows], dtype=float)
        auc = auroc_rank(y_arr, scores)
        n_nonzero = int(np.sum(scores > 0))
        results.append({
            "feature_index": int(idx),
            "auroc_resistant": float(auc),
            "n_patients": int(len(scores)),
            "n_nonzero": n_nonzero,
            "pct_nonzero": float(n_nonzero / len(scores) * 100.0),
        })

    results.sort(key=lambda x: x["auroc_resistant"], reverse=True)
    for i, r in enumerate(results, start=1):
        r["rank"] = i

    out_json = OUT_DIR / "per_diamond_auroc.json"
    with open(out_json, "w") as f:
        json.dump({
            "run_meta": {
                "tier3": str(TIER3_COHORT.relative_to(REPO_ROOT)),
                "diamonds": str(DIAMOND_MAPPING.relative_to(REPO_ROOT)),
                "positive_class": "resistant_refractory",
                "n_labeled": int(len(rows)),
            },
            "results": results,
        }, f, indent=2)

    out_csv = OUT_DIR / "per_diamond_auroc.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rank", "feature_index", "auroc_resistant", "n_nonzero", "pct_nonzero", "n_patients"])
        w.writeheader()
        for r in results:
            w.writerow({k: r[k] for k in w.fieldnames})

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_csv}")
    print("Top 5 diamonds by AUROC:")
    for r in results[:5]:
        print(f"  #{r['rank']:>2} feature {r['feature_index']}: AUROC={r['auroc_resistant']:.3f}, nonzero={r['n_nonzero']}/{r['n_patients']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
