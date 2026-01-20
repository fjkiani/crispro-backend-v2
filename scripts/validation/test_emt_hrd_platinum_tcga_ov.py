#!/usr/bin/env python3
"""
Test EMT markers + canonical HRD score vs platinum response in TCGA-OV.

Why this exists
--------------
We previously found mutation-derived DDR_bin is confounded and does not track canonical HRD_Score.
This script tests two orthogonal, literature-motivated predictors of PRIMARY platinum resistance:
  - EMT/stromal phenotype (MFAP4, EFEMP1, VIM high; CDH1 low)
  - Canonical HRD_Score (Knijnenburg / GDC PanCan DDR 2018)

Outputs:
  - downloaded expression JSON (sample -> gene -> zscore)
  - printed AUROCs for EMT score, HRD_Score, and combined model
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

import httpx


CBIO_BASE = "https://www.cbioportal.org/api"
STUDY_ID = "ov_tcga_pan_can_atlas_2018"
SAMPLE_LIST_ID = "ov_tcga_pan_can_atlas_2018_rna_seq_v2_mrna"
EXPR_PROFILE_ID = "ov_tcga_pan_can_atlas_2018_rna_seq_v2_mrna_median_all_sample_Zscores"


EMT_GENES = ["MFAP4", "EFEMP1", "VIM", "CDH1", "SNAI1"]


def tcga_patient_id(sample_id: str) -> str:
    # TCGA-XX-XXXX-01 -> TCGA-XX-XXXX
    if not sample_id:
        return sample_id
    parts = sample_id.split("-")
    return "-".join(parts[:3]) if len(parts) >= 3 else sample_id


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


def fetch_expression_zscores(sample_ids: List[str], entrez_ids: List[int]) -> pd.DataFrame:
    """
    Returns long-form df with columns: sampleId, entrezGeneId, value
    """
    rows: List[Dict] = []
    with httpx.Client(timeout=120, headers={"Accept": "application/json", "Content-Type": "application/json"}) as c:
        # Chunk sample IDs to avoid payload size issues
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
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    keep = [c for c in ["sampleId", "entrezGeneId", "value"] if c in df.columns]
    return df[keep].copy()


def auroc(y: np.ndarray, s: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cohort_csv",
        default="oncology-coPilot/oncology-backend-minimal/scripts/validation/out/ddr_bin_ov_platinum_TRUE_SAE_v2/linked_patients.adjusted.csv",
    )
    ap.add_argument(
        "--gdc_dir",
        default="oncology-coPilot/oncology-backend-minimal/data/external/gdc_pancan_ddr_2018",
    )
    ap.add_argument(
        "--out_expr_json",
        default="oncology-coPilot/oncology-backend-minimal/data/validation/tcga_ov_expression_emt.json",
    )
    args = ap.parse_args()

    cohort = pd.read_csv(args.cohort_csv)
    cohort["patient_id"] = cohort["patient_id"].astype(str)

    # Platinum labels: resistant/refractory = 1, sensitive = 0
    def lab(x):
        if not isinstance(x, str):
            return np.nan
        v = x.strip().lower()
        if v == "sensitive":
            return 0
        if v in ("resistant", "refractory"):
            return 1
        return np.nan

    cohort["y_platinum"] = cohort["platinum_response"].map(lab)
    cohort = cohort[cohort["y_platinum"].notna()].copy()
    cohort["y_platinum"] = cohort["y_platinum"].astype(int)

    # Load canonical HRD_Score from GDC PanCan DDR
    gdc_dir = Path(args.gdc_dir)
    scores_cols = (gdc_dir / "Scores.tsv").read_text().strip().split("\n")
    samples = pd.read_csv(gdc_dir / "Samples.tsv", sep="\t", header=None, names=["sample_id", "cancer_type"])
    ddr_scores = pd.read_csv(gdc_dir / "DDRscores.tsv", sep="\t", header=None, names=scores_cols)
    gdc = pd.concat([samples.reset_index(drop=True), ddr_scores.reset_index(drop=True)], axis=1)
    ov = gdc[gdc["cancer_type"] == "OV"].copy()
    ov["patient_id"] = ov["sample_id"].str[:12]
    hrd = ov[["patient_id", "HRD_Score"]].dropna().copy()

    # Download EMT expression (z-scores)
    entrez_map = get_entrez_ids(EMT_GENES)
    entrez_ids = [entrez_map[g] for g in EMT_GENES]
    sample_ids = get_sample_ids(SAMPLE_LIST_ID)
    expr_long = fetch_expression_zscores(sample_ids, entrez_ids)
    if expr_long.empty:
        raise RuntimeError("No expression rows returned from cBioPortal molecular-data/fetch")

    # Pivot to sample x gene
    rev = {v: k for k, v in entrez_map.items()}
    expr_long["gene"] = expr_long["entrezGeneId"].map(rev)
    expr_wide = expr_long.pivot_table(index="sampleId", columns="gene", values="value", aggfunc="mean")
    expr_wide.reset_index(inplace=True)
    expr_wide["patient_id"] = expr_wide["sampleId"].map(tcga_patient_id)

    # Save expression JSON (sample -> gene -> value)
    outp = Path(args.out_expr_json)
    outp.parent.mkdir(parents=True, exist_ok=True)
    as_json = {sid: {g: float(expr_wide.loc[i, g]) for g in EMT_GENES if g in expr_wide.columns} for i, sid in enumerate(expr_wide["sampleId"].tolist())}
    outp.write_text(json.dumps(as_json, indent=2, sort_keys=True))

    # Merge cohort + HRD + expression (patient-level)
    # If multiple samples per patient, average expression per patient
    expr_pat = expr_wide.groupby("patient_id")[EMT_GENES].mean(numeric_only=True).reset_index()
    merged = cohort.merge(expr_pat, on="patient_id", how="inner").merge(hrd, on="patient_id", how="inner")
    print(f"Merged rows (cohort ∩ EMT expr ∩ HRD): n={len(merged)}  pos={int(merged['y_platinum'].sum())}")

    if len(merged) < 40 or merged["y_platinum"].nunique() < 2:
        print("Not enough merged samples to compute stable AUROCs.")
        return 0

    # EMT score: high MFAP4/EFEMP1/VIM and low CDH1 => resistant
    merged["emt_score"] = (merged["MFAP4"] + merged["EFEMP1"] + merged["VIM"] - merged["CDH1"]) / 4.0

    y = merged["y_platinum"].to_numpy()
    au_emt = auroc(y, merged["emt_score"].to_numpy())
    au_hrd = auroc(y, merged["HRD_Score"].to_numpy())

    # Orientation sanity-check
    au_hrd_inv = auroc(y, -merged["HRD_Score"].to_numpy())
    au_emt_inv = auroc(y, -merged["emt_score"].to_numpy())

    print(f"AUROC EMT score (as_is)={au_emt:.3f}  (inv)={au_emt_inv:.3f}")
    print(f"AUROC HRD_Score (as_is)={au_hrd:.3f}  (inv)={au_hrd_inv:.3f}")

    # Combined model (logistic regression) with stratified CV
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
    print(f"CV AUROC (HRD + EMT) mean={np.mean(aucs):.3f} std={np.std(aucs):.3f} folds={aucs}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


