#!/usr/bin/env python3
"""Validate IO boost biomarkers (TMB / MSI) vs survival endpoints.

Outputs:
- reports/validate_io_boost_report.json
- reports/validate_io_boost_report.md
- figures/figure_io_tmb_os.png
- figures/figure_io_msi_os.png
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from _validation_utils import CohortPaths, coverage_counts, km_and_logrank, load_tcga_ov_enriched_v2, now_utc_iso, sha256_file, write_json, write_md


def plot_km(stats, title: str, out_path: Path) -> None:
    plt.figure(figsize=(6.5, 4.5))
    ax = plt.gca()
    stats["kmf_a"].plot_survival_function(ax=ax, ci_show=True)
    stats["kmf_b"].plot_survival_function(ax=ax, ci_show=True)
    ax.set_title(title)
    ax.set_xlabel("Days")
    ax.set_ylabel("Survival probability")
    ax.grid(True, alpha=0.25)

    pval = stats.get("p_value")
    ax.text(
        0.98,
        0.02,
        f"log-rank p={pval:.3g}" if pval is not None else "log-rank p=NA",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to biomarker_enriched_cohorts/",
    )
    ap.add_argument("--tag", default=os.environ.get("COHORT_TAG"), help="Tag/label for outputs (default: COHORT_TAG env or cohort filename stem)")
    ap.add_argument("--tmb_threshold", type=float, default=20.0, help="TMB threshold (mut/Mb)")
    ap.add_argument("--time_col", choices=["os_days", "pfs_days"], default="os_days")
    ap.add_argument("--event_col", choices=["os_event", "pfs_event"], default="os_event")
    ap.add_argument(
        "--msi_source",
        choices=["msi_status", "msi_score_mantis", "msi_sensor_score"],
        default="msi_status",
        help="Use derived msi_status or raw scores (thresholded internally).",
    )
    args = ap.parse_args()

    paths = CohortPaths(root=Path(args.root).resolve())
    tag = args.tag or paths.cohort_json.stem
    tag = str(tag)
    df = load_tcga_ov_enriched_v2(paths.cohort_json)

    # TMB groups
    # TMB groups (dtype-safe)
    df["tmb_group"] = None
    tmb_mask = df["tmb"].notna()
    df.loc[tmb_mask & (df["tmb"] >= args.tmb_threshold), "tmb_group"] = "TMB-high"
    df.loc[tmb_mask & (df["tmb"] < args.tmb_threshold), "tmb_group"] = "TMB-low"

    # MSI groups
    if args.msi_source == "msi_status":
        df["msi_group"] = df["msi_status"].map(lambda x: "MSI-H" if x == "MSI-H" else ("MSS" if x == "MSS" else np.nan))
    elif args.msi_source == "msi_score_mantis":
        # threshold per enrichment receipt notes
        # threshold per enrichment receipt notes (dtype-safe)
        df["msi_group"] = None
        m = df["msi_score_mantis"].notna()
        df.loc[m & (df["msi_score_mantis"] > 0.4), "msi_group"] = "MSI-H"
        df.loc[m & (df["msi_score_mantis"] <= 0.4), "msi_group"] = "MSS"
    else:
        df["msi_group"] = None
        m = df["msi_sensor_score"].notna()
        df.loc[m & (df["msi_sensor_score"] > 3.5), "msi_group"] = "MSI-H"
        df.loc[m & (df["msi_sensor_score"] <= 3.5), "msi_group"] = "MSS"

    time_col = args.time_col
    event_col = args.event_col


    # KM + log-rank for TMB (safe for small/degenerate groups)
    sub_tmb = df[[time_col, event_col, 'tmb_group']].dropna()
    sub_tmb = sub_tmb[sub_tmb['tmb_group'].isin(['TMB-high','TMB-low'])]
    n_high = int((sub_tmb['tmb_group'] == 'TMB-high').sum())
    n_low = int((sub_tmb['tmb_group'] == 'TMB-low').sum())
    tmb_stats = {"n": int(len(sub_tmb)), "n_a": n_high, "n_b": n_low, "p_value": None, "test_statistic": None, "median_days_a": None, "median_days_b": None, "kmf_a": None, "kmf_b": None}
    fig_tmb = None
    if n_high >= 2 and n_low >= 2:
        try:
            tmb_stats = km_and_logrank(df, time_col=time_col, event_col=event_col, group_col='tmb_group', group_a='TMB-high', group_b='TMB-low')
            fig_tmb = paths.figures_dir / f"figure_io_tmb_{tag}_{'os' if time_col=='os_days' else 'pfs'}.png"
            plot_km(tmb_stats, f"{tag} {time_col.replace('_days','').upper()} by TMB (thr={args.tmb_threshold})", fig_tmb)
        except Exception:
            # leave p_value None; group may be degenerate for KM/logrank
            fig_tmb = None

    # KM + log-rank for MSI (safe for small/degenerate groups)
    sub_msi = df[[time_col, event_col, 'msi_group']].dropna()
    sub_msi = sub_msi[sub_msi['msi_group'].isin(['MSI-H','MSS'])]
    n_msi_h = int((sub_msi['msi_group'] == 'MSI-H').sum())
    n_mss = int((sub_msi['msi_group'] == 'MSS').sum())
    msi_stats = {"n": int(len(sub_msi)), "n_a": n_msi_h, "n_b": n_mss, "p_value": None, "test_statistic": None, "median_days_a": None, "median_days_b": None, "kmf_a": None, "kmf_b": None}
    fig_msi = None
    if n_msi_h >= 2 and n_mss >= 2:
        try:
            msi_stats = km_and_logrank(df, time_col=time_col, event_col=event_col, group_col='msi_group', group_a='MSI-H', group_b='MSS')
            fig_msi = paths.figures_dir / f"figure_io_msi_{tag}_{'os' if time_col=='os_days' else 'pfs'}.png"
            plot_km(msi_stats, f"{tag} {time_col.replace('_days','').upper()} by MSI ({args.msi_source})", fig_msi)
        except Exception:
            fig_msi = None

    report = {
        "run": {
            "generated_at": now_utc_iso(),
            "script": str(Path(__file__).name),
            "root": str(paths.root),
            "tag": tag,
        },
        "inputs": {
            "cohort_path": str(paths.cohort_json),
            "cohort_sha256": sha256_file(paths.cohort_json),
            "endpoint": {"time_col": time_col, "event_col": event_col},
            "tmb_threshold": args.tmb_threshold,
            "msi_source": args.msi_source,
        },
        "coverage": coverage_counts(df, [time_col, event_col, "tmb", "msi_status", "msi_score_mantis", "msi_sensor_score"]),
        "tmb": {
            "n": int(tmb_stats["n"]),
            "n_high": int(tmb_stats["n_a"]),
            "n_low": int(tmb_stats["n_b"]),
            "logrank_p": tmb_stats.get("p_value"),
            "median_days_high": tmb_stats.get("median_days_a"),
            "median_days_low": tmb_stats.get("median_days_b"),
            "figure": str(fig_tmb) if fig_tmb else None,
        },
        "msi": {
            "n": int(msi_stats["n"]),
            "n_msi_h": int(msi_stats["n_a"]),
            "n_mss": int(msi_stats["n_b"]),
            "logrank_p": msi_stats.get("p_value"),
            "median_days_msi_h": msi_stats.get("median_days_a"),
            "median_days_mss": msi_stats.get("median_days_b"),
            "figure": str(fig_msi) if fig_msi else None,
        },
        "notes": [
            "These are retrospective stratification checks, not causal claims of IO benefit.",
            f"Cohort biology may limit MSI-H/TMB-high prevalence; interpret group sizes first (tag={tag}).",
        ],
    }

    out_json = paths.reports_dir / f"validate_io_boost_{tag}_report.json"
    write_json(out_json, report)

    md = f"""# IO Boost Biomarker Validation (TMB / MSI) — {tag}

