#!/usr/bin/env python3
"""
Adjusted DDR_bin analysis (deconfounded) for OV TRUE-SAE v2 cohort.

Purpose
-------
We discovered DDR_bin is heavily confounded by:
  - ddr_bin_num_variants
  - ddr_bin_coverage

This script loads a patient-level CSV that already contains:
  - ddr_bin
  - ddr_bin_adj (residualized vs the confounders)
  - survival fields (os_months, os_event)
  - platinum_response labels (sensitive/resistant/refractory)

And writes a single JSON report that is safe to cite in docs.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd


def _safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if np.isnan(v):
            return None
        return float(v)
    except Exception:
        return None


def _platinum_label(val) -> Optional[int]:
    if not isinstance(val, str):
        return None
    v = val.strip().lower()
    if v == "sensitive":
        return 0
    if v in ("resistant", "refractory"):
        return 1
    return None


def _roc_auc_safe(y: np.ndarray, s: np.ndarray) -> Optional[float]:
    # Use sklearn if available; otherwise fall back to rank-based AUROC.
    try:
        from sklearn.metrics import roc_auc_score

        if len(np.unique(y)) < 2:
            return None
        return float(roc_auc_score(y, s))
    except Exception:
        return _auroc_rank(y, s)


def _auroc_rank(y: np.ndarray, s: np.ndarray) -> Optional[float]:
    """
    Tie-safe AUROC using average ranks.
    Returns AUROC for y in {0,1} (positive=1).
    """
    y = np.asarray(y).astype(int)
    s = np.asarray(s).astype(float)
    if len(np.unique(y)) < 2:
        return None
    # average ranks handles ties correctly; constant scores => 0.5
    from scipy.stats import rankdata

    r = rankdata(s, method="average")
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return None
    sum_r_pos = float(r[y == 1].sum())
    u = sum_r_pos - n_pos * (n_pos + 1) / 2.0
    return float(u / (n_pos * n_neg))


def _try_survival_stats(
    df: pd.DataFrame, score_col: str, duration_col: str = "os_months", event_col: str = "os_event"
) -> Dict[str, Any]:
    """
    Returns:
      - logrank p-value (median split)
      - Cox PH HR/p-value for score alone
      - Cox PH HR/p-value for score + confounders (if columns exist)
    """
    out: Dict[str, Any] = {}

    # Require lifelines for real survival stats; otherwise return error.
    try:
        from lifelines import CoxPHFitter
        from lifelines.statistics import logrank_test
    except Exception as e:
        out["error"] = f"lifelines_not_available: {type(e).__name__}"
        return out

    d = df[[duration_col, event_col, score_col]].copy()
    d = d[d[duration_col].notna() & (d[duration_col] > 0) & d[event_col].isin([0, 1]) & d[score_col].notna()].copy()
    out["n"] = int(len(d))
    out["events"] = int(d[event_col].sum())
    if len(d) < 30:
        out["error"] = f"insufficient_n: {len(d)}"
        return out

    med = float(d[score_col].median())
    d["_high"] = (d[score_col] >= med).astype(int)

    g0 = d[d["_high"] == 0]
    g1 = d[d["_high"] == 1]
    lr = logrank_test(
        g0[duration_col],
        g1[duration_col],
        event_observed_A=g0[event_col],
        event_observed_B=g1[event_col],
    )
    out["median_split"] = {
        "median": med,
        "n_low": int(len(g0)),
        "n_high": int(len(g1)),
        "logrank_p_value": float(lr.p_value),
        "median_os_low": _safe_float(g0[duration_col].median()),
        "median_os_high": _safe_float(g1[duration_col].median()),
    }

    # Cox: score alone
    cph = CoxPHFitter()
    cph.fit(d[[duration_col, event_col, score_col]], duration_col=duration_col, event_col=event_col)
    out["cox_score_only"] = {
        "hazard_ratio": float(cph.hazard_ratios_[score_col]),
        "p_value": float(cph.summary.loc[score_col, "p"]),
    }

    # Cox: score + confounders (if present)
    covars = [score_col]
    if "ddr_bin_num_variants" in df.columns:
        covars.append("ddr_bin_num_variants")
    if "ddr_bin_coverage" in df.columns:
        covars.append("ddr_bin_coverage")

    if len(covars) > 1:
        d2 = df[[duration_col, event_col] + covars].copy()
        d2 = d2[d2[duration_col].notna() & (d2[duration_col] > 0) & d2[event_col].isin([0, 1])].copy()
        d2["ddr_bin_coverage"] = pd.to_numeric(d2.get("ddr_bin_coverage", 0.0), errors="coerce").fillna(0.0)
        d2["ddr_bin_num_variants"] = pd.to_numeric(d2.get("ddr_bin_num_variants", 0.0), errors="coerce").fillna(0.0)

        cph2 = CoxPHFitter()
        cph2.fit(d2[[duration_col, event_col] + covars], duration_col=duration_col, event_col=event_col)
        out["cox_with_confounders"] = {}
        for c in covars:
            out["cox_with_confounders"][c] = {
                "hazard_ratio": float(cph2.hazard_ratios_[c]),
                "p_value": float(cph2.summary.loc[c, "p"]),
            }

    return out


@dataclass
class AdjustedReport:
    meta: Dict[str, Any]
    counts: Dict[str, Any]
    survival_os: Dict[str, Any]
    platinum: Dict[str, Any]
    extreme_survival: Dict[str, Any]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input_csv",
        type=str,
        default="oncology-coPilot/oncology-backend-minimal/scripts/validation/out/ddr_bin_ov_platinum_TRUE_SAE_v2/linked_patients.adjusted.csv",
    )
    ap.add_argument(
        "--out_json",
        type=str,
        default="oncology-coPilot/oncology-backend-minimal/scripts/validation/out/ddr_bin_ov_platinum_TRUE_SAE_v2/adjusted_analysis_results.json",
    )
    ap.add_argument("--extreme_low_months", type=float, default=36.0)
    ap.add_argument("--extreme_high_months", type=float, default=84.0)
    args = ap.parse_args()

    inp = Path(args.input_csv)
    if not inp.exists():
        raise FileNotFoundError(f"input_csv not found: {inp}")

    df = pd.read_csv(inp)

    # Normalize numeric columns
    for c in ["os_months", "os_event", "ddr_bin", "ddr_bin_adj", "ddr_bin_num_variants", "ddr_bin_coverage"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Counts
    plat = df["platinum_response"].map(_platinum_label) if "platinum_response" in df.columns else pd.Series([None] * len(df))
    counts = {
        "n_total": int(len(df)),
        "n_with_os": int(df["os_months"].notna().sum()) if "os_months" in df.columns else 0,
        "n_events_os": int(df["os_event"].fillna(0).sum()) if "os_event" in df.columns else 0,
        "n_platinum_labeled": int(plat.notna().sum()),
        "n_platinum_resistant_or_refractory": int((plat == 1).sum()),
        "n_platinum_sensitive": int((plat == 0).sum()),
    }

    # Survival (OS) on adjusted score
    survival_os = _try_survival_stats(df, score_col="ddr_bin_adj") if "ddr_bin_adj" in df.columns else {"error": "missing_ddr_bin_adj"}

    # Platinum AUROC (resistant/refractory as positive)
    platinum_report: Dict[str, Any] = {"error": None}
    if "ddr_bin_adj" in df.columns and "platinum_response" in df.columns:
        valid = plat.notna() & df["ddr_bin_adj"].notna()
        y = plat[valid].astype(int).to_numpy()
        s = df.loc[valid, "ddr_bin_adj"].astype(float).to_numpy()
        auc = _roc_auc_safe(y, s)
        auc_inv = _roc_auc_safe(y, -s)
        platinum_report = {
            "positive_class": "resistant_or_refractory",
            "score": "ddr_bin_adj",
            "n": int(valid.sum()),
            "n_pos": int(y.sum()),
            "auroc": auc,
            "auroc_inverted_score": auc_inv,
            "best_auroc": max([x for x in [auc, auc_inv] if x is not None], default=None),
            "best_orientation": "as_is" if (auc is not None and (auc_inv is None or auc >= auc_inv)) else "inverted",
        }
    else:
        platinum_report = {"error": "missing_columns_for_platinum"}

    # Extreme survival AUROC: early death (<low) vs long survivor (>high)
    extreme_report: Dict[str, Any] = {"error": None}
    if "ddr_bin_adj" in df.columns and "os_months" in df.columns:
        low = float(args.extreme_low_months)
        high = float(args.extreme_high_months)
        ext = df[df["os_months"].notna() & ((df["os_months"] < low) | (df["os_months"] > high))].copy()
        ext = ext[ext["ddr_bin_adj"].notna()].copy()
        if len(ext) > 10:
            y = (ext["os_months"] < low).astype(int).to_numpy()  # 1=early death
            s = ext["ddr_bin_adj"].astype(float).to_numpy()
            auc = _roc_auc_safe(y, s)
            auc_inv = _roc_auc_safe(y, -s)
            extreme_report = {
                "label": f"early_death(<{low}mo) vs long_survivor(>{high}mo)",
                "n": int(len(ext)),
                "n_early_death": int(y.sum()),
                "n_long_survivor": int((y == 0).sum()),
                "auroc": auc,
                "auroc_inverted_score": auc_inv,
                "best_auroc": max([x for x in [auc, auc_inv] if x is not None], default=None),
                "best_orientation": "as_is" if (auc is not None and (auc_inv is None or auc >= auc_inv)) else "inverted",
            }
        else:
            extreme_report = {"error": f"insufficient_extreme_n: {len(ext)}"}
    else:
        extreme_report = {"error": "missing_columns_for_extreme_survival"}

    report = AdjustedReport(
        meta={
            "input_csv": str(inp),
            "out_json": str(Path(args.out_json)),
            "note": "ddr_bin_adj is residualized vs ddr_bin_num_variants and ddr_bin_coverage; interpret as deconfounded signal.",
        },
        counts=counts,
        survival_os=survival_os,
        platinum=platinum_report,
        extreme_survival=extreme_report,
    )

    outp = Path(args.out_json)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(asdict(report), indent=2, sort_keys=True))
    print(f"Wrote: {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


