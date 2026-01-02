#!/usr/bin/env python3
"""Plot confidence-caps tier distribution under missingness.

Reads validate_confidence_caps_tcga_ucec_missingness_report.json and creates a bar plot.

RUO only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--report",
        default="biomarker_enriched_cohorts/reports/validate_confidence_caps_tcga_ucec_missingness_report.json",
        help="Path to validate_confidence_caps missingness report JSON",
    )
    ap.add_argument(
        "--out",
        default="biomarker_enriched_cohorts/figures/figure_confidence_caps_missingness_tiers.png",
        help="Output PNG path",
    )
    args = ap.parse_args()

    report_path = Path(args.report)
    out_path = Path(args.out)

    obj = json.loads(report_path.read_text(encoding="utf-8"))
    usable = obj.get("usable", {})
    n = int(usable.get("n") or 0)
    counts = usable.get("tier_counts", {})

    tiers = ["L2", "L1", "L0"]
    vals = [int(counts.get(t, 0)) for t in tiers]
    pcts = [(v / n * 100.0) if n else 0.0 for v in vals]

    plt.figure(figsize=(7, 4.2))
    bars = plt.bar(tiers, vals, color=["#2E7D32", "#F9A825", "#C62828"])
    plt.title(f"Completeness Tier Distribution (UCEC Missingness) — N={n}")
    plt.ylabel("Patients")
    plt.xlabel("Completeness tier")

    for b, v, pct in zip(bars, vals, pcts):
        plt.text(
            b.get_x() + b.get_width() / 2,
            b.get_height() + max(vals) * 0.02,
            f"{v}\n({pct:.1f}%)",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    plt.ylim(0, max(vals) * 1.20 if vals else 1)
    plt.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200)
    print(f"✅ wrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
