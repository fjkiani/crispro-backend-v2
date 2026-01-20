#!/usr/bin/env python3
"""D9: Stage III vs Stage IV subgroup AUROC.

Reads linked_patients.csv (already includes stage).
Writes:
- out/ddr_bin_tcga_ov/subgroup_auroc_stage.json
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from ddr_bin_analysis_utils import auroc_rank, parse_stage_group, platinum_to_y

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
OUT_DIR = REPO_ROOT / "oncology-coPilot" / "oncology-backend-minimal" / "scripts" / "validation" / "out" / "ddr_bin_tcga_ov"
LINKED_CSV = OUT_DIR / "linked_patients.csv"


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


def _compute(rows: List[Dict[str, str]]) -> Dict:
    y = []
    s = []
    for r in rows:
        yy = platinum_to_y((r.get("platinum_response") or "").strip())
        if yy is None:
            continue
        ss = _parse_float(r.get("ddr_bin"))
        if ss is None:
            continue
        y.append(int(yy))
        s.append(float(ss))

    y_arr = np.array(y, dtype=int)
    s_arr = np.array(s, dtype=float)
    if len(y_arr) < 10:
        return {"n": int(len(y_arr)), "auroc_resistant": None}
    auc = auroc_rank(y_arr, s_arr)
    return {"n": int(len(y_arr)), "auroc_resistant": float(auc)}


def main() -> int:
    if not LINKED_CSV.exists():
        raise FileNotFoundError(f"Missing: {LINKED_CSV}")

    with open(LINKED_CSV, newline="") as f:
        rows = list(csv.DictReader(f))

    stage3 = []
    stage4 = []
    unknown = []

    for r in rows:
        g = parse_stage_group(r.get("stage"))
        if g == "III":
            stage3.append(r)
        elif g == "IV":
            stage4.append(r)
        else:
            unknown.append(r)

    overall = _compute(rows)
    s3 = _compute(stage3)
    s4 = _compute(stage4)

    out = {
        "run_meta": {
            "linked_csv": str(LINKED_CSV.relative_to(REPO_ROOT)),
            "positive_class": "resistant_refractory",
        },
        "overall": overall,
        "stage_iii": {**s3, "n_rows": int(len(stage3))},
        "stage_iv": {**s4, "n_rows": int(len(stage4))},
        "unknown_stage": int(len(unknown)),
        "interpretation": "Subgroup AUROC by coarse stage bucket (III vs IV).",
    }

    out_path = OUT_DIR / "subgroup_auroc_stage.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Overall AUROC: {out['overall']['auroc_resistant']}")
    print(f"Stage III: n={out['stage_iii']['n']}, AUROC={out['stage_iii']['auroc_resistant']}")
    print(f"Stage IV: n={out['stage_iv']['n']}, AUROC={out['stage_iv']['auroc_resistant']}")
    print(f"Unknown stage rows: {out['unknown_stage']}")
    print(f"Wrote: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