- **Cohort**: `{paths.cohort_json}` (sha256: `{report['inputs']['cohort_sha256']}`)
- **Endpoint**: `{time_col}` / `{event_col}`

## TMB stratification

- Threshold: {args.tmb_threshold}
- Usable n: {report['tmb']['n']} (TMB-high={report['tmb']['n_high']}, TMB-low={report['tmb']['n_low']})
- Log-rank p: {report['tmb']['logrank_p']}
- Median days (high): {report['tmb']['median_days_high']}
- Median days (low): {report['tmb']['median_days_low']}
- Figure: `{fig_tmb}`

## MSI stratification

- MSI source: {args.msi_source}
- Usable n: {report['msi']['n']} (MSI-H={report['msi']['n_msi_h']}, MSS={report['msi']['n_mss']})
- Log-rank p: {report['msi']['logrank_p']}
- Median days (MSI-H): {report['msi']['median_days_msi_h']}
- Median days (MSS): {report['msi']['median_days_mss']}
- Figure: `{fig_msi}`

## Notes

- Retrospective stratification only; do not interpret as proof of treatment effect.
"""

    out_md = paths.reports_dir / f"validate_io_boost_{tag}_report.md"
    write_md(out_md, md)

    print(f"✅ Wrote {out_json}")
    print(f"✅ Wrote {out_md}")
    print(f"✅ Wrote {fig_tmb}")
    print(f"✅ Wrote {fig_msi}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
