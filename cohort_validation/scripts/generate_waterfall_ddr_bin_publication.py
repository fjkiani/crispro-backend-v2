#!/usr/bin/env python3
"""Generate publication-quality DDR_bin waterfall plot (D10).

Reads existing linked_patients.csv from:
  oncology-coPilot/oncology-backend-minimal/scripts/validation/out/ddr_bin_tcga_ov/linked_patients.csv

Writes:
  oncology-coPilot/oncology-backend-minimal/scripts/validation/out/ddr_bin_tcga_ov/waterfall_ddr_bin_publication.png

Conventions:
- Sort descending by DDR_bin (left = highest resistance score)
- Color: resistant/refractory = red, sensitive = blue
- Optional threshold line from report.json (optimal_threshold)
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
        pr = (r.get("platinum_response") or "").strip()
        if pr not in ("sensitive", "resistant", "refractory"):
            continue
        score = _parse_float(r.get("ddr_bin"))
        if score is None:
            continue
        usable.append({
            "patient_id": r.get("patient_id"),
            "ddr_bin": float(score),
            "platinum_response": pr,
        })

    if len(usable) < 10:
        raise RuntimeError(f"Too few usable rows: {len(usable)}")

    # Sort descending by DDR_bin
    usable_sorted = sorted(usable, key=lambda x: -x["ddr_bin"])

    # Pull threshold from report.json if present
    threshold = None
    if REPORT_JSON.exists():
        with open(REPORT_JSON) as f:
            rep = json.load(f)
        threshold = rep.get("platinum_response", {}).get("optimal_threshold")

    scores = [p["ddr_bin"] for p in usable_sorted]
    colors = []
    for p in usable_sorted:
        if p["platinum_response"] in ("resistant", "refractory"):
            colors.append("#E74C3C")  # red
        else:
            colors.append("#3498DB")  # blue

    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(len(scores))
    ax.bar(x, scores, color=colors, width=1.0, edgecolor="black", linewidth=0.2)

    ax.set_xlabel("Patients (sorted by DDR_bin, high→low)")
    ax.set_ylabel("DDR_bin (resistance score)")
    ax.set_title("DDR_bin Waterfall by Platinum Response\n(red=resistant/refractory, blue=sensitive)")

    # Legend
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(facecolor="#E74C3C", label="Resistant/Refractory"),
        Patch(facecolor="#3498DB", label="Sensitive"),
    ], loc="upper right")

    # Threshold line
    if threshold is not None:
        try:
            thr = float(threshold)
            ax.axhline(thr, color="black", linestyle="--", linewidth=1.2)
            ax.text(len(scores) * 0.02, thr + 0.01, f"optimal threshold={thr:.3f}", fontsize=9)
        except Exception:
            pass

    ax.grid(True, axis="y", alpha=0.25)
    ax.set_xlim([-0.5, len(scores) - 0.5])

    plt.tight_layout()

    out_png = OUT_DIR / "waterfall_ddr_bin_publication.png"
    plt.savefig(out_png, dpi=300)
    plt.close()

    print(f"Wrote: {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
