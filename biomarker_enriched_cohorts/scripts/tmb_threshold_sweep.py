#!/usr/bin/env python3
"""TMB threshold sensitivity sweep (receipt-backed).

Runs OS stratification across multiple TMB cutoffs. Intended for MSI/TMB-rich
cohorts like TCGA-UCEC and TCGA-COADREAD.

Outputs:
- reports/tmb_threshold_sweep_<tag>.json
- reports/tmb_threshold_sweep_<tag>.md
- figures/figure_tmb_threshold_sweep_<tag>.png

RUO only.
"""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter
from scipy.stats import norm

from _validation_utils import (
    CohortPaths,
    km_and_logrank,
    load_tcga_ov_enriched_v2,
    now_utc_iso,
    sha256_file,
    write_json,
    write_md,
)


def infer_tag(cohort_path: Path, tag: str | None) -> str:
    if tag:
        return tag
    s = cohort_path.stem.lower()
    if "ucec" in s:
        return "tcga_ucec"
    if "coadread" in s:
        return "tcga_coadread"
    if "ov" in s:
        return "tcga_ov"
    return cohort_path.stem


def cox_hr(df: pd.DataFrame, group_col: str, a: str, b: str, time_col: str, event_col: str):
    """Return hazard ratio (a vs b) and 95% CI using CoxPHFitter."""

    sub = df[[time_col, event_col, group_col]].copy()
    sub[time_col] = pd.to_numeric(sub[time_col], errors="coerce")
    sub[event_col] = sub[event_col].map(lambda x: 1 if x is True or x == 1 else (0 if x is False or x == 0 else np.nan))
    sub = sub.dropna(subset=[time_col, event_col, group_col])
    sub = sub[sub[group_col].isin([a, b])].copy()
    if sub.empty:
        return None, (None, None), None

    sub["x"] = (sub[group_col] == a).astype(int)

    cph = CoxPHFitter()
    try:
        cph.fit(sub[[time_col, event_col, "x"]], duration_col=time_col, event_col=event_col)
        coef = float(cph.params_["x"])
        hr = float(np.exp(coef))
        ci = cph.confidence_intervals_.loc["x"]
        # lifelines may label CI columns as "lower-bound"/"upper-bound" or "95% lower-bound"/"95% upper-bound"
        lo_key = next((k for k in ci.index if "lower" in str(k).lower()), None)
        hi_key = next((k for k in ci.index if "upper" in str(k).lower()), None)
        if lo_key is None or hi_key is None:
            return None, (None, None), None
        lo = float(np.exp(ci[lo_key]))
        hi = float(np.exp(ci[hi_key]))
        p = float(cph.summary.loc["x", "p"])
        return hr, (lo, hi), p
    except Exception:
        return None, (None, None), None


