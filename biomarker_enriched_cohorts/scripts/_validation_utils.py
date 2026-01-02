"""Shared helpers for biomarker_enriched_cohorts validation scripts.

All logic is RUO and receipt-driven. No network calls.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test


@dataclass(frozen=True)
class CohortPaths:
    root: Path

    @property
    def cohort_json(self) -> Path:
        env = os.environ.get("COHORT_JSON")
        if env:
            return Path(env)
        return self.root / "data" / "tcga_ov_enriched_v2.json"

    @property
    def figures_dir(self) -> Path:
        return self.root / "figures"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def receipts_dir(self) -> Path:
        return self.root / "receipts"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now_utc_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def load_tcga_ov_enriched_v2(cohort_path: Path) -> pd.DataFrame:
    obj = json.loads(cohort_path.read_text(encoding="utf-8"))
    pts = (obj.get("cohort") or {}).get("patients") or []
    rows: List[Dict[str, Any]] = []

    for pt in pts:
        outcomes = pt.get("outcomes") or {}
        rows.append(
            {
                "patient_id": pt.get("patient_id"),
                "os_days": outcomes.get("os_days"),
                "os_event": outcomes.get("os_event"),
                "pfs_days": outcomes.get("pfs_days"),
                "pfs_event": outcomes.get("pfs_event"),
                "tmb": pt.get("tmb"),
                "msi_score_mantis": pt.get("msi_score_mantis"),
                "msi_sensor_score": pt.get("msi_sensor_score"),
                "msi_status": pt.get("msi_status"),
                "aneuploidy_score": pt.get("aneuploidy_score"),
                "fraction_genome_altered": pt.get("fraction_genome_altered"),
                "hrd_proxy": pt.get("hrd_proxy"),
                "brca_somatic": pt.get("brca_somatic"),
                "germline_brca_status": pt.get("germline_brca_status"),
            }
        )

    df = pd.DataFrame(rows)
    # normalize booleans: keep as bool/NaN
    for b in ["os_event", "pfs_event"]:
        if b in df.columns:
            df[b] = df[b].map(lambda x: x if isinstance(x, bool) else (True if x == 1 else (False if x == 0 else np.nan)))

    # numeric casts
    for c in [
        "os_days",
        "pfs_days",
        "tmb",
        "msi_score_mantis",
        "msi_sensor_score",
        "aneuploidy_score",
        "fraction_genome_altered",
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def km_and_logrank(
    df: pd.DataFrame,
    time_col: str,
    event_col: str,
    group_col: str,
    group_a: str,
    group_b: str,
) -> Dict[str, Any]:
    sub = df[[time_col, event_col, group_col]].dropna()
    sub = sub[sub[group_col].isin([group_a, group_b])]

    a = sub[sub[group_col] == group_a]
    b = sub[sub[group_col] == group_b]

    # lifelines expects durations as float; events as bool
    t_a = a[time_col].astype(float)
    e_a = a[event_col].astype(bool)
    t_b = b[time_col].astype(float)
    e_b = b[event_col].astype(bool)

    res = logrank_test(t_a, t_b, event_observed_A=e_a, event_observed_B=e_b)

    kmf_a = KaplanMeierFitter().fit(t_a, event_observed=e_a, label=group_a)
    kmf_b = KaplanMeierFitter().fit(t_b, event_observed=e_b, label=group_b)

    def median_days(kmf: KaplanMeierFitter) -> Optional[float]:
        m = kmf.median_survival_time_
        if m is None or (isinstance(m, float) and (math.isnan(m) or math.isinf(m))):
            return None
        return float(m)

    return {
        "n": int(len(sub)),
        "n_a": int(len(a)),
        "n_b": int(len(b)),
        "p_value": float(res.p_value) if res.p_value is not None else None,
        "test_statistic": float(res.test_statistic) if res.test_statistic is not None else None,
        "median_days_a": median_days(kmf_a),
        "median_days_b": median_days(kmf_b),
        "kmf_a": kmf_a,
        "kmf_b": kmf_b,
    }


def write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def coverage_counts(df: pd.DataFrame, cols: Sequence[str]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    n = len(df)
    for c in cols:
        nn = int(df[c].notna().sum())
        out[c] = {"n": nn, "pct": float((nn / n) * 100.0) if n else 0.0}
    return out
