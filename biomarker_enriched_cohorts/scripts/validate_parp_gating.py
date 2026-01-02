#!/usr/bin/env python3
"""Validate PARP gating proxy via HRD proxy stratification (OS/PFS).

This does NOT claim causal PARP benefit; it checks whether the HRD proxy
stratifies survival endpoints in TCGA-OV.

Outputs:
- reports/validate_parp_gating_report.json
- reports/validate_parp_gating_report.md
- figures/figure_parp_hrd_proxy_os.png
- figures/figure_parp_hrd_proxy_pfs.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from _validation_utils import CohortPaths, coverage_counts, km_and_logrank, load_tcga_ov_enriched_v2, now_utc_iso, sha256_file, write_json, write_md


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to biomarker_enriched_cohorts/",
    )
    ap.add_argument(
        "--hrd_threshold",
        type=float,
        default=0.42,
        help="Threshold on hrd_proxy_numeric (0-1) for HRD-high.",
    )
    ap.add_argument(
        "--time_col",
        choices=["os_days", "pfs_days"],
        default="os_days",
        help="Endpoint time column.",
    )
    ap.add_argument(
        "--event_col",
        choices=["os_event", "pfs_event"],
        default="os_event",
        help="Endpoint event column.",
    )
    args = ap.parse_args()

    paths = CohortPaths(root=Path(args.root).resolve())
    df = load_tcga_ov_enriched_v2(paths.cohort_json)

    # Map hrd_proxy category → numeric proxy (for thresholding). This is intentionally simple.
    hrd_map = {
        "HRD-High": 1.0,
        "HRD-Intermediate": 0.5,
        "HRD-Low": 0.0,
        "Unknown": np.nan,
        None: np.nan,
    }
    df["hrd_proxy_numeric"] = df["hrd_proxy"].map(lambda x: hrd_map.get(x, np.nan))

    # Define groups
    # Define groups (dtype-safe; avoid numpy string/NaN promotion issues)
    df["hrd_group"] = None
    mask = df["hrd_proxy_numeric"].notna()
    df.loc[mask & (df["hrd_proxy_numeric"] >= args.hrd_threshold), "hrd_group"] = "HRD-high"
    df.loc[mask & (df["hrd_proxy_numeric"] < args.hrd_threshold), "hrd_group"] = "HRD-low"

    # Choose endpoint
    time_col = args.time_col
    event_col = args.event_col

    stats = km_and_logrank(df, time_col=time_col, event_col=event_col, group_col="hrd_group", group_a="HRD-high", group_b="HRD-low")

    # Plot
    plt.figure(figsize=(6.5, 4.5))
    ax = plt.gca()
    stats["kmf_a"].plot_survival_function(ax=ax, ci_show=True)
    stats["kmf_b"].plot_survival_function(ax=ax, ci_show=True)
    ax.set_title(f"TCGA-OV {time_col.replace('_days','').upper()} by HRD proxy (thr={args.hrd_threshold})")
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

    fig_name = f"figure_parp_hrd_proxy_{'os' if time_col=='os_days' else 'pfs'}.png"
    fig_path = paths.figures_dir / fig_name
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(fig_path, dpi=300)
    plt.close()

    report = {
        "run": {
            "generated_at": now_utc_iso(),
            "script": str(Path(__file__).name),
            "root": str(paths.root),
        },
        "inputs": {
            "cohort_path": str(paths.cohort_json),
            "cohort_sha256": sha256_file(paths.cohort_json),
            "hrd_threshold": args.hrd_threshold,
            "endpoint": {"time_col": time_col, "event_col": event_col},
        },
        "coverage": coverage_counts(df, [time_col, event_col, "hrd_proxy"]),
        "groups": {
            "n_total": int(len(df)),
            "n_usable": int(stats["n"]),
            "n_hrd_high": int(stats["n_a"]),
            "n_hrd_low": int(stats["n_b"]),
        },
        "results": {
            "logrank_p": stats.get("p_value"),
            "test_statistic": stats.get("test_statistic"),
            "median_days_hrd_high": stats.get("median_days_a"),
            "median_days_hrd_low": stats.get("median_days_b"),
            "figure": str(fig_path),
        },
        "notes": [
            "HRD proxy is derived (aneuploidy + FGA).",
            "This analysis tests stratification of survival endpoints, not treatment response to PARP inhibitors.",
        ],
    }

    out_json = paths.reports_dir / "validate_parp_gating_report.json"
    write_json(out_json, report)

    md = f"""# PARP Gate Proxy Validation (HRD proxy)

- **Cohort**: `{paths.cohort_json}` (sha256: `{report['inputs']['cohort_sha256']}`)
- **Endpoint**: `{time_col}` / `{event_col}`
- **HRD threshold**: `{args.hrd_threshold}` (on derived `hrd_proxy_numeric`)

## Counts

- Total patients: {report['groups']['n_total']}
- Usable (non-missing endpoint + HRD group): {report['groups']['n_usable']}
- HRD-high: {report['groups']['n_hrd_high']}
- HRD-low: {report['groups']['n_hrd_low']}

## Results

- Log-rank p-value: {report['results']['logrank_p']}
- Median {time_col} (HRD-high): {report['results']['median_days_hrd_high']}
- Median {time_col} (HRD-low): {report['results']['median_days_hrd_low']}

## Figure

- `{fig_path}`

## Notes

- HRD proxy is a **derived** label; treat as a proxy for genomic instability.
- This does **not** validate PARP drug response; it validates biomarker stratification signal in survival endpoints.
"""

    out_md = paths.reports_dir / "validate_parp_gating_report.md"
    write_md(out_md, md)

    print(f"✅ Wrote {out_json}")
    print(f"✅ Wrote {out_md}")
    print(f"✅ Wrote {fig_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
