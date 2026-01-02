#!/usr/bin/env python3
"""Baseline comparison for IO biomarkers (TMB-only vs MSI-only vs OR).

Goal: provide "Nature-tier" sanity checks:
- Does TMB-only stratify OS?
- Does MSI-only stratify OS?
- Does OR (TMB>=thr OR MSI-H) stratify OS?
- What are effect sizes (Cox HR + CI) for each?
- What is a post-hoc power approximation (Schoenfeld) given observed HR and event counts?

This is NOT a clinical claim about IO treatment benefit.

Outputs:
- reports/baseline_comparison_io_<tag>.json
- reports/baseline_comparison_io_<tag>.md
- figures/figure_baseline_comparison_io_<tag>.png (forest plot of HRs)

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

from _validation_utils import CohortPaths, km_and_logrank, load_tcga_ov_enriched_v2, now_utc_iso, sha256_file, write_json, write_md


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


def is_msi_h(x) -> bool | None:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    s = str(x).strip().upper()
    if not s:
        return None
    # Common labels: MSI-H, MSI-High
    if "MSI" in s and ("HIGH" in s or "-H" in s or s.endswith("H")) and "MSS" not in s:
        return True
    if "MSS" in s or "STABLE" in s:
        return False
    return None


def cox_hr(sub: pd.DataFrame, time_col: str, event_col: str, group_col: str, pos_label: str = "Positive"):
    """Cox HR (Positive vs Negative) with robust CI column handling."""

    df = sub[[time_col, event_col, group_col]].copy()
    df[time_col] = pd.to_numeric(df[time_col], errors="coerce")
    df[event_col] = df[event_col].map(lambda x: 1 if x is True or x == 1 else (0 if x is False or x == 0 else np.nan))
    df = df.dropna(subset=[time_col, event_col, group_col])

    # binary indicator: 1 for Positive
    df["x"] = (df[group_col] == pos_label).astype(int)

    if df["x"].nunique() < 2:
        return None, (None, None), None

    cph = CoxPHFitter()
    try:
        cph.fit(df[[time_col, event_col, "x"]], duration_col=time_col, event_col=event_col)
        coef = float(cph.params_["x"])
        hr = float(np.exp(coef))

        ci = cph.confidence_intervals_.loc["x"]
        lo_key = next((k for k in ci.index if "lower" in str(k).lower()), None)
        hi_key = next((k for k in ci.index if "upper" in str(k).lower()), None)
        if lo_key is None or hi_key is None:
            return hr, (None, None), float(cph.summary.loc["x", "p"])
        lo = float(np.exp(ci[lo_key]))
        hi = float(np.exp(ci[hi_key]))

        p = float(cph.summary.loc["x", "p"])
        return hr, (lo, hi), p
    except Exception:
        return None, (None, None), None


def approx_logrank_power(hr: float | None, n_events: int, frac_positive: float, alpha: float = 0.05) -> float | None:
    """Post-hoc power approximation from HR using Schoenfeld/log-rank."""

    if hr is None or hr <= 0:
        return None
    if n_events <= 0:
        return None
    p = float(frac_positive)
    if p <= 0 or p >= 1:
        return None

    z_alpha = norm.ppf(1 - alpha / 2.0)
    z = math.sqrt(n_events * p * (1.0 - p)) * abs(math.log(hr)) - z_alpha
    return float(norm.cdf(z))


def build_groups(df: pd.DataFrame, tmb_thr: float) -> pd.DataFrame:
    out = df.copy()

    tmb = pd.to_numeric(out.get("tmb"), errors="coerce")
    out["_tmb_known"] = tmb.notna()
    out["_tmb_pos"] = (tmb >= tmb_thr).fillna(False)

    msi_flag = out.get("msi_status").map(is_msi_h) if "msi_status" in out.columns else pd.Series([None] * len(out), index=out.index)
    out["_msi_known"] = msi_flag.notna()
    out["_msi_pos"] = msi_flag.fillna(False).astype(bool)

    def make_group(pos: pd.Series, known: pd.Series) -> pd.Series:
        g = pd.Series(np.nan, index=out.index, dtype=object)
        g[known & (~pos)] = "Negative"
        g[known & (pos)] = "Positive"
        return g

    out["group_tmb"] = make_group(out["_tmb_pos"], out["_tmb_known"])
    out["group_msi"] = make_group(out["_msi_pos"], out["_msi_known"])

    any_known = out["_tmb_known"] | out["_msi_known"]
    pos_or = (out["_tmb_known"] & out["_tmb_pos"]) | (out["_msi_known"] & out["_msi_pos"])
    neg_or = any_known & (~pos_or)

    grp_or = pd.Series(np.nan, index=out.index, dtype=object)
    grp_or[neg_or] = "Negative"
    grp_or[pos_or] = "Positive"
    out["group_or"] = grp_or

    return out


def run_one(df: pd.DataFrame, group_col: str, time_col: str, event_col: str, min_group_size: int) -> dict:
    sub = df[[time_col, event_col, group_col]].dropna()
    sub = sub[sub[group_col].isin(["Positive", "Negative"])].copy()

    n_pos = int((sub[group_col] == "Positive").sum())
    n_neg = int((sub[group_col] == "Negative").sum())
    n = int(len(sub))

    ev = pd.to_numeric(sub[event_col], errors="coerce").fillna(0)
    n_events = int(ev.sum())

    if n_pos < min_group_size or n_neg < min_group_size:
        return {
            "n": n,
            "n_positive": n_pos,
            "n_negative": n_neg,
            "events": n_events,
            "logrank_p": None,
            "logrank_stat": None,
            "median_days_positive": None,
            "median_days_negative": None,
            "cox_hr_pos_vs_neg": None,
            "cox_ci": [None, None],
            "cox_p": None,
            "approx_logrank_power": None,
            "note": f"Skipped KM/log-rank (min_group_size={min_group_size})",
        }

    km = km_and_logrank(
        df=sub,
        time_col=time_col,
        event_col=event_col,
        group_col=group_col,
        group_a="Negative",
        group_b="Positive",
    )

    hr, (lo, hi), p_cph = cox_hr(sub, time_col=time_col, event_col=event_col, group_col=group_col)
    frac_pos = (n_pos / n) if n else 0.0
    pw = approx_logrank_power(hr=hr, n_events=n_events, frac_positive=frac_pos)

    return {
        "n": int(km.get("n")),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "events": n_events,
        "logrank_p": km.get("p_value"),
        "logrank_stat": km.get("test_statistic"),
        "median_days_negative": km.get("median_days_a"),
        "median_days_positive": km.get("median_days_b"),
        "cox_hr_pos_vs_neg": hr,
        "cox_ci": [lo, hi],
        "cox_p": p_cph,
        "approx_logrank_power": pw,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to biomarker_enriched_cohorts/",
    )
    ap.add_argument("--tag", default=os.environ.get("COHORT_TAG"))
    ap.add_argument("--time_col", default="os_days")
    ap.add_argument("--event_col", default="os_event")
    ap.add_argument("--tmb_threshold", type=float, default=20.0)
    ap.add_argument("--min_group_size", type=int, default=20)
    args = ap.parse_args()

    root = Path(args.root)
    paths = CohortPaths(root)
    cohort_path = paths.cohort_json
    tag = infer_tag(cohort_path, args.tag)

    df = load_tcga_ov_enriched_v2(cohort_path)
    df = build_groups(df, tmb_thr=args.tmb_threshold)

    res = {
        "tmb_only": run_one(df, "group_tmb", args.time_col, args.event_col, args.min_group_size),
        "msi_only": run_one(df, "group_msi", args.time_col, args.event_col, args.min_group_size),
        "or_gate": run_one(df, "group_or", args.time_col, args.event_col, args.min_group_size),
    }

    out_json = paths.reports_dir / f"baseline_comparison_io_{tag}.json"
    out_md = paths.reports_dir / f"baseline_comparison_io_{tag}.md"
    out_fig = paths.figures_dir / f"figure_baseline_comparison_io_{tag}.png"

    obj = {
        "tag": tag,
        "generated_at": now_utc_iso(),
        "cohort": str(cohort_path),
        "cohort_sha256": sha256_file(cohort_path),
        "endpoint": {"time_col": args.time_col, "event_col": args.event_col},
        "tmb_threshold": args.tmb_threshold,
        "min_group_size": args.min_group_size,
        "results": res,
        "notes": [
            "Baseline comparison is a cohort suitability sanity-check for IO biomarker prevalence/power.",
            "Not a claim of IO treatment benefit.",
        ],
    }

    write_json(out_json, obj)

    # Forest plot of HRs (Positive vs Negative)
    labels = ["TMB-only", "MSI-only", "OR (TMB or MSI)"]
    keys = ["tmb_only", "msi_only", "or_gate"]

    hrs = [res[k].get("cox_hr_pos_vs_neg") for k in keys]
    cis = [res[k].get("cox_ci") for k in keys]

    y = np.arange(len(labels))[::-1]

    plt.figure(figsize=(7.6, 3.8))
    ax = plt.gca()
    ax.axvline(1.0, color="#888", linestyle="--", linewidth=1)

    for yi, lab, hr, ci, k in zip(y, labels, hrs, cis, keys):
        r = res[k]
        n = r.get("n")
        npos = r.get("n_positive")
        p = r.get("logrank_p")

        if hr is None or ci is None or ci[0] is None or ci[1] is None:
            ax.plot([np.nan], [yi], marker="o", color="#444")
            ax.text(0.02, yi, f"{lab} (N={n}, pos={npos}) — HR NA", va="center", transform=ax.get_yaxis_transform())
            continue

        lo, hi = float(ci[0]), float(ci[1])
        ax.plot([hr], [yi], marker="o", color="#1565C0")
        ax.hlines(yi, lo, hi, color="#1565C0", linewidth=2)
        ax.text(
            0.02,
            yi,
            f"{lab} (N={n}, pos={npos})  HR={hr:.2f} [{lo:.2f}-{hi:.2f}]  logrank p={p:.3g}" if p is not None else f"{lab} (N={n}, pos={npos})  HR={hr:.2f} [{lo:.2f}-{hi:.2f}]  logrank p=NA",
            va="center",
            transform=ax.get_yaxis_transform(),
            fontsize=9,
        )

    ax.set_yticks([])
    ax.set_xscale("log")
    ax.set_xlabel("Cox HR (Positive vs Negative) — log scale")
    ax.set_title(f"Baseline IO Biomarker Effect Sizes ({tag})")
    ax.grid(True, axis="x", alpha=0.25)

    plt.tight_layout()
    out_fig.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_fig, dpi=300)
    plt.close()

    # Markdown
    md = []
    md.append(f"# Baseline Comparison: IO Biomarkers ({tag})")
    md.append("")
    md.append(f"- Cohort: `{cohort_path}`")
    md.append(f"- Endpoint: {args.time_col}/{args.event_col}")
    md.append(f"- TMB threshold: {args.tmb_threshold}")
    md.append(f"- Min group size (KM/log-rank): {args.min_group_size}")
    md.append("")
    md.append("| Strategy | N | Positive | Negative | log-rank p | Cox HR (pos vs neg) | 95% CI | Cox p | Approx power |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    for lab, k in zip(labels, keys):
        r = res[k]
        hr = r.get("cox_hr_pos_vs_neg")
        lo, hi = (r.get("cox_ci") or [None, None])
        md.append(
            "| {lab} | {n} | {pos} | {neg} | {p} | {hr} | {ci} | {cp} | {pw} |".format(
                lab=lab,
                n=r.get("n"),
                pos=r.get("n_positive"),
                neg=r.get("n_negative"),
                p=("NA" if r.get("logrank_p") is None else f"{r['logrank_p']:.4g}"),
                hr=("NA" if hr is None else f"{hr:.2f}"),
                ci=("NA" if lo is None or hi is None else f"{float(lo):.2f}-{float(hi):.2f}"),
                cp=("NA" if r.get("cox_p") is None else f"{r['cox_p']:.4g}"),
                pw=("NA" if r.get("approx_logrank_power") is None else f"{r['approx_logrank_power']:.2f}"),
            )
        )

    md.append("")
    md.append(f"- Figure: `figures/{out_fig.name}`")
    write_md(out_md, "\n".join(md))

    print(f"✅ wrote {out_json}")
    print(f"✅ wrote {out_md}")
    print(f"✅ wrote {out_fig}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
