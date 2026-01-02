#!/usr/bin/env python3
"""Confidence caps validation (safety mechanism) via completeness tiers.

We can't validate "confidence" directly without model outputs, but we *can* validate
that completeness tiers are computable and quantify endpoint variability per tier.

This script defines tiers using biomarker availability:
- L0: missing TMB AND missing MSI scores AND missing aneuploidy/FGA
- L2: has at least K of {TMB, MSI (either score), aneuploidy+FGA}
- L1: everything else

Outputs:
- reports/validate_confidence_caps_report.json
- reports/validate_confidence_caps_report.md
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd

from _validation_utils import CohortPaths, coverage_counts, load_tcga_ov_enriched_v2, now_utc_iso, sha256_file, write_json, write_md


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--tag", default=os.environ.get("COHORT_TAG"), help="Tag/label for outputs (default: COHORT_TAG env or cohort filename stem)")
    ap.add_argument("--k", type=int, default=2, help="How many biomarkers present to call L2")
    ap.add_argument("--endpoint", choices=["os_days", "pfs_days"], default="os_days")
    args = ap.parse_args()

    paths = CohortPaths(root=Path(args.root).resolve())
    tag = args.tag or paths.cohort_json.stem
    tag = str(tag)
    df = load_tcga_ov_enriched_v2(paths.cohort_json)

    # biomarker presence flags
    has_tmb = df["tmb"].notna()
    has_msi = df[["msi_score_mantis", "msi_sensor_score"]].notna().any(axis=1)
    has_hrd_proxy_inputs = df[["aneuploidy_score", "fraction_genome_altered"]].notna().all(axis=1)

    biomarker_count = (has_tmb.astype(int) + has_msi.astype(int) + has_hrd_proxy_inputs.astype(int))

    # tiers
    df["tier"] = "L1"
    df.loc[(~has_tmb) & (~has_msi) & (~has_hrd_proxy_inputs), "tier"] = "L0"
    df.loc[biomarker_count >= args.k, "tier"] = "L2"

    # endpoint variability per tier
    endpoint = args.endpoint
    sub = df[[endpoint, "tier"]].dropna()

    stats = {}
    for tier in ["L0", "L1", "L2"]:
        vals = sub.loc[sub["tier"] == tier, endpoint].astype(float)
        if len(vals) == 0:
            continue
        stats[tier] = {
            "n": int(len(vals)),
            "median": float(np.median(vals)),
            "iqr": float(np.percentile(vals, 75) - np.percentile(vals, 25)),
            "mean": float(np.mean(vals)),
            "std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
            "cv": float((np.std(vals, ddof=1) / np.mean(vals))) if (len(vals) > 1 and np.mean(vals) != 0) else None,
        }

    counts = sub["tier"].value_counts().to_dict()

    report = {
        "run": {"generated_at": now_utc_iso(), "script": str(Path(__file__).name), "root": str(paths.root), "tag": tag},
        "inputs": {
            "cohort_path": str(paths.cohort_json),
            "cohort_sha256": sha256_file(paths.cohort_json),
            "endpoint": endpoint,
            "tier_definition": {
                "L0": "missing TMB AND missing MSI scores AND missing aneuploidy+FGA",
                "L2": f"at least {args.k} of [TMB, MSI (either score), aneuploidy+FGA] present",
                "L1": "else",
            },
        },
        "coverage": coverage_counts(df, [endpoint, "tmb", "msi_score_mantis", "msi_sensor_score", "aneuploidy_score", "fraction_genome_altered"]),
        "usable": {"n": int(len(sub)), "tier_counts": counts},
        "variability": stats,
        "notes": [
            "This validates that completeness tiers are computable from available biomarkers.",
            "It does not validate a specific confidence cap number (0.4/0.6); those are safety-policy caps.",
        ],
    }

    out_json = paths.reports_dir / f"validate_confidence_caps_{tag}_report.json"
    write_json(out_json, report)

    md_lines = [
        "# Confidence Caps — CompletenTier Variability Check ({tag})",
        "",
        f"- **Cohort**: `{paths.cohort_json}` (sha256: `{report['inputs']['cohort_sha256']}`)",
      f"- **Endpoint**: `{endpoint}`",
        f"- **L2 rule**: ≥{args.k} biomarkers present",
        "",
        "## Tier counts (usable rows)",
        "",
        f"{report['usable']['tier_counts']}",
        "",
        "## Variability by tier",
        "",
    ]

    for tier, s in report["variability"].items():
        md_lines.extend(
            [
                f"### {tier}",
                f"- n: {s['n']}",
                f"- median: {s['median']}",
                f"- IQR: {s['iqr']}",
                f"- mean: {s['mean']}",
                f"- std: {s['std']}",
                f"- CV: {s['cv']}",
                "",
            ]
        )

    md_lines.extend(
        [
            "## Notes",
            "- These tiers are used to justify conservative confidence caps on incomplete data.",
            "",
        ]
    )

    out_md = paths.reports_dir / f"validate_confidence_caps_{tag}_report.md"
    write_md(out_md, "\n".join(md_lines))

    print(f"✅ Wrote {out_json}")
    print(f"✅ Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
