#!/usr/bin/env python3
"""Validate simple multi-modal risk tiers (HRD proxy + TMB + MSI + BRCA somatic).

Defines (example, conservative):
- Favorable: BRCA somatic present OR (HRD-High AND (TMB-high OR MSI-H))
- Intermediate: HRD-High OR TMB-high OR MSI-H
- Unfavorable: none of the above

Outputs:
- reports/validate_multimodal_risk_report.json
- reports/validate_multimodal_risk_report.md
- figures/figure_multimodal_risk_os.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from lifelines import KaplanMeierFitter
from lifelines.statistics import multivariate_logrank_test

from _validation_utils import (
    CohortPaths,
    coverage_counts,
    load_tcga_ov_enriched_v2,
    now_utc_iso,
    sha256_file,
    write_json,
    write_md,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--tmb_threshold", type=float, default=20.0)
    ap.add_argument("--hrd_high_label", default="HRD-High")
    ap.add_argument("--time_col", choices=["os_days", "pfs_days"], default="os_days")
    ap.add_argument("--event_col", choices=["os_event", "pfs_event"], default="os_event")
    args = ap.parse_args()

    paths = CohortPaths(root=Path(args.root).resolve())
    df = load_tcga_ov_enriched_v2(paths.cohort_json)

    # Features
    df["tmb_high"] = np.where(df["tmb"].isna(), np.nan, df["tmb"] >= args.tmb_threshold)
    df["msi_h"] = df["msi_status"].map(lambda x: True if x == "MSI-H" else (False if x == "MSS" else np.nan))
    df["hrd_high"] = df["hrd_proxy"].map(lambda x: True if x == args.hrd_high_label else (False if isinstance(x, str) else np.nan))
    df["brca_somatic_present"] = df["brca_somatic"].map(lambda x: True if x in ("BRCA1", "BRCA2") else False)

    # Define tiers
    def tier(row) -> str:
        tmb_high = row.get("tmb_high") is True
        msi_h = row.get("msi_h") is True
        hrd_high = row.get("hrd_high") is True
        brca = bool(row.get("brca_somatic_present"))

        if brca or (hrd_high and (tmb_high or msi_h)):
            return "Favorable"
        if hrd_high or tmb_high or msi_h:
            return "Intermediate"
        return "Unfavorable"

    df["risk_tier"] = df.apply(tier, axis=1)

    # Survival subset
    sub = df[[args.time_col, args.event_col, "risk_tier"]].dropna()
    sub[args.event_col] = sub[args.event_col].astype(bool)

    mv = multivariate_logrank_test(sub[args.time_col].astype(float), sub["risk_tier"], sub[args.event_col])

    plt.figure(figsize=(6.5, 4.5))
    ax = plt.gca()

    order = ["Favorable", "Intermediate", "Unfavorable"]
    km_medians = {}

    for label in order:
        grp = sub[sub["risk_tier"] == label]
        if len(grp) == 0:
            continue
        kmf = KaplanMeierFitter().fit(
            grp[args.time_col].astype(float),
            event_observed=grp[args.event_col].astype(bool),
            label=f"{label} (n={len(grp)})",
        )
        kmf.plot_survival_function(ax=ax, ci_show=True)
        km_medians[label] = float(kmf.median_survival_time_) if kmf.median_survival_time_ is not None else None

    ax.set_title(f"TCGA-OV {args.time_col.replace('_days','').upper()} by Multi-modal Risk Tier")
    ax.set_xlabel("Days")
    ax.set_ylabel("Survival probability")
    ax.grid(True, alpha=0.25)
    ax.text(0.98, 0.02, f"log-rank p={float(mv.p_value):.3g}", transform=ax.transAxes, ha="right", va="bottom", fontsize=9)

    fig_path = paths.figures_dir / f"figure_multimodal_risk_{'os' if args.time_col=='os_days' else 'pfs'}.png"
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(fig_path, dpi=300)
    plt.close()

    counts = sub["risk_tier"].value_counts().to_dict()

    report = {
        "run": {"generated_at": now_utc_iso(), "script": str(Path(__file__).name), "root": str(paths.root)},
        "inputs": {
            "cohort_path": str(paths.cohort_json),
            "cohort_sha256": sha256_file(paths.cohort_json),
            "endpoint": {"time_col": args.time_col, "event_col": args.event_col},
            "tmb_threshold": args.tmb_threshold,
            "hrd_high_label": args.hrd_high_label,
            "tier_definition": {
                "Favorable": "BRCA_somatic OR (HRD-High AND (TMB-high OR MSI-H))",
                "Intermediate": "HRD-High OR TMB-high OR MSI-H",
                "Unfavorable": "else",
            },
        },
        "coverage": coverage_counts(df, [args.time_col, args.event_col, "tmb", "msi_status", "hrd_proxy", "brca_somatic"]),
        "usable": {"n": int(len(sub)), "counts": counts},
        "results": {
            "logrank_p": float(mv.p_value) if mv.p_value is not None else None,
            "test_statistic": float(mv.test_statistic) if mv.test_statistic is not None else None,
            "median_days_by_tier": km_medians,
            "figure": str(fig_path),
        },
        "notes": [
            "This is a retrospective stratification check, not proof of treatment effect.",
            "Germline BRCA is unknown in this cohort; BRCA_somatic is used as a proxy stratifier.",
        ],
    }

    out_json = paths.reports_dir / "validate_multimodal_risk_report.json"
    write_json(out_json, report)

    md = f"""# Multi-modal Risk Stratification Validation

- **Cohort**: `{paths.cohort_json}` (sha256: `{report['inputs']['cohort_sha256']}`)
- **Endpoint**: `{args.time_col}` / `{args.event_col}`

## Tier definition

- Favorable: {report['inputs']['tier_definition']['Favorable']}
- Intermediate: {report['inputs']['tier_definition']['Intermediate']}
- Unfavorable: {report['inputs']['tier_definition']['Unfavorable']}

## Counts

- Usable n (non-missing endpoint): {report['usable']['n']}
- Tier counts: {report['usable']['counts']}

## Results

- Log-rank p (3-group): {report['results']['logrank_p']}
- Median days by tier: {report['results']['median_days_by_tier']}

## Figure

- `{fig_path}`

## Notes

- Retrospective stratification only; do not interpret as causal treatment effect.
"""

    out_md = paths.reports_dir / "validate_multimodal_risk_report.md"
    write_md(out_md, md)

    print(f"✅ Wrote {out_json}")
    print(f"✅ Wrote {out_md}")
    print(f"✅ Wrote {fig_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
