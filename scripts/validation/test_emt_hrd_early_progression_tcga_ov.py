#!/usr/bin/env python3
"""
EMT + HRD score test using an *available* proxy endpoint in TCGA-OV PanCan Atlas:
early recurrence / progression after initial therapy.

Motivation
----------
Public cBioPortal OV studies do not expose a clean "platinum response" clinical attribute.
Our prior platinum labels (sensitive/resistant/refractory) are attached to the TRUE-SAE v2 cohort
and do NOT overlap with HRD+expression resources (intersection contains only sensitive cases).

So we use a pragmatic proxy:
  - DFS_STATUS + DFS_MONTHS from cBioPortal (PanCan Atlas OV study)
  - Define EARLY EVENT as DFS event within a threshold window (default 12 months)

Then test:
  - EMT score (MFAP4+EFEMP1+VIM - CDH1)
  - Canonical HRD_Score (GDC PanCan DDR 2018)
  - Combined logistic regression (HRD + EMT)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import httpx


CBIO_BASE = "https://www.cbioportal.org/api"
STUDY_ID = "ov_tcga_pan_can_atlas_2018"
SAMPLE_LIST_ID = "ov_tcga_pan_can_atlas_2018_rna_seq_v2_mrna"
EXPR_PROFILE_ID = "ov_tcga_pan_can_atlas_2018_rna_seq_v2_mrna_median_all_sample_Zscores"

EMT_GENES = ["MFAP4", "EFEMP1", "VIM", "CDH1", "SNAI1"]


def tcga_patient_id(sample_id: str) -> str:
    if not sample_id:
        return sample_id
    parts = sample_id.split("-")
    return "-".join(parts[:3]) if len(parts) >= 3 else sample_id


def safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if np.isnan(v):
            return None
        return float(v)
    except Exception:
        return None


def parse_event_status(s: str) -> Optional[int]:
    if not isinstance(s, str) or not s:
        return None
    s = s.strip()
    if s.startswith("1:"):
        return 1
    if s.startswith("0:"):
        return 0
    return None


def get_entrez_ids(genes: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    with httpx.Client(timeout=60, headers={"Accept": "application/json"}) as c:
        for g in genes:
            r = c.get(f"{CBIO_BASE}/genes/{g}")
            r.raise_for_status()
            j = r.json()
            out[g] = int(j["entrezGeneId"])
    return out


def get_sample_ids(sample_list_id: str) -> List[str]:
    with httpx.Client(timeout=60, headers={"Accept": "application/json"}) as c:
        r = c.get(f"{CBIO_BASE}/sample-lists/{sample_list_id}")
        r.raise_for_status()
        j = r.json()
        return list(j.get("sampleIds") or [])


def fetch_expression(sample_ids: List[str], entrez_ids: List[int]) -> pd.DataFrame:
    rows: List[Dict] = []
    with httpx.Client(timeout=120, headers={"Accept": "application/json", "Content-Type": "application/json"}) as c:
        sample_chunk = 100
        for i in range(0, len(sample_ids), sample_chunk):
            payload = {"sampleIds": sample_ids[i : i + sample_chunk], "entrezGeneIds": entrez_ids}
            r = c.post(
                f"{CBIO_BASE}/molecular-profiles/{EXPR_PROFILE_ID}/molecular-data/fetch",
                params={"projection": "SUMMARY"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "items" in data:
                data = data["items"]
            rows.extend(data or [])
    df = pd.DataFrame(rows)
    return df[["sampleId", "patientId", "entrezGeneId", "value"]].copy()


def fetch_patient_clinical(patient_ids: List[str], attribute_ids: List[str]) -> pd.DataFrame:
    """
    Fetch patient-level clinical data via per-patient endpoint:
      GET /studies/{studyId}/patients/{patientId}/clinical-data

    NOTE: The bulk POST /clinical-data/fetch has been observed to return HTTP 200 with an empty body
    in this environment, so we use the deterministic per-patient fallback.
    """
    rows: List[Dict[str, str]] = []
    attrs = set(attribute_ids)
    with httpx.Client(timeout=60, headers={"Accept": "application/json"}) as c:
        for pid in patient_ids:
            try:
                r = c.get(f"{CBIO_BASE}/studies/{STUDY_ID}/patients/{pid}/clinical-data", params={"projection": "SUMMARY"})
                if r.status_code >= 400:
                    continue
                items = r.json() or []
                d = {it.get("clinicalAttributeId"): it.get("value") for it in items if it.get("clinicalAttributeId") in attrs}
                if d:
                    d["patient_id"] = pid
                    rows.append(d)
            except Exception:
                continue
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def auroc(y: np.ndarray, s: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--gdc_dir",
        default="oncology-coPilot/oncology-backend-minimal/data/external/gdc_pancan_ddr_2018",
    )
    ap.add_argument(
        "--early_months",
        type=float,
        default=12.0,
        help="DFS event within this many months => early progression (positive class)",
    )
    ap.add_argument(
        "--out_json",
        default="oncology-coPilot/oncology-backend-minimal/scripts/validation/out/emt_hrd_tcga_ov_early_progression.json",
    )
    args = ap.parse_args()

    # HRD_Score (canonical) from GDC PanCan DDR
    gdc_dir = Path(args.gdc_dir)
    scores_cols = (gdc_dir / "Scores.tsv").read_text().strip().split("\n")
    samples = pd.read_csv(gdc_dir / "Samples.tsv", sep="\t", header=None, names=["sample_id", "cancer_type"])
    ddr_scores = pd.read_csv(gdc_dir / "DDRscores.tsv", sep="\t", header=None, names=scores_cols)
    gdc = pd.concat([samples.reset_index(drop=True), ddr_scores.reset_index(drop=True)], axis=1)
    ov = gdc[gdc["cancer_type"] == "OV"].copy()
    ov["patient_id"] = ov["sample_id"].str[:12]
    hrd = ov[["patient_id", "HRD_Score"]].dropna().copy()

    # EMT expression from cBioPortal
    entrez_map = get_entrez_ids(EMT_GENES)
    rev = {v: k for k, v in entrez_map.items()}
    entrez_ids = [entrez_map[g] for g in EMT_GENES]
    sample_ids = get_sample_ids(SAMPLE_LIST_ID)
    expr_long = fetch_expression(sample_ids, entrez_ids)
    expr_long["gene"] = expr_long["entrezGeneId"].map(rev)
    expr_wide = expr_long.pivot_table(index="sampleId", columns="gene", values="value", aggfunc="mean").reset_index()
    expr_wide["patient_id"] = expr_wide["sampleId"].map(tcga_patient_id)
    expr_pat = expr_wide.groupby("patient_id")[EMT_GENES].mean(numeric_only=True).reset_index()

    # Clinical DFS status/months for these patients (PanCan Atlas)
    patient_ids = sorted(expr_pat["patient_id"].unique().tolist())
    clin = fetch_patient_clinical(patient_ids, ["DFS_MONTHS", "DFS_STATUS"])
    clin["dfs_months"] = clin["DFS_MONTHS"].map(safe_float)
    clin["dfs_event"] = clin["DFS_STATUS"].map(parse_event_status)
    clin = clin[["patient_id", "dfs_months", "dfs_event"]].copy()

    merged = expr_pat.merge(hrd, on="patient_id", how="inner").merge(clin, on="patient_id", how="inner")
    merged = merged[merged["dfs_months"].notna() & merged["dfs_event"].isin([0, 1])].copy()

    # Define early progression label
    early_thr = float(args.early_months)
    merged["y_early_prog"] = ((merged["dfs_event"] == 1) & (merged["dfs_months"] <= early_thr)).astype(int)

    y = merged["y_early_prog"].to_numpy()
    n = len(merged)
    pos = int(y.sum())
    print(f"Merged n={n}  early_events(pos)={pos}  threshold={early_thr}mo")
    if pos == 0 or pos == n:
        print("Degenerate label distribution; change threshold or check data.")
        return 0

    merged["emt_score"] = (merged["MFAP4"] + merged["EFEMP1"] + merged["VIM"] - merged["CDH1"]) / 4.0

    au_emt = auroc(y, merged["emt_score"].to_numpy())
    au_hrd = auroc(y, merged["HRD_Score"].to_numpy())
    au_emt_inv = auroc(y, -merged["emt_score"].to_numpy())
    au_hrd_inv = auroc(y, -merged["HRD_Score"].to_numpy())

    # Combined model CV AUROC
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import roc_auc_score

    X = merged[["HRD_Score", "emt_score"]].to_numpy()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=7)
    aucs = []
    for tr, te in cv.split(X, y):
        m = LogisticRegression(max_iter=500)
        m.fit(X[tr], y[tr])
        p = m.predict_proba(X[te])[:, 1]
        aucs.append(float(roc_auc_score(y[te], p)))

    out = {
        "meta": {
            "study_id": STUDY_ID,
            "sample_list_id": SAMPLE_LIST_ID,
            "expr_profile_id": EXPR_PROFILE_ID,
            "early_months_threshold": early_thr,
            "label": "early_progression = DFS event within threshold months",
        },
        "counts": {"n": n, "n_pos": pos, "pos_rate": pos / max(1, n)},
        "metrics": {
            "auroc_emt": au_emt,
            "auroc_emt_inverted": au_emt_inv,
            "auroc_hrd": au_hrd,
            "auroc_hrd_inverted": au_hrd_inv,
            "cv_auroc_hrd_plus_emt": {"mean": float(np.mean(aucs)), "std": float(np.std(aucs)), "folds": aucs},
        },
    }

    outp = Path(args.out_json)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"Wrote: {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