def approx_logrank_power(hr: float | None, n_events: int, frac_group_a: float, alpha: float = 0.05) -> float | None:
    """Post-hoc log-rank power approximation (Schoenfeld).

    power ≈ Φ( sqrt(E*p*(1-p)) * |log(HR)| - z_{1-α/2} )
    """

    if hr is None or hr <= 0:
        return None
    if n_events <= 0:
        return None
    p = float(frac_group_a)
    if p <= 0 or p >= 1:
        return None

    z_alpha = norm.ppf(1 - alpha / 2.0)
    z = math.sqrt(n_events * p * (1.0 - p)) * abs(math.log(hr)) - z_alpha
    return float(norm.cdf(z))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path iomarker_enriched_cohorts/",
    )
    ap.add_argument("--tag", default=os.environ.get("COHORT_TAG"), help="Output tag (e.g. tcga_ucec)")
    ap.add_argument("--time_col", default="os_days")
    ap.add_argument("--event_col", default="os_event")
    ap.add_argument("--thresholds", default="10,15,20,25,30", help="Comma-separated cutoffs")
    ap.add_argument("--min_group_size", type=int, default=20)
    args = ap.parse_args()

    root = Path(args.root)
    paths = CohortPaths(root)
    cohort_path = paths.cohort_json
    tag = infer_tag(cohort_path, args.tag)

    df = load_tcga_ov_enriched_v2(cohort_path)

    thresholds = [float(x.strip()) for x in args.thresholds.split(",") if x.strip()]

    # events (overall)
    ev = pd.to_numeric(df.get(args.event_col), errors="coerce").fillna(0)
    n_events = int(ev.sum())

    rows = []
    for thr in thresholds:
        grp = pd.Series(np.nan, index=df.index, dtype=object)
        tmb = pd.to_numeric(df.get("tmb"), errors="coerce")
        grp[tmb.notna() & (tmb < thr)] = "TMB-low"
        grp[tmb.notna() & (tmb >= thr)] = "TMB-high"
        df["tmb_group"] = grp

        # enforce minimum size for meaningful KM/log-rank
        sub = df[[args.time_col, args.event_col, "tmb_group"]].dropna()
        n_low = int((sub["tmb_group"] == "TMB-low").sum())
        n_high = int((sub["tmb_group"] == "TMB-high").sum())
        n = int(len(sub))

        if n_low >= args.min_group_size and n_high >= args.min_group_size:
            km = km_and_logrank(
                df=df,
                time_col=args.time_col,
                event_col=args.event_col,
                group_col="tmb_group",
                group_a="TMB-low",
                group_b="TMB-high",
            )
            logrank_p = km.get("p_value")
            logrank_stat = km.get("test_statistic")
            median_low = km.get("median_days_a")
            median_high = km.get("median_days_b")
        else:
            logrank_p = None
            logrank_stat = None
            median_low = None
            median_high = None

        hr, (lo, hi), cox_p = cox_hr(
            df=df,
            group_col="tmb_group",
            a="TMB-high",
            b="TMB-low",
            time_col=args.time_col,
            event_col=args.event_col,
        )

        frac_high = (n_high / n) if n else 0.0
        power = approx_logrank_power(hr=hr, n_events=n_events, frac_group_a=frac_high)

        rows.append(
            {
                "tmb_threshold": thr,
                "n": n,
                "n_low": n_low,
                "n_high": n_high,
                "logrank_p": logrank_p,
                "logrank_stat": logrank_stat,
                "median_days_low": median_low,
                "median_days_high": median_high,
                "cox_hr_high_vs_low": hr,
                "cox_ci": [lo, hi],
                "cox_p": cox_p,
                "events_total": n_events,
                "approx_logrank_power": power,
            }
        )

    # Write JSON
    out_json = paths.reports_dir / f"tmb_threshold_sweep_{tag}.json"
    write_json(
        out_json,
        {
            "tag": tag,
            "generated_at": now_utc_iso(),
            "cohort": str(cohort_path),
            "cohort_sha256": sha256_file(cohort_path),
            "endpoint": {"time_col": args.time_col, "event_col": args.event_col},
            "thresholds": thresholds,
            "min_group_size": args.min_group_size,
            "rows": rows,
            "notes": [
                "Post-hoc power is an approximation derived from Cox HR (Schoenfeld/log-rank).",
                "It is provided as a sanity-check, not a prospective power plan.",
            ],
        },
    )

    # Plot
    fig_path = paths.figures_dir / f"figure_tmb_threshold_sweep_{tag}.png"
    xs = [r["tmb_threshold"] for r in rows]
    ps = [r["logrank_p"] if r["logrank_p"] is not None else 1.0 for r in rows]
    hrs = [r["cox_hr_high_vs_low"] if r["cox_hr_high_vs_low"] is not None else np.nan for r in rows]

    plt.figure(figsize=(7.2, 4.4))
    ax1 = plt.gca()
    ax1.plot(xs, ps, marker="o", label="log-rank p")
    ax1.axhline(0.05, color="#888", linestyle="--", linewidth=1)
    ax1.set_yscale("log")
    ax1.set_xlabel("TMB-high cutoff (mut/Mb)")
    ax1.set_ylabel("log-rank p (log scale)")
    ax1.grid(True, alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(xs, hrs, marker="s", color="#C62828", label="Cox HR (high vs low)")
    ax2.axhline(1.0, color="#C62828", linestyle=":", linewidth=1)
    ax2.set_ylabel("Cox HR (TMB-high vs TMB-low)")

    plt.title(f"TMB Threshold Sensitivity ({tag})")
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="upper right", frameon=True)

    fig_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(fig_path, dpi=300)
    plt.close()

    # Write MD
    out_md = paths.reports_dir / f"tmb_threshold_sweep_{tag}.md"
    md = []
    md.append(f"# TMB Threshold Sensitivity Sweep ({tag})")
    md.append("")
    md.append(f"- Cohort: `{cohort_path}`")
    md.append(f"- Endpoint: {args.time_col}/{args.event_col}")
    md.append(f"- Min group size (KM/log-rank): {args.min_group_size}")
    md.append("")
    md.append("| Cutoff | N | TMB-high | TMB-low | log-rank p | Cox HR (high vs low) | 95% CI | Cox p | Approx power |")
    md.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        hr = r["cox_hr_high_vs_low"]
        lo, hi = r["cox_ci"]
        md.append(
            "| {thr:.0f} | {n} | {nh} | {nl} | {p} | {hr} | {ci} | {cp} | {pw} |".format(
                thr=r["tmb_threshold"],
                n=r["n"],
                nh=r["n_high"],
                nl=r["n_low"],
                p=("NA" if r["logrank_p"] is None else f"{r['logrank_p']:.4g}"),
                hr=("NA" if hr is None else f"{hr:.2f}"),
                ci=("NA" if lo is None or hi is None else f"{lo:.2f}-{hi:.2f}"),
                cp=("NA" if r["cox_p"] is None else f"{r['cox_p']:.4g}"),
                pw=("NA" if r["approx_logrank_power"] is None else f"{r['approx_logrank_power']:.2f}"),
            )
        )

    md.append("")
    md.append(f"- Figure: `figures/{fig_path.name}`")
    write_md(out_md, "\n".join(md))

    print(f"✅ wrote {out_json}")
    print(f"✅ wrote {out_md}")
    print(f"✅ wrote {fig_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
